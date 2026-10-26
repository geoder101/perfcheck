from __future__ import annotations

from html import escape
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from examples import _capstone_view
from examples._capstone import Scenario, run_capstone
from examples._support import (
    mock_prometheus_endpoint,
    perfcheck_executable,
    run_local_command,
)

from perfcheck.report_schemas import Report
from perfcheck.run_models import RunArtifact
from perfcheck.summary_models import SummaryArtifact
from tests.examples_check import run_standalone_notebook

if TYPE_CHECKING:
    from examples._capstone import CapstoneReceipt

_ROOT = Path(__file__).parents[1]
_FIXTURE = _ROOT / "examples/fixtures/prometheus-matrix.json"
_PASS_POLICY = _ROOT / "tests/fixtures/policy-pass.json"


@pytest.fixture(scope="module")
def capstones() -> tuple[CapstoneReceipt, ...]:
    return tuple(run_capstone(scenario) for scenario in Scenario)


@pytest.mark.parametrize("scenario", tuple(Scenario))
def test_capstone_view_keeps_full_reports_in_accessible_containers(
    capstones: tuple[CapstoneReceipt, ...], scenario: Scenario
) -> None:
    # Given: the actual selected workflow receipt, including the complete report.
    receipt = next(item for item in capstones if item.scenario is scenario)

    # When: its notebook evidence is rendered without changing the receipt.
    rendered = _capstone_view.render_capstone_evidence(receipt).text

    # Then: summaries wrap and full reports remain keyboard-accessible in bounds.
    assert 'aria-label="Capstone decision summary"' in rendered
    assert 'aria-label="Full JSON report"' in rendered
    assert 'aria-label="Full Markdown report"' in rendered
    assert rendered.count('tabindex="0"') == 2
    assert "overflow-x: auto" in rendered
    assert ".capstone-evidence table" in rendered
    assert "display: table" in rendered
    assert "overflow-wrap: anywhere" in rendered
    assert "min-width: 0" in rendered
    assert escape(receipt.report_json.decode()) in rendered
    assert "<table>" in rendered
    assert receipt.scenario.value in rendered
    assert f"Compare exit status: {receipt.comparison_status}" in rendered
    assert f"Overwrite exit status: {receipt.overwrite_status}" in rendered


@pytest.mark.parametrize("scenario", tuple(Scenario))
def test_selected_capstone_has_real_decision_and_cleaned_workspace(
    capstones: tuple[CapstoneReceipt, ...], scenario: Scenario
) -> None:
    # Given: one selected scenario, executed through the actual console script.
    capstone = next(receipt for receipt in capstones if receipt.scenario is scenario)
    expected = {
        Scenario.PASS: (0, "pass", 4, 0.0),
        Scenario.REGRESSION: (1, "fail", 4, 10.0),
        Scenario.ADVISORY_REFERENCE: (2, "inconclusive", 3, 10.0),
    }
    code, status, count, effect = expected[capstone.scenario]

    # When: its persisted report is inspected after the helper returns.
    report = Report.model_validate_json(capstone.report_json)
    metric = report.metrics[0]

    # Then: actual artifacts, not synthesized decisions, explain the CLI outcome.
    assert (capstone.comparison_status, report.suite_status) == (code, status)
    assert metric.status == status
    assert metric.effect == effect
    assert metric.direction == "higher_is_worse"
    assert (metric.statistic, metric.unit, metric.practical_threshold) == (
        "mean",
        "seconds",
        0.0,
    )
    assert (metric.baseline.count, metric.current.count) == (2, count - 2)
    assert metric.sample_size_warning
    assert metric.exclusions == ()
    assert metric.options.effective_alpha == 0.05
    assert metric.options.requested_alpha == 0.05
    assert capstone.stage_statuses == (0,) * (count * 2)
    assert len(capstone.commands) == count * 2 + 2
    assert capstone.overwrite_status == 3
    assert capstone.overwrite_context == "error: invalid command input"
    assert not capstone.workspace.exists()
    assert metric.metric_id in capstone.report_markdown
    assert f"Suite status: {status}" in capstone.report_markdown
    if count == 3:
        assert metric.method == "baseline_reference"
        assert metric.reference_anomaly is True
        assert metric.reference_quantile == 10.0
        assert metric.decision_lower_bound is None
        assert metric.options.effective_seed is None
        assert metric.options.requested_resamples is None
        assert metric.options.effective_resamples is None
        assert "--seed" not in capstone.commands[-2]
        assert "--resamples" not in capstone.commands[-2]
    else:
        assert metric.method == "cohort_bootstrap"
        assert metric.decision_lower_bound == effect
        assert metric.options.effective_seed == 20260705
        assert metric.options.requested_resamples == 1000
        assert metric.options.effective_resamples == 2000


@pytest.mark.parametrize("scenario", tuple(Scenario))
def test_capstone_sources_are_unique_eligible_and_comparable(
    capstones: tuple[CapstoneReceipt, ...], scenario: Scenario
) -> None:
    # Given: real collected raw artifacts and canonical CLI summaries.
    capstone = next(receipt for receipt in capstones if receipt.scenario is scenario)
    runs = tuple(RunArtifact.model_validate_json(p) for p in capstone.raw_artifacts)
    summaries = tuple(
        SummaryArtifact.model_validate_json(p) for p in capstone.summary_artifacts
    )

    # When: source provenance and eligibility are inspected across both cohorts.
    identities = {(run.run_id, run.content_sha256) for run in runs}

    # Then: every summary traces to a distinct nonoverlapping source under one policy.
    assert len(identities) == len(runs)
    assert len({run.run_id for run in runs}) == len(runs)
    assert len({run.content_sha256 for run in runs}) == len(runs)
    assert len({run.policy_sha256 for run in runs}) == 1
    for previous, following in pairwise(runs):
        assert previous.source_interval.end < following.source_interval.start
    for run, summary in zip(runs, summaries, strict=True):
        assert summary.source_run_id == run.run_id
        assert summary.source_content_sha256 == run.content_sha256
        assert summary.policy_sha256 == run.policy_sha256
        series = run.metric_records[0].series
        assert series is not None
        assert len(series.samples) == 41
        assert series.samples[0].timestamp == run.source_interval.start
        assert series.samples[-1].timestamp == run.source_interval.end
        selected = summary.metric_records[0].summary
        assert selected is not None
        assert selected.eligibility.eligible
        assert selected.eligibility.retained_points == 41
        assert selected.eligibility.coverage == 1.0


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
    assert "Selected scenario: pass" in result.stdout
    assert "decision_lower_bound" in result.stdout
    assert "eligible=True" in result.stdout
    assert "fake-bearer-token" not in result.stdout
    assert "fake-bearer-token" not in result.stderr
