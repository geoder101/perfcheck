"""Validate manual mutation receipts and stage only approved Action downloads."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Final, assert_never

from tools.mutation_campaign import BUDGET, SELECTION, TARGET
from tools.mutation_ci_models import Manifest, Start, Status
from tools.mutation_evidence import (
    EvidenceError,
    NativeStats,
    read_inventory,
    read_stats,
    require,
)

_FILES: Final = (
    "status.json",
    "manifest.json",
    "outcomes.json",
    "inspection.json",
    "imports.jsonl",
    "inspection-imports.jsonl",
    "results.txt",
    "parse.log",
    "baseline.log",
    "run.log",
    "export.log",
    "generated-baseline.log",
    "forced-failure.log",
    "inspect-killed.diff",
    "inspect-survived.diff",
    *(
        f"inspect-{verdict}-{index}.log"
        for verdict in ("killed", "survived")
        for index in range(3)
    ),
    "mutants/mutmut-cicd-stats.json",
    "mutants/mutmut-stats.json",
    f"mutants/{TARGET}",
    f"mutants/{TARGET}.meta",
)


def head(root: Path) -> str:
    """Read actual Git identity, never substitute an event label for HEAD."""
    return subprocess.check_output(  # noqa: S603 - fixed Git identity command
        [shutil.which("git") or "git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        timeout=10,
    ).strip()


def safe(root: Path, relative: str) -> Path:
    """Reject redirected paths before reading or staging artifact content."""
    path = root / relative
    require(
        all(
            not part.is_symlink()
            for part in (path, *path.parents)
            if part != root.parent
        ),
        "redirected evidence path",
    )
    return path


def digest(path: Path) -> str:
    """Hash a known input without persisting its contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root: Path) -> None:
    """Refuse stale outputs and record source identity before the pilot."""
    require(not safe(root, "mutation").exists(), "existing mutation output")
    require(not safe(root, "mutation-ci").exists(), "existing CI receipt")
    start = Start.model_validate(
        {
            "tested_sha": head(root),
            "expected_sha": os.environ["GITHUB_SHA"],
            "event": os.environ["GITHUB_EVENT_NAME"],
            "run_id": os.environ["GITHUB_RUN_ID"],
            "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
            "started_ns": time.time_ns(),
            "source_sha256": digest(root / TARGET),
            "lock_sha256": digest(root / "uv.lock"),
        }
    )
    require(start.tested_sha == start.expected_sha, "checkout SHA mismatch")
    (root / "mutation-ci").mkdir()
    _ = (root / "mutation-ci/start.json").write_text(start.model_dump_json(indent=2))


def counts(output: Path) -> NativeStats:
    """Reconcile recorded native counters with the raw target-only inventory."""
    stats = read_stats(output / "mutants/mutmut-cicd-stats.json")
    inventory = read_inventory(output / "mutants")
    codes = Counter(inventory.exit_code_by_key.values())
    require(
        all(code in {0, 1, 36, -24, 24, 152, 255} for code in codes),
        "invalid raw outcomes",
    )
    expected = NativeStats(
        killed=codes[1],
        survived=codes[0],
        total=len(inventory.exit_code_by_key),
        timeout=sum(codes[key] for key in (36, -24, 24, 152, 255)),
        no_tests=0,
        skipped=0,
        suspicious=0,
        check_was_interrupted_by_user=0,
        segfault=0,
    )
    require(stats == expected, "counts mismatch")
    return stats


