from datetime import UTC, datetime, timedelta
from typing import assert_never

import pytest

from perfcheck.bootstrap import BaselineReferenceResult, CohortBootstrapResult
from perfcheck.collection_models import SourceInterval
from perfcheck.comparison_models import ComparisonCohorts
from perfcheck.model_types import (
    ComparisonMethod,
    ComparisonMode,
    Direction,
    MetricAvailability,
    MetricId,
    MetricUnit,
    Statistic,
    Status,
)
from perfcheck.policy import comparison_fingerprint
from perfcheck.policy_models import MetricPolicy, SuitePolicy
from perfcheck.regression import evaluate_regression
from perfcheck.regression_metrics import evaluate_metric
from perfcheck.regression_models import MetricEvaluationInput
from perfcheck.summary_models import (
    EligibilityResult,
    MetricSummary,
    SummaryArtifact,
    SummaryMetricRecord,
)

_BASE = datetime(2026, 1, 1, tzinfo=UTC)
_POLICY_SHA256 = "a" * 64


def _policy(
    direction: Direction, comparison_mode: ComparisonMode = ComparisonMode.AUTO
) -> SuitePolicy:
    return SuitePolicy(
        policy_id="policy-1",
        suite_id="suite-1",
        policy_sha256=_POLICY_SHA256,
        metrics=(
            MetricPolicy(
                metric_id=MetricId("latency"),
                query="latency_seconds",
                unit=MetricUnit.SECONDS,
                direction=direction,
                statistic=Statistic.P99,
                practical_threshold=5.0,
                step_seconds=15,
                rate_window_seconds=60,
            ),
        ),
        comparison_mode=comparison_mode,
    )


def _summary(policy: SuitePolicy, *, index: int, value: float) -> SummaryArtifact:
    metric = policy.metrics[0]
    start = _BASE + timedelta(hours=index * 2)
    end = start + timedelta(minutes=10)
    eligibility = EligibilityResult(
        eligible=True,
        reason=None,
        analysis_start=start,
        analysis_end=end,
        retained_points=21,
        expected_points=41,
        coverage=0.8,
    )
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
                    point_count=21,
                    compatibility_fingerprint=comparison_fingerprint(policy, metric),
                    eligibility=eligibility,
                ),
            ),
        ),
    )


def _reference_cohorts(
    policy: SuitePolicy, *, current_value: float, baseline_value: float
) -> ComparisonCohorts:
    return _cohorts(policy, (current_value,), (baseline_value,) * 10)


