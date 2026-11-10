import pytest

from perfcheck.bootstrap import CohortBootstrapOptions
from perfcheck.comparison_models import ComparisonCohorts
from perfcheck.model_types import ComparisonMode, Direction
from perfcheck.policy import comparison_fingerprint
from perfcheck.policy_models import MetricPolicy, SuitePolicy
from perfcheck.regression import evaluate_regression
from perfcheck.report import (
    Report,
    build_report,
    render_json_report,
    render_markdown_report,
)
from perfcheck.storage import artifact_content_sha256, policy_content_sha256
from tests.comparison_boundary_support import (
    boundary_metric,
    boundary_policy,
    boundary_summary,
)


@pytest.fixture
def mixed_report(
    adverse: float,
) -> tuple[SuitePolicy, ComparisonCohorts, Report]:
    lower = MetricPolicy.model_validate(
        boundary_metric("z_lower").model_dump()
        | {"direction": Direction.LOWER_IS_WORSE}
    )
    policy = boundary_policy(
        (
            boundary_metric("pending"),
            lower,
            boundary_metric("a_pass"),
            boundary_metric("disabled", enabled=False),
        )
    )
    cohorts = ComparisonCohorts(
        current=tuple(
            boundary_summary(policy, n, (None, adverse, 12.0 if n < 5 else None, 100.0))
            for n in range(1, 6)
        ),
        baseline=tuple(
            boundary_summary(policy, n, (7.0, 20.0, 10.0 if n < 19 else None, 1.0))
            for n in range(10, 20)
        ),
    )
    outcome = evaluate_regression(
        policy, cohorts, CohortBootstrapOptions(seed=17, requested_resamples=100)
    )
    assert outcome.metrics[0].status == "inconclusive"
    assert outcome.status == ("fail" if adverse == 14.0 else "inconclusive")
    return policy, cohorts, build_report(policy, cohorts, outcome)


@pytest.mark.parametrize("metric_id", ["a_pass", "disabled", "pending", "z_lower"])
@pytest.mark.parametrize("adverse", [14.0, 18.0], ids=["later-fail", "no-fail"])
def test_each_report_metric_retains_its_own_evidence(
    mixed_report: tuple[SuitePolicy, ComparisonCohorts, Report], metric_id: str
) -> None:
    # Given: independent metric values, directions, eligibility, and enabled states.
    policy, cohorts, report = mixed_report
    expected_current: dict[str, tuple[float, ...]] = {
        "a_pass": (12.0,) * 4,
        "disabled": (100.0,) * 5,
        "pending": (),
        "z_lower": tuple(
            record.summary.value
            for summary in cohorts.current
            for record in summary.metric_records
            if record.metric_id == "z_lower"
            and record.summary is not None
            and record.summary.value is not None
        ),
    }
    expected_baseline = {
        "a_pass": (10.0,) * 9,
        "disabled": (1.0,) * 10,
        "pending": (7.0,) * 10,
        "z_lower": (20.0,) * 10,
    }

    # When: the actual JSON renderer exports the assembled evaluation.
    parsed = Report.model_validate_json(render_json_report(report))

    # Then: no neighboring metric's evidence or policy interpretation leaks in.
    metric = next(item for item in parsed.metrics if item.metric_id == metric_id)
    configured = next(item for item in policy.metrics if item.metric_id == metric_id)
    assert (
        tuple(sample.value for sample in metric.current.values)
        == expected_current[metric_id]
    )
    assert (
        tuple(sample.value for sample in metric.baseline.values)
        == expected_baseline[metric_id]
    )
    assert metric.current.count == len(expected_current[metric_id])
    assert metric.baseline.count == len(expected_baseline[metric_id])
    assert metric.comparison_fingerprint == comparison_fingerprint(policy, configured)
    assert metric.direction == configured.direction
    assert metric.statistic == "mean"
    assert metric.unit == "seconds"
    assert metric.practical_threshold == 5.0
    assert metric.enabled is configured.enabled
    expected_effect = {
        "a_pass": 2.0,
        "disabled": None,
        "pending": None,
        "z_lower": 20.0 - expected_current["z_lower"][0],
    }
    assert metric.effect == expected_effect[metric_id]
    statuses = {
        "a_pass": "pass",
        "disabled": "inconclusive",
        "pending": "inconclusive",
        "z_lower": report.suite_status,
    }
    assert metric.status == (
        "pass"
        if metric_id == "z_lower" and metric.effect == 2.0
        else statuses[metric_id]
    )
    reasons = {
        "a_pass": None,
        "disabled": "metric_disabled",
        "pending": "insufficient_current_runs",
        "z_lower": None,
    }
    assert metric.reason == reasons[metric_id]


