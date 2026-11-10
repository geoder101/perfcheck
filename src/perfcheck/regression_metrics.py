"""Per-metric policy evaluation for regression decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from perfcheck.bootstrap import (
    DEFAULT_COHORT_OPTIONS,
    DEFAULT_REFERENCE_OPTIONS,
    CohortBootstrapOptions,
    MetricComparisonInput,
    ReferenceOptions,
    baseline_references,
    bootstrap_cohorts,
)
from perfcheck.model_types import ComparisonMethod, MetricReason, Status
from perfcheck.policy import select_comparison
from perfcheck.regression_cohorts import eligible_metric_cohort
from perfcheck.regression_models import Cohort, MetricEvaluationInput, MetricOutcome

if TYPE_CHECKING:
    from perfcheck.comparison_models import ComparisonCohorts


def evaluate_metric(
    evaluation: MetricEvaluationInput, cohorts: ComparisonCohorts
) -> MetricOutcome:
    """Evaluate one policy metric against validated current and baseline cohorts."""
    if not evaluation.metric.enabled:
        return MetricOutcome(
            metric_id=evaluation.metric.metric_id,
            direction=evaluation.metric.direction,
            enabled=False,
            status=Status.INCONCLUSIVE,
            method=None,
            evidence=None,
            reason=MetricReason.METRIC_DISABLED,
            exclusions=(),
        )

    current = eligible_metric_cohort(evaluation, cohorts.current, Cohort.CURRENT)
    baseline = eligible_metric_cohort(evaluation, cohorts.baseline, Cohort.BASELINE)
    selection = select_comparison(
        evaluation.policy, current.comparison_inputs, baseline.comparison_inputs
    )
    exclusions = current.exclusions + baseline.exclusions
    if selection.method is None:
        return MetricOutcome(
            metric_id=evaluation.metric.metric_id,
            direction=evaluation.metric.direction,
            enabled=True,
            status=Status.INCONCLUSIVE,
            method=None,
            evidence=None,
            reason=str(selection.reason),
            exclusions=exclusions,
        )

    metric_input = MetricComparisonInput(
        metric_id=evaluation.metric.metric_id,
        direction=evaluation.metric.direction,
        requested_alpha=evaluation.policy.nominal_alpha,
        effective_alpha=selection.alpha_effective,
        practical_threshold=evaluation.metric.practical_threshold,
        current=current.run_values,
        baseline=baseline.run_values,
        sample_size_warning=selection.small_cohort_warning,
    )
    match selection.method:
        case ComparisonMethod.BASELINE_REFERENCE:
            (evidence,) = baseline_references(
                (metric_input,), _reference_options(evaluation.cohort_options)
            )
            return MetricOutcome(
                metric_id=evaluation.metric.metric_id,
                direction=evaluation.metric.direction,
                enabled=True,
                status=Status.INCONCLUSIVE,
                method=evidence.method,
                evidence=evidence,
                reason=None,
                exclusions=exclusions,
            )
        case ComparisonMethod.COHORT_BOOTSTRAP:
            (evidence,) = bootstrap_cohorts(
                (metric_input,), _cohort_options(evaluation)
            )
            status = (
                Status.FAIL
                if evidence.lower_decision_bound > evaluation.metric.practical_threshold
                else Status.PASS
            )
            return MetricOutcome(
                metric_id=evaluation.metric.metric_id,
                direction=evaluation.metric.direction,
                enabled=True,
                status=status,
                method=evidence.method,
                evidence=evidence,
                reason=None,
                exclusions=exclusions,
            )
        case _:
            assert_never(selection.method)


def _reference_options(
    cohort_options: CohortBootstrapOptions | None,
) -> ReferenceOptions:
    if cohort_options is None:
        return DEFAULT_REFERENCE_OPTIONS
    return ReferenceOptions(
        seed=cohort_options.seed,
        requested_resamples=cohort_options.requested_resamples,
    )


def _cohort_options(evaluation: MetricEvaluationInput) -> CohortBootstrapOptions:
    options = evaluation.cohort_options or DEFAULT_COHORT_OPTIONS
    return CohortBootstrapOptions(
        seed=options.seed,
        requested_resamples=options.requested_resamples,
        enabled_metric_count=sum(
            metric.enabled for metric in evaluation.policy.metrics
        ),
    )
