from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path  # noqa: TC003 - pytest resolves the fixture annotation.

from typer.testing import CliRunner

from perfcheck.cli import app
from perfcheck.collection_models import (
    FloatSample,
    LabelledMetricSeries,
    MetricCollectionRecord,
    QueryProvenance,
    SourceInterval,
)
from perfcheck.model_types import (
    Direction,
    MetricAvailability,
    MetricId,
    MetricUnit,
    Statistic,
)
from perfcheck.policy_models import MetricPolicy, SuitePolicy
from perfcheck.run_models import RunArtifact, RunMetadata
from perfcheck.storage import (
    artifact_content_sha256,
    policy_content_sha256,
    summary_cache_path,
    write_artifact,
)
from perfcheck.summary_models import SummaryArtifact

_BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _policy() -> SuitePolicy:
    initial = SuitePolicy(
        policy_id="policy-1",
        suite_id="suite-1",
        policy_sha256="0" * 64,
        min_baseline_reference_runs=1,
        metrics=(
            MetricPolicy(
                metric_id=MetricId("latency"),
                query="latency_seconds",
                unit=MetricUnit.SECONDS,
                direction=Direction.HIGHER_IS_WORSE,
                statistic=Statistic.MEAN,
                practical_threshold=0.0,
                step_seconds=15,
                rate_window_seconds=60,
            ),
        ),
    )
    return initial.model_copy(update={"policy_sha256": policy_content_sha256(initial)})


def _run(policy: SuitePolicy, index: int, value: float) -> RunArtifact:
    interval = SourceInterval(
        start=_BASE + timedelta(hours=index),
        end=_BASE + timedelta(hours=index, minutes=10),
    )
    initial = RunArtifact(
        content_sha256="0" * 64,
        run_id=f"run-{index}",
        suite_id=policy.suite_id,
        source_interval=interval,
        policy_sha256=policy.policy_sha256,
        policy_snapshot=policy,
        metadata=RunMetadata(
            test_name="load-test",
            git_sha="abcdef",
            environment="ci",
            scenario="baseline",
            target_topology="single-node",
        ),
        metric_records=(
            MetricCollectionRecord(
                metric_id=MetricId("latency"),
                availability=MetricAvailability.AVAILABLE,
                provenance=QueryProvenance(
                    endpoint_url="https://metrics.example.test",
                    query="latency_seconds",
                    start=interval.start,
                    end=interval.end,
                    step_seconds=15,
                ),
                series=LabelledMetricSeries(
                    metric_id=MetricId("latency"),
                    samples=tuple(
                        FloatSample(
                            timestamp=interval.start + timedelta(seconds=15 * sample),
                            value=value,
                        )
                        for sample in range(41)
                    ),
                ),
            ),
        ),
    )
    return initial.model_copy(
        update={"content_sha256": artifact_content_sha256(initial)}
    )


def _write_policy(path: Path, policy: SuitePolicy) -> None:
    _ = path.write_text(policy.model_dump_json(), encoding="utf-8")


def test_summarize_writes_canonical_summary_without_stdout(
    tmp_path: Path,
) -> None:
    # Given: verified raw evidence and its matching canonical policy.
    policy = _policy()
    policy_path = tmp_path / "policy.json"
    raw_path = tmp_path / "run.json"
    summary_path = tmp_path / "summary.json"
    _write_policy(policy_path, policy)
    write_artifact(raw_path, _run(policy, 1, 10.0))

    # When: summarize receives its explicit output path.
    result = CliRunner().invoke(
        app,
        [
            "summarize",
            "--policy",
            str(policy_path),
            "--run",
            str(raw_path),
            "--out",
            str(summary_path),
        ],
    )

    # Then: it writes a verified summary and reserves stdout for machine output.
    assert result.exit_code == 0
    assert result.stdout == ""
    payload = SummaryArtifact.model_validate_json(summary_path.read_bytes())
    assert payload.artifact_type == "summary"


