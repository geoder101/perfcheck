from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest
from pydantic import JsonValue, TypeAdapter

_ROOT: Final = Path(__file__).parents[1]
_JSON: Final = TypeAdapter(dict[str, JsonValue])


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COVERAGE_", "COV_CORE_", "_COVERAGE_"))
    }
    return subprocess.run(  # noqa: S603 - owned tool with controlled local fixtures.
        [sys.executable, "-P", "-m", "tools.quality_evidence", *args],
        cwd=root,
        env={
            **environment,
            "PYTHONPATH": str(_ROOT),
            "GITHUB_STEP_SUMMARY": str(root / "summary.md"),
            "GITHUB_EVENT_NAME": os.environ.get("EVIDENCE_TEST_EVENT", "pull_request"),
            "GITHUB_REF": os.environ.get("EVIDENCE_TEST_REF", "refs/pull/12/merge"),
            "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "2",
            "PR_HEAD_SHA": os.environ.get("EVIDENCE_TEST_HEAD", "a" * 40),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    git = shutil.which("git")
    assert git
    root = tmp_path / "checkout"
    _ = subprocess.run(  # noqa: S603 - clone local committed history, no new commits.
        [git, "clone", "--quiet", "--no-hardlinks", str(_ROOT), str(root)],
        env={**os.environ, "GIT_MASTER": "1"},
        capture_output=True,
        check=True,
        timeout=30,
    )
    result = _run(root, "prepare")
    assert result.returncode == 0, result.stderr
    return root


def _reports(root: Path, source: str = "x = 1\nif x:\n    x = 2\n") -> None:
    """Generate real branch-mode SQLite, JSON and HTML without the full suite."""
    sample = root / "sample.py"
    _ = sample.write_text(source, encoding="utf-8")
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COVERAGE_", "COV_CORE_", "_COVERAGE_"))
    }
    for arguments in (
        ("run", "--branch", "sample.py"),
        ("json", "-o", "coverage/coverage.json"),
        ("html", "-d", "coverage/html"),
    ):
        result = subprocess.run(  # noqa: S603 - real installed coverage on tiny input.
            [sys.executable, "-m", "coverage", *arguments],
            cwd=root,
            env={
                **environment,
                "COVERAGE_RCFILE": os.devnull,
                "COVERAGE_FILE": str(root / "coverage/.coverage"),
            },
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_export_records_actual_merge_revision_and_combined_counts(
    checkout: Path,
) -> None:
    # Given: fresh real reports and a PR head distinct from the checkout.
    _reports(checkout)
    git = shutil.which("git")
    assert git
    actual_head = subprocess.check_output(  # noqa: S603 - independent read-only oracle.
        [git, "rev-parse", "HEAD"],
        cwd=checkout,
        env={**os.environ, "GIT_MASTER": "1"},
        text=True,
        timeout=10,
    ).strip()
    # When: the actual CI exporter runs against a successful gate outcome.
    result = _run(checkout, "export", "--outcome", "success")
    # Then: exact checkout provenance, count-based measurement and raw data survive.
    assert result.returncode == 0, result.stderr
    evidence = checkout / "coverage/evidence"
    metadata = _JSON.validate_json((evidence / "provenance.json").read_bytes())
    marker = _JSON.validate_json((evidence / "start.json").read_bytes())
    assert metadata["tested_sha"] == marker["tested_sha"] == actual_head
    assert metadata["tested_sha"] != metadata["pr_head_sha"] == "a" * 40
    assert metadata["gate_outcome"] == "success"
    assert metadata["availability"] == "complete"
    assert metadata["dirty"] is True
    assert (evidence / ".coverage").read_bytes().startswith(b"SQLite format 3")
    assert (evidence / "html/index.html").is_file()
    summary = (checkout / "summary.md").read_text()
    assert str(metadata["tested_sha"]) in summary
    assert "PR head (not tested revision)" in summary
    assert "80.000000" in summary  # 3 statements + 1 of 2 branches, not averages.


@pytest.mark.parametrize("outcome", ["failure", "cancelled", "skipped"])
def test_nonpassing_gate_never_becomes_success(checkout: Path, outcome: str) -> None:
    # Given: valid reports cannot override the actual gate outcome.
    _reports(checkout)
    # When: export receives GitHub's actual nonpassing outcome.
    result = _run(checkout, "export", "--outcome", outcome)
    # Then: evidence remains diagnostic and the exporter also fails.
    assert result.returncode != 0
    metadata = _JSON.validate_json(
        (checkout / "coverage/evidence/provenance.json").read_bytes()
    )
    assert metadata["gate_outcome"] == outcome
    assert metadata["availability"] != "complete" or outcome == "failure"


@pytest.mark.parametrize(
    "damage",
    [
        "missing-json",
        "missing-html",
        "missing-raw",
        "malformed-json",
        "invalid-raw",
        "stale-json",
        "stale-raw",
        "stale-html",
        "wrong-sha",
        "unreadable-raw",
        "invalid-sqlite",
    ],
)
def test_invalid_evidence_is_unavailable_not_reused(
    checkout: Path, damage: str
) -> None:
    # Given: a measurement with one invalid report or altered checkout claim.
    _reports(checkout)
    paths = {
        "json": checkout / "coverage/coverage.json",
        "html": checkout / "coverage/html/index.html",
        "raw": checkout / "coverage/.coverage",
    }
    if damage.startswith("missing-"):
        paths[damage.removeprefix("missing-")].unlink()
    elif damage.startswith("stale-"):
        os.utime(paths[damage.removeprefix("stale-")], ns=(1, 1))
    elif damage == "malformed-json":
        _ = paths["json"].write_text('{"totals": {"num_statements": "bad"}}')
    elif damage == "invalid-raw":
        _ = paths["raw"].write_text("not SQLite")
    elif damage == "invalid-sqlite":
        _ = paths["raw"].write_bytes(b"SQLite format 3\x00" + b"invalid" * 100)
    elif damage == "unreadable-raw":
        paths["raw"].chmod(0)
        if os.access(paths["raw"], os.R_OK):
            pytest.skip("this platform/user cannot enforce a read-denied fixture")
    else:
        marker_path = checkout / "coverage/evidence/start.json"
        marker = _JSON.validate_json(marker_path.read_bytes())
        marker["tested_sha"] = "b" * 40
        _ = marker_path.write_bytes(_JSON.dump_json(marker))
    # When: the workflow exporter validates the completed result.
    result = _run(checkout, "export", "--outcome", "success")
    # Then: stale/broken evidence is never uploaded as current-run measurement.
    assert result.returncode != 0
    evidence = checkout / "coverage/evidence"
    metadata = _JSON.validate_json((evidence / "provenance.json").read_bytes())
    assert metadata["availability"] == "unavailable"
    assert not (evidence / ".coverage").exists()
    assert not (evidence / "coverage.json").exists()
    assert "unavailable" in (checkout / "summary.md").read_text()


@pytest.mark.parametrize("event", ["push", "workflow_dispatch"])
def test_non_pr_export_has_no_fabricated_pr_head(
    checkout: Path, monkeypatch: pytest.MonkeyPatch, event: str
) -> None:
    # Given: a real checkout prepared for a push/manual event, including dirty QA.
    monkeypatch.setenv("EVIDENCE_TEST_EVENT", event)
    monkeypatch.setenv("EVIDENCE_TEST_REF", "refs/heads/trunk")
    monkeypatch.setenv("EVIDENCE_TEST_HEAD", "")
    assert _run(checkout, "prepare").returncode == 0
    _reports(checkout)
    # When: the actual exporter records this invocation.
    result = _run(checkout, "export", "--outcome", "success")
    # Then: tested revision comes from git and absent PR context stays absent.
    assert result.returncode == 0, result.stderr
    metadata = _JSON.validate_json(
        (checkout / "coverage/evidence/provenance.json").read_bytes()
    )
    assert metadata["event"] == event
    assert metadata["pr_head_sha"] is None
    assert metadata["ref"] == "refs/heads/trunk"


def test_prepare_rejects_event_revision_mismatch(
    checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: the event claims a revision different from actual git HEAD.
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    # When: the same command used before the workflow gate prepares provenance.
    result = _run(checkout, "prepare")
    # Then: measurement cannot run with a mislabeled immutable checkout.
    assert result.returncode != 0


def test_export_without_reports_writes_unavailable_summary(checkout: Path) -> None:
    # Given: preparation succeeded but collection produced no report files.
    # When: always-run export receives the actual failed step outcome.
    result = _run(checkout, "export", "--outcome", "failure")
    # Then: absence is explicit diagnostic evidence, never a successful result.
    assert result.returncode != 0
    metadata = _JSON.validate_json(
        (checkout / "coverage/evidence/provenance.json").read_bytes()
    )
    assert metadata["totals"] is None
    assert metadata["availability"] == "unavailable"
    assert "Measurement unavailable" in (checkout / "summary.md").read_text()


def test_staging_does_not_copy_hidden_html_files(checkout: Path) -> None:
    # Given: a report directory contains unrelated hidden data.
    _reports(checkout)
    _ = (checkout / "coverage/html/.env").write_text("not coverage evidence")
    # When: reports are staged for the explicitly hidden-enabled artifact action.
    result = _run(checkout, "export", "--outcome", "success")
    # Then: only the selected raw hidden file is published, not hidden HTML data.
    assert result.returncode == 0, result.stderr
    assert not (checkout / "coverage/evidence/html/.env").exists()


def test_invalidated_retry_removes_previously_staged_reports(checkout: Path) -> None:
    # Given: an earlier export staged valid reports, which are now invalidated.
    _reports(checkout)
    assert _run(checkout, "export", "--outcome", "success").returncode == 0
    (checkout / "coverage/coverage.json").unlink()
    # When: export is retried after the reports become unavailable.
    result = _run(checkout, "export", "--outcome", "failure")
    # Then: old staged reports cannot accompany unavailable provenance.
    assert result.returncode != 0
    assert not (checkout / "coverage/evidence/.coverage").exists()
    assert not (checkout / "coverage/evidence/html").exists()


def test_multiline_source_report_uses_analyzed_not_raw_trace_lines(
    checkout: Path,
) -> None:
    # Given: real coverage normalizes multiline execution into report line numbers.
    _reports(
        checkout,
        """\"\"\"Sample module.\"\"\"
def compute(
    value: int,
) -> int:
    return (
        value
        + 1
    )
compute(1)
""",
    )
    # When: fresh JSON and readable raw branch data are exported together.
    result = _run(checkout, "export", "--outcome", "success")
    # Then: valid analyzed reports are not rejected for raw tracing differences.
    assert result.returncode == 0, result.stdout + result.stderr
