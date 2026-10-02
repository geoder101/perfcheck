from datetime import UTC, datetime, timedelta

import pytest

from perfcheck.bootstrap import BaselineReferenceResult, CohortBootstrapResult
from perfcheck.collection_models import CollectionFailure, SourceInterval
from perfcheck.comparison_models import ComparisonCohorts
from perfcheck.model_types import (
    CollectionFailureReason,
    Direction,
    EligibilityReason,
    MetricAvailability,
    MetricUnit,
    Statistic,
    Status,
)
from perfcheck.policy import comparison_fingerprint
from perfcheck.policy_models import MetricPolicy, SuitePolicy
from perfcheck.regression import Cohort, MetricExclusion, evaluate_regression
from perfcheck.summary_models import (
    EligibilityResult,
    MetricSummary,
    SummaryArtifact,
    SummaryMetricRecord,
)

_BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _policy(*, min_current_runs: int = 5, min_baseline_runs: int = 10) -> SuitePolicy:
    return SuitePolicy(
        policy_id="policy-1",
        suite_id="suite-1",
        policy_sha256="a" * 64,
        metrics=(
            MetricPolicy(
                metric_id="latency",
                query="latency_seconds",
                unit=MetricUnit.SECONDS,
                direction=Direction.HIGHER_IS_WORSE,
                statistic=Statistic.P99,
                practical_threshold=5.0,
                step_seconds=15,
                rate_window_seconds=60,
            ),
        ),
        min_current_runs=min_current_runs,
        min_baseline_runs=min_baseline_runs,
    )


def _summary(
    policy: SuitePolicy, *, index: int, value: float | None
) -> SummaryArtifact:
    metric = policy.metrics[0]
    start = _BASE + timedelta(hours=index * 2)
    end = start + timedelta(minutes=10)
    eligible = value is not None
    return SummaryArtifact(
        content_sha256=f"{index:064x}",
        summary_id=f"summary-{index}",
        source_run_id=f"run-{index}",
        source_content_sha256=f"{index + 100:064x}",
        source_interval=SourceInterval(start=start, end=end),
        policy_sha256=policy.policy_sha256,
        policy_snapshot=policy,
        metric_records=(
            SummaryMetricRecord(
                metric_id=metric.metric_id,
                availability=MetricAvailability.AVAILABLE,
                summary=MetricSummary(
                    statistic=metric.statistic,
                    value=value,
                    point_count=21 if eligible else 0,
                    compatibility_fingerprint=comparison_fingerprint(policy, metric),
                    eligibility=EligibilityResult(
                        eligible=eligible,
                        reason=(
                            None if eligible else EligibilityReason.INSUFFICIENT_POINTS
                        ),
                        analysis_start=start,
                        analysis_end=end,
                        retained_points=21 if eligible else 0,
                        expected_points=41,
                        coverage=0.8 if eligible else 0.0,
                    ),
                ),
            ),
        ),
    )


def _cohorts(
    policy: SuitePolicy,
    current_values: tuple[float | None, ...],
    baseline_values: tuple[float | None, ...],
) -> ComparisonCohorts:
    return ComparisonCohorts(
        current=tuple(
            _summary(policy, index=index, value=value)
            for index, value in enumerate(current_values, start=1)
        ),
        baseline=tuple(
            _summary(policy, index=index, value=value)
            for index, value in enumerate(baseline_values, start=10)
        ),
    )


def test_evaluate_regression_filters_ineligible_runs_before_default_count_gate() -> (
    None
):
    # Given: five supplied current runs, one of which has no eligible scalar.
    policy = _policy()
    cohorts = _cohorts(policy, (16.0, 16.0, 16.0, 16.0, None), (10.0,) * 10)

    # When: the evaluator filters values before it asks policy to select a method.
    outcome = evaluate_regression(policy, cohorts)

    # Then: the four eligible runs are insufficient and retain their exclusion reason.
    metric = outcome.metrics[0]
    assert outcome.status is Status.INCONCLUSIVE
    assert metric.reason == "insufficient_current_runs"
    assert metric.exclusions == (
        MetricExclusion(
            cohort=Cohort.CURRENT,
            source_run_id="run-5",
            reason="insufficient_points",
        ),
    )


def test_evaluate_regression_preserves_unavailable_exclusions() -> None:
    # Given: a default-size comparison where one baseline metric is unavailable.
    policy = _policy()
    cohorts = _cohorts(policy, (16.0,) * 5, (10.0,) * 10)
    unavailable = cohorts.baseline[-1].model_copy(
        update={
            "metric_records": (
                SummaryMetricRecord(
                    metric_id="latency",
                    availability=MetricAvailability.UNAVAILABLE,
                    failure=CollectionFailure(
                        reason=CollectionFailureReason.TIMEOUT,
                        detail="query timed out",
                    ),
                ),
            )
        }
    )
    incomplete_cohorts = ComparisonCohorts(
        current=cohorts.current,
        baseline=(*cohorts.baseline[:-1], unavailable),
    )

    # When: the unavailable baseline artifact is excluded before selection.
    outcome = evaluate_regression(policy, incomplete_cohorts)

    # Then: the policy sees only nine baseline values and records the timeout.
    metric = outcome.metrics[0]
    assert metric.reason == "insufficient_baseline_runs"
    assert metric.exclusions == (
        MetricExclusion(
            cohort=Cohort.BASELINE,
            source_run_id="run-19",
            reason="timeout",
        ),
    )


def test_evaluate_regression_marks_reduced_cohort_minima_as_a_warning() -> None:
    # Given: a policy that explicitly permits a two-by-two bootstrap cohort.
    policy = _policy(min_current_runs=2, min_baseline_runs=2)
    cohorts = _cohorts(policy, (16.0, 16.0), (10.0, 10.0))

    # When: automatic selection uses the reduced cohort minima.
    outcome = evaluate_regression(policy, cohorts)

    # Then: the bootstrap evidence retains a sample-size warning with its verdict.
    assert outcome.status is Status.FAIL
    match outcome.metrics[0].evidence:
        case CohortBootstrapResult(sample_size_warning=True):
            pass
        case CohortBootstrapResult():
            pytest.fail("expected reduced-minimum warning")
        case BaselineReferenceResult() | None:
            pytest.fail("expected cohort-bootstrap evidence")
