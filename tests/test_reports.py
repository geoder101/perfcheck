from dataclasses import replace
from datetime import UTC, datetime, timedelta

from perfcheck.collection_models import SourceInterval
from perfcheck.comparison_models import ComparisonCohorts
from perfcheck.model_types import (
    Direction,
    MetricAvailability,
    MetricId,
    MetricUnit,
    Statistic,
)
from perfcheck.policy import comparison_fingerprint
from perfcheck.policy_models import MetricPolicy, SuitePolicy
from perfcheck.regression import evaluate_regression
from perfcheck.regression_models import Cohort, MetricExclusion
from perfcheck.report import (
    Report,
    build_report,
    render_json_report,
    render_markdown_report,
)
from perfcheck.summary_models import (
    EligibilityResult,
    MetricSummary,
    SummaryArtifact,
    SummaryMetricRecord,
)

_BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _policy() -> SuitePolicy:
    return SuitePolicy(
        policy_id="policy-1",
        suite_id="suite-1",
        policy_sha256="a" * 64,
        metrics=(
            MetricPolicy(
                metric_id=MetricId("zeta"),
                query="zeta_seconds",
                unit=MetricUnit.SECONDS,
                direction=Direction.HIGHER_IS_WORSE,
                statistic=Statistic.P99,
                practical_threshold=5.0,
                step_seconds=15,
                rate_window_seconds=60,
            ),
            MetricPolicy(
                metric_id=MetricId("alpha"),
                query="alpha_seconds",
                unit=MetricUnit.SECONDS,
                direction=Direction.HIGHER_IS_WORSE,
                statistic=Statistic.P99,
                practical_threshold=5.0,
                step_seconds=15,
                rate_window_seconds=60,
            ),
        ),
    )


def _summary(
    policy: SuitePolicy, *, index: int, values: tuple[float, float]
) -> SummaryArtifact:
    start = _BASE + timedelta(hours=index)
    eligibility = EligibilityResult(
        eligible=True,
        reason=None,
        analysis_start=start,
        analysis_end=start + timedelta(minutes=10),
        retained_points=21,
        expected_points=41,
        coverage=0.8,
    )
    return SummaryArtifact(
        content_sha256=f"{index:064x}",
        summary_id=f"summary-{index}",
        source_run_id=f"run-{index}",
        source_content_sha256=f"{index + 100:064x}",
        source_interval=SourceInterval(start=start, end=start + timedelta(minutes=10)),
        policy_sha256=policy.policy_sha256,
        policy_snapshot=policy,
        metric_records=tuple(
            SummaryMetricRecord(
                metric_id=metric.metric_id,
                availability=MetricAvailability.AVAILABLE,
                summary=MetricSummary(
                    statistic=metric.statistic,
                    value=value,
                    point_count=21,
                    compatibility_fingerprint=comparison_fingerprint(policy, metric),
                    eligibility=eligibility,
                ),
            )
            for metric, value in zip(policy.metrics, values, strict=True)
        ),
    )


def _inputs() -> tuple[SuitePolicy, ComparisonCohorts]:
    policy = _policy()
    return (
        policy,
        ComparisonCohorts(
            current=tuple(
                _summary(policy, index=index, values=(16.0, 14.0))
                for index in range(1, 6)
            ),
            baseline=tuple(
                _summary(policy, index=index, values=(10.0, 10.0))
                for index in range(10, 20)
            ),
        ),
    )


def test_render_json_report_is_canonical_and_lexically_orders_metrics() -> None:
    # Given: a policy declared out of lexical metric order and a deterministic result.
    policy, cohorts = _inputs()
    outcome = evaluate_regression(policy, cohorts)

    # When: the evaluated report is rendered twice as JSON.
    report = build_report(policy, cohorts, outcome)
    rendered = render_json_report(report)

    # Then: it is canonical JSON with a final LF and lexical metric order.
    assert rendered == render_json_report(report)
    assert rendered.endswith("\n")
    payload = Report.model_validate_json(rendered)
    assert [metric.metric_id for metric in payload.metrics] == ["alpha", "zeta"]
    assert payload.metrics[0].current.values[0].value == 14
    assert not hasattr(payload.provenance, "input_paths")