def _cohorts(
    policy: SuitePolicy,
    current_values: tuple[float, ...],
    baseline_values: tuple[float, ...],
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


@pytest.mark.parametrize(
    ("direction", "current_value", "baseline_value"),
    [
        (Direction.HIGHER_IS_WORSE, 16.0, 10.0),
        (Direction.LOWER_IS_WORSE, 14.0, 20.0),
    ],
)
def test_evaluate_regression_keeps_directional_reference_anomalies_inconclusive(
    direction: Direction, current_value: float, baseline_value: float
) -> None:
    # Given: a one-current advisory reference effect strictly beyond the threshold.
    policy = _policy(direction)
    cohorts = _reference_cohorts(
        policy, current_value=current_value, baseline_value=baseline_value
    )

    # When: the policy evaluator maps the reference evidence to a verdict.
    outcome = evaluate_regression(policy, cohorts)

    # Then: reference anomalies remain advisory and never create a suite failure.
    assert outcome.status is Status.INCONCLUSIVE
    metric_outcome = outcome.metrics[0]
    assert metric_outcome.status is Status.INCONCLUSIVE
    match metric_outcome.evidence:
        case BaselineReferenceResult(reference_anomaly=True):
            pass
        case BaselineReferenceResult():
            pytest.fail("expected an advisory anomaly")
        case CohortBootstrapResult() | None:
            pytest.fail("expected baseline-reference evidence")
        case _:
            assert_never(metric_outcome.evidence)


@pytest.mark.parametrize(
    ("direction", "current_value", "baseline_value"),
    [
        (Direction.HIGHER_IS_WORSE, 15.0, 10.0),
        (Direction.LOWER_IS_WORSE, 15.0, 20.0),
    ],
)
def test_evaluate_regression_treats_reference_threshold_equality_as_advisory(
    direction: Direction, current_value: float, baseline_value: float
) -> None:
    # Given: one advisory reference effect exactly equal to the threshold.
    policy = _policy(direction)
    cohorts = _reference_cohorts(
        policy, current_value=current_value, baseline_value=baseline_value
    )

    # When: the policy evaluator applies its practical threshold rule.
    outcome = evaluate_regression(policy, cohorts)

    # Then: equality records no anomaly and remains inconclusive.
    assert outcome.status is Status.INCONCLUSIVE
    match outcome.metrics[0].evidence:
        case BaselineReferenceResult(reference_anomaly=False):
            pass
        case BaselineReferenceResult():
            pytest.fail("expected no advisory anomaly at the threshold")
        case CohortBootstrapResult() | None:
            pytest.fail("expected baseline-reference evidence")
        case _:
            assert_never(outcome.metrics[0].evidence)


@pytest.mark.parametrize(
    ("direction", "current_value", "baseline_value", "expected_status"),
    [
        (Direction.HIGHER_IS_WORSE, 16.0, 10.0, Status.FAIL),
        (Direction.HIGHER_IS_WORSE, 15.0, 10.0, Status.PASS),
        (Direction.LOWER_IS_WORSE, 14.0, 20.0, Status.FAIL),
        (Direction.LOWER_IS_WORSE, 15.0, 20.0, Status.PASS),
    ],
)
def test_evaluate_regression_uses_a_strict_directional_cohort_bound(
    direction: Direction,
    current_value: float,
    baseline_value: float,
    expected_status: Status,
) -> None:
    # Given: a qualifying constant cohort with a lower bound at or beyond threshold.
    policy = _policy(direction)
    cohorts = _cohorts(policy, (current_value,) * 5, (baseline_value,) * 10)

    # When: automatic selection evaluates the cohort bootstrap evidence.
    outcome = evaluate_regression(policy, cohorts)

    # Then: only an oriented bound strictly greater than threshold fails.
    assert outcome.status is expected_status
    assert outcome.metrics[0].method is ComparisonMethod.COHORT_BOOTSTRAP


def test_evaluate_regression_keeps_invalid_explicit_reference_mode_inconclusive() -> (
    None
):
    # Given: explicit reference mode with two current runs instead of exactly one.
    policy = _policy(Direction.HIGHER_IS_WORSE, ComparisonMode.BASELINE_REFERENCE)
    cohorts = _cohorts(policy, (16.0, 16.0), (10.0,) * 10)

    # When: the evaluator delegates selection to the policy contract.
    outcome = evaluate_regression(policy, cohorts)

    # Then: it retains the stable selection reason without inventing evidence.
    assert outcome.status is Status.INCONCLUSIVE
    assert outcome.metrics[0].method is None
    assert outcome.metrics[0].reason == "baseline_reference_requires_one_current_run"


def test_evaluate_metric_keeps_reference_anomalies_advisory() -> None:
    # Given: one current result with a reference anomaly beyond the threshold.
    policy = _policy(Direction.HIGHER_IS_WORSE)
    cohorts = _reference_cohorts(policy, current_value=16.0, baseline_value=10.0)
    evaluation = MetricEvaluationInput(policy, policy.metrics[0], None)

    # When: the per-metric evaluator applies the selected reference method.
    outcome = evaluate_metric(evaluation, cohorts)

    # Then: the anomaly remains explicit evidence but cannot become a failure.
    assert outcome.status is Status.INCONCLUSIVE
    assert outcome.method is ComparisonMethod.BASELINE_REFERENCE
    match outcome.evidence:
        case BaselineReferenceResult(reference_anomaly=True):
            pass
        case BaselineReferenceResult():
            pytest.fail("expected an advisory anomaly")
        case CohortBootstrapResult() | None:
            pytest.fail("expected baseline-reference evidence")
        case _:
            assert_never(outcome.evidence)