def test_compare_json_writes_exactly_one_report_to_stdout(tmp_path: Path) -> None:
    # Given: two independently summarized raw runs under one policy.
    policy = _policy()
    policy_path = tmp_path / "policy.json"
    current_raw = tmp_path / "current.json"
    baseline_raw = tmp_path / "baseline.json"
    current_summary = tmp_path / "current.summary.json"
    baseline_summary = tmp_path / "baseline.summary.json"
    report_json = tmp_path / "report.json"
    report_markdown = tmp_path / "report.md"
    _write_policy(policy_path, policy)
    write_artifact(current_raw, _run(policy, 1, 11.0))
    write_artifact(baseline_raw, _run(policy, 2, 10.0))
    runner = CliRunner()
    for raw_path, summary_path in (
        (current_raw, current_summary),
        (baseline_raw, baseline_summary),
    ):
        assert (
            runner.invoke(
                app,
                [
                    "summarize",
                    "--policy",
                    str(policy_path),
                    "--run",
                    str(raw_path),
                    "--out",
                    str(summary_path),
                ],
            ).exit_code
            == 0
        )

    # When: compare is asked for machine-readable stdout.
    result = runner.invoke(
        app,
        [
            "compare",
            "--policy",
            str(policy_path),
            "--current",
            str(current_summary),
            "--baseline",
            str(baseline_summary),
            "--report-json",
            str(report_json),
            "--report-md",
            str(report_markdown),
            "--json",
        ],
    )

    # Then: stdout is one report document and the advisory outcome is inconclusive.
    assert result.exit_code == 2
    assert '"suite_status":"inconclusive"' in result.stdout
    assert report_json.read_text(encoding="utf-8") == result.stdout
    assert report_markdown.exists()


def test_compare_preflight_rejects_existing_reports_without_mutation(
    tmp_path: Path,
) -> None:
    # Given: explicit report destinations that already contain user data.
    report_json = tmp_path / "report.json"
    report_markdown = tmp_path / "report.md"
    _ = report_json.write_text("keep-json", encoding="utf-8")
    _ = report_markdown.write_text("keep-markdown", encoding="utf-8")

    # When: compare is invoked without --force.
    result = CliRunner().invoke(
        app,
        [
            "compare",
            "--policy",
            str(tmp_path / "missing-policy.json"),
            "--current",
            str(tmp_path / "current.json"),
            "--baseline",
            str(tmp_path / "baseline.json"),
            "--report-json",
            str(report_json),
            "--report-md",
            str(report_markdown),
        ],
    )

    # Then: preflight wins over later input errors and leaves both files unchanged.
    assert result.exit_code == 3
    assert report_json.read_text(encoding="utf-8") == "keep-json"
    assert report_markdown.read_text(encoding="utf-8") == "keep-markdown"


def test_compare_derives_raw_summaries_without_cache_then_writes_opted_in_cache(
    tmp_path: Path,
) -> None:
    # Given: raw convenience inputs with no sibling summary caches.
    policy = _policy()
    policy_path = tmp_path / "policy.json"
    current_raw = tmp_path / "current.json"
    baseline_raw = tmp_path / "baseline.json"
    report_json = tmp_path / "report.json"
    report_markdown = tmp_path / "report.md"
    _write_policy(policy_path, policy)
    write_artifact(current_raw, _run(policy, 1, 11.0))
    write_artifact(baseline_raw, _run(policy, 2, 10.0))
    runner = CliRunner()
    arguments = [
        "compare",
        "--policy",
        str(policy_path),
        "--current",
        str(current_raw),
        "--baseline",
        str(baseline_raw),
        "--report-json",
        str(report_json),
        "--report-md",
        str(report_markdown),
    ]

    # When: compare derives summaries without the explicit cache-write option.
    first = runner.invoke(app, arguments)

    # Then: it succeeds inconclusively and does not mutate either input sibling.
    assert first.exit_code == 2
    assert not summary_cache_path(current_raw, policy.policy_sha256).exists()
    assert not summary_cache_path(baseline_raw, policy.policy_sha256).exists()

    # When: the same raw inputs opt into cache materialization and report replacement.
    second = runner.invoke(app, [*arguments, "--write-summary-cache", "--force"])

    # Then: both canonical sibling caches are atomically materialized.
    assert second.exit_code == 2
    assert summary_cache_path(current_raw, policy.policy_sha256).exists()
    assert summary_cache_path(baseline_raw, policy.policy_sha256).exists()