def export(root: Path) -> int:
    """Always explain unavailable evidence; publish only safely staged known files."""
    ci = safe(root, "mutation-ci")
    ci.mkdir(exist_ok=True)
    published = False
    message = "Evidence rejected or unavailable; no complete experiment claimed."
    code = 1
    try:
        candidates = (
            "mutation-ci/start.json",
            "mutation-ci/stdout.log",
            *(f"mutation/{name}" for name in _FILES),
        )
        selected = tuple(safe(root, name) for name in candidates)
        stage = safe(root, "mutation-ci/evidence")
        stage.mkdir()
        for path in selected:
            if path.is_file():
                destination = stage / path.relative_to(root)
                destination.parent.mkdir(parents=True, exist_ok=True)
                _ = shutil.copyfile(path, destination)
        published = True
        start = Start.model_validate_json((ci / "start.json").read_text())
        require(
            start.tested_sha
            == start.expected_sha
            == os.environ["GITHUB_SHA"]
            == head(root),
            "checkout identity mismatch",
        )
        require(
            start.source_sha256 == digest(root / TARGET)
            and start.lock_sha256 == digest(root / "uv.lock"),
            "source identity mismatch",
        )
        output = root / "mutation"
        status = Status.model_validate_json((output / "status.json").read_text())
        outcome = os.environ["MUTATION_OUTCOME"]
        require(
            outcome in {"success", "failure", "cancelled", "skipped"},
            "unknown step outcome",
        )
        require(
            (status.status == "complete") == (outcome == "success"),
            "step/status mismatch",
        )
        match status.status:
            case "invalid" | "incomplete":
                message = (
                    f"Status: {status.status}; counts unavailable/unvalidated. "
                    f"Step: {outcome}."
                )
            case "complete":
                manifest = Manifest.model_validate_json(
                    (output / "manifest.json").read_text()
                )
                require(
                    manifest.source_sha256 == start.source_sha256
                    and manifest.lock_sha256 == start.lock_sha256,
                    "manifest identity mismatch",
                )
                require(
                    manifest.target == TARGET
                    and manifest.tests == SELECTION
                    and manifest.child_budget_seconds == BUDGET
                    and status.source_unchanged,
                    "invalid policy receipt",
                )
                for name in (
                    "status.json",
                    "manifest.json",
                    "mutants/mutmut-cicd-stats.json",
                    f"mutants/{TARGET}.meta",
                    "results.txt",
                    "run.log",
                    "baseline.log",
                    "parse.log",
                    "outcomes.json",
                    "inspection.json",
                    "imports.jsonl",
                    "inspection-imports.jsonl",
                    "forced-failure.log",
                    "generated-baseline.log",
                    "export.log",
                ):
                    require(
                        (output / name).stat().st_mtime_ns >= start.started_ns
                        and (output / name).stat().st_size > 0,
                        "stale or empty evidence",
                    )
                stats = counts(output)
                message = (
                    f"Status: complete; total: {stats.total}; killed: {stats.killed}; "
                    f"survived: {stats.survived}; timeout: {stats.timeout}; "
                    f"other outcomes: 0. Tested SHA: `{start.tested_sha}`."
                )
                code = 0
            case unreachable:
                assert_never(unreachable)
    except EvidenceError, OSError, ValueError, KeyError, subprocess.SubprocessError:
        code = 1
    summary = (
        "## Manual mutation pilot\n\n"
        + message
        + "\n\n"
        + "Survivors are advisory; no survival-score gate. Command: `just mutation`.\n"
        "Target: `"
        + TARGET
        + "`; tests: `"
        + SELECTION
        + "`.\n"
        + "One worker; 600-second child budget. Download approved evidence from this "
        "run's mutation-evidence artifact (7-day retention); not published on Pages.\n"
    )
    _ = (ci / "summary.md").write_text(summary)
    if published:
        _ = shutil.copyfile(ci / "summary.md", ci / "evidence/summary.md")
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
        _ = stream.write(summary)
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
        _ = stream.write(f"publish={str(published).lower()}\n")
    return code


def main() -> int:
    """Expose the two fixed workflow phases without forwarding pilot options."""
    root = Path.cwd()
    match sys.argv[1:]:
        case ["prepare"]:
            prepare(root)
            return 0
        case ["export"]:
            return export(root)
        case _:
            return 2


if __name__ == "__main__":
    raise SystemExit(main())