def test_renderers_preserve_empty_report_document_layout() -> None:
    # Given: a valid report whose metric table has no data rows.
    policy, cohorts = _inputs()
    report = build_report(
        policy, cohorts, evaluate_regression(policy, cohorts)
    ).model_copy(update={"metrics": ()})

    # When: its two public documents are rendered.
    rendered_json = render_json_report(report)
    rendered_markdown = render_markdown_report(report)

    # Then: canonical JSON and the complete review document use the stable layout.
    assert rendered_json == "".join(
        (
            '{"metrics":[],"provenance":{"algorithm_manifest":{"bootstrap":',
            '"pcg64-percentile-v1","eligibility":"trim-coverage-gap-v1","report":',
            '"canonical-json-markdown-v1","summary":"linear-quantile-v1"},',
            '"policy_id":"policy-1","policy_sha256":"',
            "a" * 64,
            '","suite_id":"suite-1"},"schema_version":1,"suite_status":"fail"}\n',
        )
    )
    metric_columns = (
        "Metric",
        "Statistic",
        "Status",
        "Current",
        "Baseline",
        "Effect",
        "CI",
        "Threshold",
        "Warning",
        "Fingerprint",
        "Reason",
    )
    metric_header = f"| {' | '.join(metric_columns)} |"
    assert rendered_markdown == "\n".join(
        (
            "# Perfcheck report",
            "",
            "Suite status: fail",
            "",
            metric_header,
            "| --- | --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- | --- |",
            "",
            "## Exclusions",
            "",
            "| Metric | Cohort | Run | Reason |",
            "| --- | --- | --- | --- |",
            "",
            "## Provenance",
            "",
            "| Field | Value |",
            "| --- | --- |",
            "| Policy ID | policy-1 |",
            "| Suite ID | suite-1 |",
            "| Policy SHA-256 | " + "a" * 64 + " |",
            "| Algorithm manifest | canonical-json-markdown-v1 |",
            "",
        )
    )


def test_render_markdown_report_escapes_cells_and_formats_signed_values() -> None:
    # Given: report evidence with punctuation and a newline in an exclusion reason.
    policy, cohorts = _inputs()
    outcome = evaluate_regression(policy, cohorts)
    altered = replace(
        outcome.metrics[0],
        exclusions=(
            MetricExclusion(
                cohort=Cohort.CURRENT,
                source_run_id="run-1",
                reason="bad|`cell\nnext",
            ),
        ),
    )
    report = build_report(
        policy,
        cohorts,
        replace(outcome, metrics=(altered, *outcome.metrics[1:])),
    )

    # When: the report is rendered as Markdown.
    rendered = render_markdown_report(report)

    # Then: all table cells are safe and every numeric presentation is signed.
    assert "bad\\|\\`cell<br>next" in rendered
    assert "+14.000000" in rendered
    assert "+5.000000" in rendered
    assert "\r" not in rendered


def test_rendered_reports_exclude_secret_bearing_policy_query() -> None:
    # Given: report inputs whose collection query contained an adversarial bearer echo.
    credential = "unsafe-bearer-value"
    policy, cohorts = _inputs()
    metric = policy.metrics[0].model_copy(
        update={"query": f'up{{authorization="{credential}"}}'}
    )
    secret_bearing_policy = policy.model_copy(
        update={"metrics": (metric, *policy.metrics[1:])}
    )
    outcome = evaluate_regression(secret_bearing_policy, cohorts)

    # When: the report model is rendered to its JSON and Markdown public formats.
    report = build_report(secret_bearing_policy, cohorts, outcome)
    rendered_json = render_json_report(report)
    rendered_markdown = render_markdown_report(report)

    # Then: renderers omit the query and cannot disclose its credential.
    assert credential not in rendered_json
    assert credential not in rendered_markdown
