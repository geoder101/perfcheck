from typing import assert_never

import pytest

from perfcheck.comparison_models import ComparisonCohorts
from perfcheck.model_types import Status
from perfcheck.regression import Cohort, MetricExclusion, evaluate_regression
from tests.comparison_boundary_support import (
    boundary_metric,
    boundary_policy,
    boundary_summary,
)


@pytest.mark.parametrize(
    ("cohort", "reason"),
    [
        (Cohort.CURRENT, "insufficient_current_runs"),
        (Cohort.BASELINE, "insufficient_baseline_runs"),
    ],
)
def test_missing_metric_excludes_its_source_from_the_affected_cohort(
    cohort: Cohort, reason: str
) -> None:
    # Given: coherent hashed summaries, one from a policy with a different metric.
    policy = boundary_policy((boundary_metric("latency"),))
    other_policy = boundary_policy((boundary_metric("throughput"),))
    missing = boundary_summary(other_policy, 20, (10.0,))
    current = tuple(boundary_summary(policy, n, (12.0,)) for n in range(1, 4))
    baseline = tuple(boundary_summary(policy, n, (10.0,)) for n in range(10, 14))
    match cohort:
        case Cohort.CURRENT:
            current = (missing, *current[1:])
        case Cohort.BASELINE:
            baseline = (missing, *baseline[1:])
        case _:
            assert_never(cohort)
    cohorts = ComparisonCohorts(current=current, baseline=baseline)

    # When: the evaluated metric is absent from one otherwise valid summary.
    outcome = evaluate_regression(policy, cohorts)

    # Then: exactly that source is excluded and the cohort minimum is unmet.
    assert outcome.status is Status.INCONCLUSIVE
    (metric,) = outcome.metrics
    assert metric.metric_id == "latency"
    assert metric.status is Status.INCONCLUSIVE
    assert metric.reason == reason
    assert metric.method is None
    assert metric.evidence is None
    assert metric.exclusions == (MetricExclusion(cohort, "run-20", "missing_metric"),)