@pytest.mark.parametrize("adverse", [14.0, 18.0], ids=["later-fail", "no-fail"])
def test_family_alpha_counts_enabled_unevaluable_but_not_disabled_metrics(
    mixed_report: tuple[SuitePolicy, ComparisonCohorts, Report],
) -> None:
    # Given: three enabled metrics, only two of which can be evaluated.
    _, _, report = mixed_report

    # When: method options and exclusions are exported to JSON.
    parsed = Report.model_validate_json(render_json_report(report))

    # Then: both decisions use the fixed three-gate family; disabled contributes none.
    metrics = {str(metric.metric_id): metric for metric in parsed.metrics}
    for name in ("a_pass", "z_lower"):
        metric = metrics[name]
        assert metric.method == "cohort_bootstrap"
        assert metric.options.requested_alpha == 0.05
        assert metric.options.effective_alpha == pytest.approx(0.05 / 3)
        assert metric.decision_lower_bound == metric.effect
        assert metric.diagnostic_lower_bound == metric.effect
        assert metric.diagnostic_upper_bound == metric.effect
        assert metric.options.effective_seed == 17
        assert metric.options.requested_resamples == 100
        assert metric.options.effective_resamples == 6000
        assert metric.sample_size_warning is (name == "a_pass")
    for name in ("pending", "disabled"):
        assert metrics[name].method is None
        assert metrics[name].options.effective_alpha is None
        assert metrics[name].options.effective_resamples is None
        assert metrics[name].sample_size_warning is False
    assert [
        (x.cohort, x.source_run_id, x.reason) for x in metrics["a_pass"].exclusions
    ] == [("current", "run-05", "timeout"), ("baseline", "run-19", "timeout")]
    assert [
        (x.cohort, x.source_run_id, x.reason) for x in metrics["pending"].exclusions
    ] == [("current", f"run-{n:02}", "timeout") for n in range(1, 6)]
    assert metrics["disabled"].exclusions == metrics["z_lower"].exclusions == ()


@pytest.mark.parametrize("adverse", [14.0, 18.0], ids=["later-fail", "no-fail"])
def test_markdown_and_json_agree_on_each_metric_and_exclusion(
    mixed_report: tuple[SuitePolicy, ComparisonCohorts, Report],
) -> None:
    # Given: a real evaluated mixed-status report, not manufactured outcomes.
    policy, cohorts, report = mixed_report

    # When: both supported documents are rendered.
    parsed = Report.model_validate_json(render_json_report(report))
    markdown = render_markdown_report(report)

    # Then: each Markdown row conveys the JSON verdict, values, bounds and reason.
    assert f"Suite status: {parsed.suite_status}\n" in markdown
    assert [metric.metric_id for metric in parsed.metrics] == [
        "a_pass",
        "disabled",
        "pending",
        "z_lower",
    ]
    for metric in parsed.metrics:
        row = next(
            line
            for line in markdown.splitlines()
            if line.startswith(f"| {metric.metric_id} | mean |")
        )
        cells = row.split(" | ")
        assert cells[2] == metric.status
        for column, cohort in zip(
            cells[3:5], (metric.current, metric.baseline), strict=True
        ):
            values = ", ".join(f"{sample.value:+.6f}" for sample in cohort.values)
            assert column == f"{cohort.count}: [{values}]"
        assert cells[5] == ("-" if metric.effect is None else f"{metric.effect:+.6f}")
        assert cells[6] == (
            "-"
            if metric.diagnostic_lower_bound is None
            else (
                f"{metric.diagnostic_lower_bound:+.6f} "
                f"to {metric.diagnostic_upper_bound:+.6f}"
            )
        )
        assert cells[7] == f"{metric.practical_threshold:+.6f}"
        assert cells[8] == str(metric.sample_size_warning)
        assert cells[9] == metric.comparison_fingerprint
        assert cells[10] == (metric.reason or "-") + " |"
        for exclusion in metric.exclusions:
            assert (
                f"| {metric.metric_id} | {exclusion.cohort} | "
                f"{exclusion.source_run_id} | {exclusion.reason} |"
            ) in markdown
    assert parsed.provenance.policy_sha256 == policy_content_sha256(policy)
    for summary in cohorts.current + cohorts.baseline:
        assert summary.content_sha256 == artifact_content_sha256(summary)
    assert f"| Policy SHA-256 | {policy.policy_sha256} |" in markdown


def test_reference_reports_keep_directional_anomalies_advisory() -> None:
    # Given: two reference metrics with opposite directions and distinct effects.
    lower = MetricPolicy.model_validate(
        boundary_metric("lower").model_dump() | {"direction": Direction.LOWER_IS_WORSE}
    )
    policy = boundary_policy(
        (boundary_metric("higher"), lower), ComparisonMode.BASELINE_REFERENCE
    )
    cohorts = ComparisonCohorts(
        current=(boundary_summary(policy, 1, (16.0, 18.0)),),
        baseline=tuple(
            boundary_summary(policy, n, (10.0, 20.0)) for n in range(10, 20)
        ),
    )

    # When: the actual reference evaluation is built and rendered.
    report = build_report(policy, cohorts, evaluate_regression(policy, cohorts))
    parsed = Report.model_validate_json(render_json_report(report))

    # Then: the anomaly is retained without becoming a failing gate.
    assert parsed.suite_status == "inconclusive"
    assert tuple(metric.effect for metric in parsed.metrics) == (6.0, 2.0)
    assert tuple(metric.reference_anomaly for metric in parsed.metrics) == (True, False)
    assert tuple(metric.reference_quantile for metric in parsed.metrics) == (
        10.0,
        -20.0,
    )
    for metric in parsed.metrics:
        assert metric.method == "baseline_reference"
        assert metric.status == "inconclusive"
        assert (metric.current.count, metric.baseline.count) == (1, 10)
        assert metric.options.effective_alpha == 0.025
        assert metric.options.effective_seed is None
        assert metric.decision_lower_bound is None
        assert metric.diagnostic_lower_bound is None
    markdown = render_markdown_report(report)
    assert "| higher | mean | inconclusive | 1: [+16.000000]" in markdown
    assert "| lower | mean | inconclusive | 1: [+18.000000]" in markdown
    for name, effect in (("higher", "+6.000000"), ("lower", "+2.000000")):
        row = next(
            line
            for line in markdown.splitlines()
            if line.startswith(f"| {name} | mean |")
        )
        assert row.split(" | ")[5:9] == [effect, "-", "+5.000000", "True"]
