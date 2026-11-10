"""Metric-specific eligibility filtering for regression cohorts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from perfcheck.bootstrap import RunValue
from perfcheck.model_types import MetricReason
from perfcheck.policy import ComparisonInput, comparison_fingerprint
from perfcheck.regression_models import (
    Cohort,
    EligibleMetricCohort,
    MetricEvaluationInput,
    MetricExclusion,
)

if TYPE_CHECKING:
    from perfcheck.summary_models import SummaryArtifact


def eligible_metric_cohort(
    evaluation: MetricEvaluationInput,
    summaries: tuple[SummaryArtifact, ...],
    cohort: Cohort,
) -> EligibleMetricCohort:
    """Filter one cohort to summaries eligible for the evaluated metric."""
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
                    cohort, summary.source_run_id, MetricReason.METRIC_MISSING
                )
            )
            continue
        record = records[0]
        if record.summary is None:
            exclusions.append(
                MetricExclusion(
                    cohort,
                    summary.source_run_id,
                    record.failure.reason.value
                    if record.failure is not None
                    else MetricReason.METRIC_UNAVAILABLE,
                )
            )
            continue
        if record.summary.value is None:
            exclusions.append(
                MetricExclusion(
                    cohort,
                    summary.source_run_id,
                    record.summary.eligibility.reason.value
                    if record.summary.eligibility.reason is not None
                    else MetricReason.METRIC_INELIGIBLE,
                )
            )
            continue
        run_values.append(RunValue(summary.source_run_id, record.summary.value))
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
    return EligibleMetricCohort(
        run_values=tuple(run_values),
        comparison_inputs=tuple(comparison_inputs),
        exclusions=tuple(exclusions),
    )
