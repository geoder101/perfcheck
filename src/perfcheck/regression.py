"""Compatibility facade for suite regression evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from perfcheck.regression_aggregation import aggregate_status
from perfcheck.regression_metrics import evaluate_metric
from perfcheck.regression_models import (
    Cohort,
    MetricEvaluationInput,
    MetricExclusion,
    MetricOutcome,
    RegressionOutcome,
)

__all__ = (
    "Cohort",
    "MetricExclusion",
    "MetricOutcome",
    "RegressionOutcome",
    "evaluate_regression",
)

if TYPE_CHECKING:
    from perfcheck.bootstrap import CohortBootstrapOptions
    from perfcheck.comparison_models import ComparisonCohorts
    from perfcheck.policy_models import SuitePolicy


def evaluate_regression(
    policy: SuitePolicy,
    cohorts: ComparisonCohorts,
    cohort_options: CohortBootstrapOptions | None = None,
) -> RegressionOutcome:
    """Apply one suite policy to validated cohorts without claiming equivalence."""
    outcomes = tuple(
        evaluate_metric(MetricEvaluationInput(policy, metric, cohort_options), cohorts)
        for metric in policy.metrics
    )
    return RegressionOutcome(status=aggregate_status(outcomes), metrics=outcomes)
