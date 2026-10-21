from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from examples._support import (
    mock_prometheus_endpoint,
    perfcheck_executable,
    run_local_command,
)

from tests.examples_check import run_standalone_notebook

if TYPE_CHECKING:
    import pytest

_ROOT = Path(__file__).parents[1]
_FIXTURE = _ROOT / "examples/fixtures/prometheus-matrix.json"
_PASS_POLICY = _ROOT / "tests/fixtures/policy-pass.json"


def test_tampered_raw_artifact_is_rejected_before_summary_is_written(
    tmp_path: Path,
) -> None:
    # Given: a raw run created through the public collect command and then altered.
    raw_path = tmp_path / "raw.json"
    summary_path = tmp_path / "summary.json"
    with mock_prometheus_endpoint(_FIXTURE) as endpoint:
        collect = run_local_command(
            (
                str(perfcheck_executable()),
                "collect",
                "--suite",
                str(_PASS_POLICY),
                "--prometheus-url",
                endpoint,
                "--run-id",
                "lesson-tampered",
                "--start",
                "2026-07-01T10:00:00Z",
                "--end",
                "2026-07-01T10:10:00Z",
                "--out",
                str(raw_path),
            ),
            cwd=tmp_path,
        )
    _ = raw_path.write_bytes(
        raw_path.read_bytes().replace(
            b'"run_id":"lesson-tampered"', b'"run_id":"tampered-run"', 1
        )
    )

    # When: summarize receives the tampered raw artifact through the public CLI.
    summarize = run_local_command(
        (
            str(perfcheck_executable()),
            "summarize",
            "--policy",
            str(_PASS_POLICY),
            "--run",
            str(raw_path),
            "--out",
            str(summary_path),
        ),
        cwd=tmp_path,
    )

    # Then: the generic input error is returned and no summary is persisted.
    assert collect.returncode == 0
    assert summarize.returncode == 3
    assert "error: invalid command input" in summarize.stderr
    assert not summary_path.exists()


def test_comparison_lesson_reports_known_pass_with_both_temporary_formats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the standalone comparison lesson and an unsafe parent credential.
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", "fake-bearer-token")
    lesson_path = _ROOT / "examples/04-compare.py"

    # When: the lesson collects, summarizes, and compares its local fixture cohorts.
    result = run_standalone_notebook(lesson_path)

    # Then: both temporary report formats describe the known passing decision safely.
    assert result.returncode == 0, result.stderr
    assert '"suite_status": "pass"' in result.stdout
    assert "JSON report (temporary)" in result.stdout
    assert "Markdown report (temporary)" in result.stdout
    assert "fake-bearer-token" not in result.stdout
    assert "fake-bearer-token" not in result.stderr


def test_failures_lesson_handles_existing_report_preflight_without_secret_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the standalone failure lesson and a parent-only credential.
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", "fake-bearer-token")
    lesson_path = _ROOT / "examples/05-failures-and-ci.py"

    # When: the lesson catches its documented report-output preflight failure.
    result = run_standalone_notebook(lesson_path)

    # Then: it preserves the exact CLI outcome while the notebook itself succeeds.
    assert result.returncode == 0, result.stderr
    assert (
        "Handled failure: exit status 3 — error: invalid command input" in result.stdout
    )
    assert "fake-bearer-token" not in result.stdout
    assert "fake-bearer-token" not in result.stderr
