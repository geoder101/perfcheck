"""Report model assembly from validated policy, summary, and outcome evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from perfcheck.bootstrap import BaselineReferenceResult, CohortBootstrapResult
from perfcheck.model_types import MetricId
from perfcheck.policy import comparison_fingerprint
from perfcheck.report_schemas import (
    Report,
    ReportCohort,
    ReportExclusion,
    ReportMetric,
    ReportOptions,
    ReportProvenance,
    ReportSample,
)

if TYPE_CHECKING:
    from perfcheck.comparison_models import ComparisonCohorts
    from perfcheck.policy_models import MetricPolicy, SuitePolicy
    from perfcheck.regression_models import MetricOutcome, RegressionOutcome
    from perfcheck.summary_models import SummaryArtifact


def build_report(
    policy: SuitePolicy, cohorts: ComparisonCohorts, outcome: RegressionOutcome
) -> Report:
    """Build a stable, path-free model from policy, summaries, and verdicts."""
    policy_metrics = {metric.metric_id: metric for metric in policy.metrics}
    metrics = tuple(
        _build_metric(
            policy,
            policy_metrics[MetricId(outcome_metric.metric_id)],
            cohorts,
            outcome_metric,
        )
        for outcome_metric in sorted(
            outcome.metrics, key=lambda metric: metric.metric_id
        )
    )
    return Report(
        suite_status=outcome.status,
        provenance=ReportProvenance(
            policy_id=policy.policy_id,
            suite_id=policy.suite_id,
            policy_sha256=policy.policy_sha256,
            algorithm_manifest=policy.algorithm_manifest,
        ),
        metrics=metrics,
    )


def _build_metric(
    policy: SuitePolicy,
    metric: MetricPolicy,
    cohorts: ComparisonCohorts,
    outcome: MetricOutcome,
) -> ReportMetric:
    evidence = outcome.evidence
    parts: tuple[
        float | None,
        float | None,
        float | None,
        float | None,
        float | None,
        bool | None,
    ]
    warning: bool
    options: ReportOptions
    match evidence:
        case CohortBootstrapResult() as cohort:
            parts = _cohort_bootstrap_fields(cohort)
            warning = cohort.sample_size_warning
            options = _options(cohort)
        case BaselineReferenceResult() as reference:
            parts = _baseline_reference_fields(reference)
            warning = reference.sample_size_warning
            options = _options(reference)
        case None:
            parts = (None, None, None, None, None, None)
            warning = False
            options = _empty_options()
        case _:
            assert_never(evidence)
    (
        effect,
        decision_lower_bound,
        diagnostic_lower_bound,
        diagnostic_upper_bound,
        reference_quantile,
        reference_anomaly,
    ) = parts
    return ReportMetric(
        metric_id=MetricId(outcome.metric_id),
        statistic=metric.statistic,
        unit=metric.unit,
        direction=outcome.direction,
        enabled=outcome.enabled,
        status=outcome.status,
        method=outcome.method,
        current=_cohort(metric.metric_id, cohorts.current),
        baseline=_cohort(metric.metric_id, cohorts.baseline),
        effect=effect,
        decision_lower_bound=decision_lower_bound,
        diagnostic_lower_bound=diagnostic_lower_bound,
        diagnostic_upper_bound=diagnostic_upper_bound,
        reference_quantile=reference_quantile,
        reference_anomaly=reference_anomaly,
        practical_threshold=metric.practical_threshold,
        sample_size_warning=warning,
        comparison_fingerprint=comparison_fingerprint(policy, metric),
        exclusions=tuple(
            ReportExclusion(
                cohort=exclusion.cohort,
                source_run_id=exclusion.source_run_id,
                reason=exclusion.reason,
            )
            for exclusion in outcome.exclusions
        ),
        options=options,
        reason=outcome.reason,
    )


def _cohort_bootstrap_fields(
    evidence: CohortBootstrapResult,
) -> tuple[float, float, float, float, None, None]:
    """Project cohort-bootstrap evidence onto the six optional report fields."""
    return (
        evidence.observed_effect,
        evidence.lower_decision_bound,
        evidence.diagnostic_lower_bound,
        evidence.diagnostic_upper_bound,
        None,
        None,
    )


def _baseline_reference_fields(
    evidence: BaselineReferenceResult,
) -> tuple[float, None, None, None, float, bool]:
    """Project baseline-reference evidence onto the six optional report fields."""
    return (
        evidence.reference_effect,
        None,
        None,
        None,
        evidence.reference_quantile,
        evidence.reference_anomaly,
    )


def _empty_options() -> ReportOptions:
    """Return the option set used when no comparison evidence is present."""
    return ReportOptions(
        requested_alpha=None,
        effective_alpha=None,
        effective_seed=None,
        requested_resamples=None,
        effective_resamples=None,
    )


def _cohort(metric_id: str, summaries: tuple[SummaryArtifact, ...]) -> ReportCohort:
    samples = tuple(
        sorted(
            (
                ReportSample(
                    source_run_id=summary.source_run_id,
                    source_content_sha256=summary.source_content_sha256,
                    value=record.summary.value,
                )
                for summary in summaries
                for record in summary.metric_records
                if record.metric_id == metric_id
                and record.summary is not None
                and record.summary.value is not None
            ),
            key=lambda sample: sample.source_run_id,
        )
    )
    return ReportCohort(count=len(samples), values=samples)


def _options(
    evidence: CohortBootstrapResult | BaselineReferenceResult,
) -> ReportOptions:
    return ReportOptions(
        requested_alpha=evidence.requested_alpha,
        effective_alpha=evidence.effective_alpha,
        effective_seed=evidence.effective_seed,
        requested_resamples=evidence.requested_resamples,
        effective_resamples=evidence.effective_resamples,
    )
