"""Capture invocation provenance and export validated CI coverage evidence."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Literal

import typer
from coverage.exceptions import CoverageException
from pydantic import ValidationError

from tools.quality_evidence_models import (
    EvidenceError,
    Outcome,
    Provenance,
    RunStart,
    require,
)
from tools.quality_evidence_reports import (
    clear_staged_reports,
    safe_tree,
    stage_reports,
)

app = typer.Typer(pretty_exceptions_enable=False)


def _git(*arguments: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise EvidenceError
    return subprocess.check_output(  # noqa: S603 - fixed read-only git arguments.
        [git, *arguments],
        text=True,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "GIT_MASTER": "1"},
        timeout=10,
    ).strip()


def _tool_version(name: Literal["uv", "just"]) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise EvidenceError
    return subprocess.check_output(  # noqa: S603 - fixed version-query commands.
        [executable, "--version"], text=True, timeout=10
    ).strip()


def _publication_ready(ready: bool) -> None:
    """Gate artifact upload on validation, independently of the failed gate status."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as stream:
            _ = stream.write(f"publish={'true' if ready else 'false'}\n")


@app.command()
def prepare() -> None:
    """Record checkout identity and start bounds before the separate gate step."""
    root = Path.cwd()
    try:
        start = RunStart(
            started_ns=time.time_ns(),
            tested_sha=_git("rev-parse", "HEAD"),
            expected_sha=os.environ.get("GITHUB_SHA") or None,
            pr_head_sha=os.environ.get("PR_HEAD_SHA") or None,
            event=os.environ.get("GITHUB_EVENT_NAME", "local"),
            ref=os.environ.get("GITHUB_REF", "local"),
            run_id=os.environ.get("GITHUB_RUN_ID", "0"),
            run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT", "0"),
            dirty=bool(_git("status", "--porcelain")),
        )
        require(start.expected_sha is None or start.expected_sha == start.tested_sha)
        output = root / "coverage"
        safe_tree(output)
        evidence = output / "evidence"
        if evidence.exists():
            shutil.rmtree(evidence)
        evidence.mkdir(parents=True)
        _ = (evidence / "start.json").write_text(start.model_dump_json(indent=2))
    except OSError, subprocess.SubprocessError, ValidationError, EvidenceError:
        _ = sys.stderr.write("cannot prepare current coverage invocation\n")
        raise typer.Exit(1) from None


@app.command()
def export(outcome: Annotated[Outcome, typer.Option()]) -> None:
    """Write honest provenance and summary without changing the gate outcome."""
    root = Path.cwd()
    evidence = root / "coverage/evidence"
    finished_ns = time.time_ns()
    try:
        _publication_ready(ready=False)
        safe_tree(root / "coverage")
        clear_staged_reports(evidence)
        start = RunStart.model_validate_json((evidence / "start.json").read_bytes())
        head = _git("rev-parse", "HEAD")
        dirty = bool(_git("status", "--porcelain"))
        totals = None
        availability: Literal["complete", "partial", "unavailable"] = "unavailable"
        reason = None
        try:
            require(head == start.tested_sha)
            require(start.expected_sha is None or head == start.expected_sha)
            require(start.run_id == os.environ.get("GITHUB_RUN_ID", "0"))
            require(start.run_attempt == os.environ.get("GITHUB_RUN_ATTEMPT", "0"))
            require(outcome in {Outcome.SUCCESS, Outcome.FAILURE})
            totals = stage_reports(root, start, finished_ns)
            availability = "complete" if outcome == Outcome.SUCCESS else "partial"
            if availability == "partial":
                reason = "failed gate; full-suite completion is unverified"
        except OSError, ValidationError, CoverageException, EvidenceError:
            clear_staged_reports(evidence)
            reason = "unavailable: missing/stale/invalid reports or checkout mismatch"
        provenance = Provenance(
            tested_sha=start.tested_sha,
            observed_export_sha=head,
            expected_sha=start.expected_sha,
            pr_head_sha=start.pr_head_sha,
            event=start.event,
            ref=start.ref,
            run_id=start.run_id,
            run_attempt=start.run_attempt,
            dirty=start.dirty or dirty,
            started_ns=start.started_ns,
            finished_ns=finished_ns,
            gate_outcome=outcome,
            availability=availability,
            reason=reason,
            totals=totals,
            versions={
                "python": platform.python_version(),
                "uv": _tool_version("uv"),
                "just": _tool_version("just"),
                **{
                    name: version(name) for name in ("coverage", "pytest", "pytest-cov")
                },
            },
        )
        _ = (evidence / "provenance.json").write_text(
            provenance.model_dump_json(indent=2), encoding="utf-8"
        )
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with Path(summary_path).open("a", encoding="utf-8") as stream:
                _ = stream.write(render_summary(provenance))
        safe_tree(evidence)
        _publication_ready(ready=True)
        if outcome != "success" or availability != "complete":
            raise typer.Exit(1)
    except OSError, subprocess.SubprocessError, ValidationError, EvidenceError:
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with Path(summary_path).open("a", encoding="utf-8") as stream:
                _ = stream.write(
                    "## Coverage evidence\n\nUnavailable: invalid provenance.\n"
                )
        raise typer.Exit(1) from None


def render_summary(provenance: Provenance) -> str:
    """Render count-derived measurement with explicit tested-vs-PR revision labels."""
    totals = provenance.totals
    measurement = "Measurement unavailable."
    if totals is not None:
        measurement = (
            f"Combined: **{totals.combined_percent:.6f}%**; floor: 99% "
            "(coverage.py precision semantics).\n"
            f"Statements: {totals.covered_lines}/{totals.num_statements}; "
            f"branches: {totals.covered_branches}/{totals.num_branches}; "
            f"excluded lines: {totals.excluded_lines}."
        )
    return (
        "## Coverage evidence\n\n"
        f"Gate: **{provenance.gate_outcome}**; "
        f"evidence: **{provenance.availability}**.\n\n"
        f"Tested checkout: `{provenance.tested_sha}`\n\n"
        f"Observed export checkout: `{provenance.observed_export_sha}`\n\n"
        f"PR head (not tested revision): `{provenance.pr_head_sha or 'N/A'}`\n\n"
        f"Event/ref: `{provenance.event}` / `{provenance.ref}`; "
        f"run {provenance.run_id}, attempt {provenance.run_attempt}.\n\n"
        f"{measurement}\n\n"
        f"{provenance.reason or 'Gate completed successfully.'}\n\n"
        "Download this run's coverage-evidence artifact (retained 7 days); "
        "open html/index.html, coverage.json, .coverage, and provenance.json. "
        "Unavailable reports are omitted, never replaced by an older baseline.\n"
    )


if __name__ == "__main__":
    app()
