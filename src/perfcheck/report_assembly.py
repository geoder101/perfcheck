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
    match evidence:
        case CohortBootstrapResult():
            effect = evidence.observed_effect
            decision_lower_bound = evidence.lower_decision_bound
            diagnostic_lower_bound = evidence.diagnostic_lower_bound
            diagnostic_upper_bound = evidence.diagnostic_upper_bound
            reference_quantile = None
            reference_anomaly = None
            warning = evidence.sample_size_warning
            options = _options(evidence)
        case BaselineReferenceResult():
            effect = evidence.reference_effect
            decision_lower_bound = None
            diagnostic_lower_bound = None
            diagnostic_upper_bound = None
            reference_quantile = evidence.reference_quantile
            reference_anomaly = evidence.reference_anomaly
            warning = evidence.sample_size_warning
            options = _options(evidence)
        case None:
            effect = None
            decision_lower_bound = None
            diagnostic_lower_bound = None
            diagnostic_upper_bound = None
            reference_quantile = None
            reference_anomaly = None
            warning = False
            options = ReportOptions(
                requested_alpha=None,
                effective_alpha=None,
                effective_seed=None,
                requested_resamples=None,
                effective_resamples=None,
            )
        case _:
            assert_never(evidence)
    return ReportMetric(
        metric_id=outcome.metric_id,
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
