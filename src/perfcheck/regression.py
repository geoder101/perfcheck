"""Policy-driven regression outcomes over validated summary cohorts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from perfcheck.bootstrap import (
    DEFAULT_COHORT_OPTIONS,
    DEFAULT_REFERENCE_OPTIONS,
    BaselineReferenceResult,
    CohortBootstrapOptions,
    CohortBootstrapResult,
    MetricComparisonInput,
    ReferenceOptions,
    RunValue,
    baseline_references,
    bootstrap_cohorts,
)
from perfcheck.model_types import ComparisonMethod, Direction, Status
from perfcheck.policy import ComparisonInput, comparison_fingerprint, select_comparison

if TYPE_CHECKING:
    from perfcheck.comparison_models import ComparisonCohorts
    from perfcheck.policy_models import MetricPolicy, SuitePolicy
    from perfcheck.summary_models import SummaryArtifact


class Cohort(StrEnum):
    """The source cohort of a metric exclusion."""

    CURRENT = "current"
    BASELINE = "baseline"


@dataclass(frozen=True, slots=True)
class MetricExclusion:
    """One run withheld from one metric decision with its exact reason."""

    cohort: Cohort
    source_run_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class MetricOutcome:
    """One metric's verdict, selected evidence, and filtered run provenance."""

    metric_id: str
    direction: Direction
    enabled: bool
    status: Status
    method: ComparisonMethod | None
    evidence: BaselineReferenceResult | CohortBootstrapResult | None
    reason: str | None
    exclusions: tuple[MetricExclusion, ...]


@dataclass(frozen=True, slots=True)
class RegressionOutcome:
    """Deterministic suite verdict assembled from its policy metric outcomes."""

    status: Status
    metrics: tuple[MetricOutcome, ...]


@dataclass(frozen=True, slots=True)
class _MetricEvaluationInput:
    policy: SuitePolicy
    metric: MetricPolicy
    cohort_options: CohortBootstrapOptions | None


@dataclass(frozen=True, slots=True)
class _EligibleMetricCohort:
    run_values: tuple[RunValue, ...]
    comparison_inputs: tuple[ComparisonInput, ...]
    exclusions: tuple[MetricExclusion, ...]


def evaluate_regression(
    policy: SuitePolicy,
    cohorts: ComparisonCohorts,
    cohort_options: CohortBootstrapOptions | None = None,
) -> RegressionOutcome:
    """Apply one suite policy to validated cohorts without claiming equivalence."""
    outcomes = tuple(
        _evaluate_metric(
            _MetricEvaluationInput(
                policy=policy,
                metric=metric,
                cohort_options=cohort_options,
            ),
            cohorts,
        )
        for metric in policy.metrics
    )
    return RegressionOutcome(status=_aggregate_status(outcomes), metrics=outcomes)


def _evaluate_metric(
    evaluation: _MetricEvaluationInput, cohorts: ComparisonCohorts
) -> MetricOutcome:
    if not evaluation.metric.enabled:
        return MetricOutcome(
            metric_id=evaluation.metric.metric_id,
            direction=evaluation.metric.direction,
            enabled=False,
            status=Status.INCONCLUSIVE,
            method=None,
            evidence=None,
            reason="metric_disabled",
            exclusions=(),
        )

    current = _eligible_metric_cohort(evaluation, cohorts.current, Cohort.CURRENT)
    baseline = _eligible_metric_cohort(evaluation, cohorts.baseline, Cohort.BASELINE)
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
                (metric_input,),
                _cohort_options(evaluation.policy, evaluation.cohort_options),
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


def _eligible_metric_cohort(
    evaluation: _MetricEvaluationInput,
    summaries: tuple[SummaryArtifact, ...],
    cohort: Cohort,
) -> _EligibleMetricCohort:
    run_values: list[RunValue] = []
    comparison_inputs: list[ComparisonInput] = []
    exclusions: list[MetricExclusion] = []
    for summary in summaries:
        records = tuple(
            record
            for record in summary.metric_records
            if record.metric_id == evaluation.metric.metric_id
        )
        if not records:
            exclusions.append(
                MetricExclusion(
                    cohort=cohort,
                    source_run_id=summary.source_run_id,
                    reason="missing_metric",
                )
            )
            continue
        record = records[0]
        if record.summary is None:
            exclusions.append(
                MetricExclusion(
                    cohort=cohort,
                    source_run_id=summary.source_run_id,
                    reason=(
                        record.failure.reason.value
                        if record.failure is not None
                        else "metric_unavailable"
                    ),
                )
            )
            continue
        if record.summary.value is None:
            exclusions.append(
                MetricExclusion(
                    cohort=cohort,
                    source_run_id=summary.source_run_id,
                    reason=(
                        record.summary.eligibility.reason.value
                        if record.summary.eligibility.reason is not None
                        else "metric_ineligible"
                    ),
                )
            )
            continue
        run_values.append(
            RunValue(source_run_id=summary.source_run_id, value=record.summary.value)
        )
        comparison_inputs.append(
            ComparisonInput(
                source_run_id=summary.source_run_id,
                source_content_sha256=summary.source_content_sha256,
                interval_start=summary.source_interval.start,
                interval_end=summary.source_interval.end,
                policy_sha256=summary.policy_sha256,
                metric_fingerprints=tuple(
                    record.summary.compatibility_fingerprint
                    if metric.metric_id == evaluation.metric.metric_id
                    else comparison_fingerprint(evaluation.policy, metric)
                    for metric in evaluation.policy.metrics
                ),
            )
        )
    return _EligibleMetricCohort(
        run_values=tuple(run_values),
        comparison_inputs=tuple(comparison_inputs),
        exclusions=tuple(exclusions),
    )


def _reference_options(
    cohort_options: CohortBootstrapOptions | None,
) -> ReferenceOptions:
    if cohort_options is None:
        return DEFAULT_REFERENCE_OPTIONS
    return ReferenceOptions(
        seed=cohort_options.seed,
        requested_resamples=cohort_options.requested_resamples,
    )


def _cohort_options(
    policy: SuitePolicy, cohort_options: CohortBootstrapOptions | None
) -> CohortBootstrapOptions:
    options = cohort_options or DEFAULT_COHORT_OPTIONS
    return CohortBootstrapOptions(
        seed=options.seed,
        requested_resamples=options.requested_resamples,
        enabled_metric_count=sum(metric.enabled for metric in policy.metrics),
    )


def _aggregate_status(metrics: tuple[MetricOutcome, ...]) -> Status:
    enabled_metrics = tuple(metric for metric in metrics if metric.enabled)
    if any(metric.status is Status.FAIL for metric in enabled_metrics):
        return Status.FAIL
    if any(metric.status is Status.INCONCLUSIVE for metric in enabled_metrics):
        return Status.INCONCLUSIVE
    return Status.PASS
