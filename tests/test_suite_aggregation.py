from datetime import UTC, datetime, timedelta

import pytest

from perfcheck.bootstrap import BaselineReferenceResult, CohortBootstrapResult
from perfcheck.collection_models import SourceInterval
from perfcheck.comparison_models import ComparisonCohorts
from perfcheck.model_types import (
    Direction,
    EligibilityReason,
    MetricAvailability,
    MetricUnit,
    Statistic,
    Status,
)
from perfcheck.policy import comparison_fingerprint
from perfcheck.policy_models import MetricPolicy, SuitePolicy
from perfcheck.regression import evaluate_regression
from perfcheck.summary_models import (
    EligibilityResult,
    MetricSummary,
    SummaryArtifact,
    SummaryMetricRecord,
)

_BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _metric(metric_id: str, *, enabled: bool = True) -> MetricPolicy:
    return MetricPolicy(
        metric_id=metric_id,
        query=f"{metric_id}_seconds",
        unit=MetricUnit.SECONDS,
        direction=Direction.HIGHER_IS_WORSE,
        statistic=Statistic.P99,
        practical_threshold=5.0,
        step_seconds=15,
        rate_window_seconds=60,
        enabled=enabled,
    )


def _policy(metrics: tuple[MetricPolicy, ...]) -> SuitePolicy:
    return SuitePolicy(
        policy_id="policy-1",
        suite_id="suite-1",
        policy_sha256="a" * 64,
        metrics=metrics,
    )


def _summary(
    policy: SuitePolicy, *, index: int, values: tuple[float | None, ...]
) -> SummaryArtifact:
    start = _BASE + timedelta(hours=index * 2)
    end = start + timedelta(minutes=10)
    return SummaryArtifact(
        content_sha256=f"{index:064x}",
        summary_id=f"summary-{index}",
        source_run_id=f"run-{index}",
        source_content_sha256=f"{index + 100:064x}",
        source_interval=SourceInterval(start=start, end=end),
        policy_sha256=policy.policy_sha256,
        policy_snapshot=policy,
        metric_records=tuple(
            SummaryMetricRecord(
                metric_id=metric.metric_id,
                availability=MetricAvailability.AVAILABLE,
                summary=MetricSummary(
                    statistic=metric.statistic,
                    value=value,
                    point_count=21 if value is not None else 0,
                    compatibility_fingerprint=comparison_fingerprint(policy, metric),
                    eligibility=EligibilityResult(
                        eligible=value is not None,
                        reason=(
                            None
                            if value is not None
                            else EligibilityReason.INSUFFICIENT_POINTS
                        ),
                        analysis_start=start,
                        analysis_end=end,
                        retained_points=21 if value is not None else 0,
                        expected_points=41,
                        coverage=0.8 if value is not None else 0.0,
                    ),
                ),
            )
            for metric, value in zip(policy.metrics, values, strict=True)
        ),
    )


def _cohorts(
    policy: SuitePolicy,
    current_values: tuple[tuple[float | None, ...], ...],
    baseline_values: tuple[tuple[float | None, ...], ...],
) -> ComparisonCohorts:
    return ComparisonCohorts(
        current=tuple(
            _summary(policy, index=index, values=values)
            for index, values in enumerate(current_values, start=1)
        ),
        baseline=tuple(
            _summary(policy, index=index, values=values)
            for index, values in enumerate(baseline_values, start=10)
        ),
    )


def test_evaluate_regression_fails_a_suite_when_any_enabled_metric_fails() -> None:
    # Given: two enabled gates with a deterministic fail and pass cohort result.
    policy = _policy((_metric("latency"), _metric("memory")))
    cohorts = _cohorts(policy, ((16.0, 14.0),) * 5, ((10.0, 10.0),) * 10)

    # When: both metrics use the policy's cohort bootstrap mode.
    outcome = evaluate_regression(policy, cohorts)

    # Then: family alpha is fixed at 0.05 / 2 and any failure fails the suite.
    assert outcome.status is Status.FAIL
    assert tuple(metric.status for metric in outcome.metrics) == (
        Status.FAIL,
        Status.PASS,
    )
    match outcome.metrics[0].evidence:
        case CohortBootstrapResult(effective_alpha=0.025):
            pass
        case CohortBootstrapResult():
            pytest.fail("expected Bonferroni-adjusted alpha")
        case BaselineReferenceResult() | None:
            pytest.fail("expected cohort-bootstrap evidence")


def test_evaluate_regression_returns_inconclusive_when_no_enabled_metric_fails() -> (
    None
):
    # Given: one passing gate and one one-current advisory reference gate.
    policy = _policy((_metric("latency"), _metric("memory")))
    cohorts = _cohorts(
        policy,
        ((14.0, 16.0), (14.0, None), (14.0, None), (14.0, None), (14.0, None)),
        ((10.0, 10.0),) * 10,
    )

    # When: each metric filters its own eligible evidence before selection.
    outcome = evaluate_regression(policy, cohorts)

    # Then: the advisory metric prevents a PASS but cannot create a FAIL.
    assert outcome.status is Status.INCONCLUSIVE
    assert tuple(metric.status for metric in outcome.metrics) == (
        Status.PASS,
        Status.INCONCLUSIVE,
    )


def test_evaluate_regression_excludes_disabled_metrics_from_alpha_and_aggregation() -> (
    None
):
    # Given: one passing enabled gate and one disabled metric with adverse values.
    policy = _policy((_metric("latency"), _metric("memory", enabled=False)))
    cohorts = _cohorts(policy, ((14.0, 100.0),) * 5, ((10.0, 10.0),) * 10)

    # When: the suite policy evaluates all declared metric memberships.
    outcome = evaluate_regression(policy, cohorts)

    # Then: only the enabled metric sets alpha and the suite verdict.
    assert outcome.status is Status.PASS
    assert outcome.metrics[1].enabled is False
    assert outcome.metrics[1].status is Status.INCONCLUSIVE
    match outcome.metrics[0].evidence:
        case CohortBootstrapResult(effective_alpha=0.05):
            pass
        case CohortBootstrapResult():
            pytest.fail("expected single-gate alpha")
        case BaselineReferenceResult() | None:
            pytest.fail("expected cohort-bootstrap evidence")
