"""Deterministic JSON and Markdown report schema and renderers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from perfcheck.bootstrap import BaselineReferenceResult, CohortBootstrapResult
from perfcheck.model_types import AlgorithmManifest, StrictModel
from perfcheck.policy import comparison_fingerprint
from perfcheck.storage import canonical_json_bytes

if TYPE_CHECKING:
    from perfcheck.comparison_models import ComparisonCohorts
    from perfcheck.policy_models import MetricPolicy, SuitePolicy
    from perfcheck.regression import MetricOutcome, RegressionOutcome
    from perfcheck.summary_models import SummaryArtifact


class ReportSample(StrictModel):
    """One eligible scalar with canonical source identities."""

    source_run_id: str
    source_content_sha256: str
    value: float


class ReportCohort(StrictModel):
    """Stable selected values from one comparison cohort."""

    count: int
    values: tuple[ReportSample, ...]


class ReportExclusion(StrictModel):
    """One retained reason a run could not support a metric decision."""

    cohort: str
    source_run_id: str
    reason: str


class ReportOptions(StrictModel):
    """Method inputs and retained stochastic options."""

    requested_alpha: float | None
    effective_alpha: float | None
    effective_seed: int | None
    requested_resamples: int | None
    effective_resamples: int | None


class ReportProvenance(StrictModel):
    """Portable policy identity and algorithm manifest without local paths."""

    policy_id: str
    suite_id: str
    policy_sha256: str
    algorithm_manifest: AlgorithmManifest


class ReportMetric(StrictModel):
    """Reviewable report representation of one regression metric."""

    metric_id: str
    statistic: str
    unit: str
    direction: str
    enabled: bool
    status: str
    method: str | None
    current: ReportCohort
    baseline: ReportCohort
    effect: float | None
    decision_lower_bound: float | None
    diagnostic_lower_bound: float | None
    diagnostic_upper_bound: float | None
    reference_quantile: float | None
    reference_anomaly: bool | None
    practical_threshold: float
    sample_size_warning: bool
    comparison_fingerprint: str
    exclusions: tuple[ReportExclusion, ...]
    options: ReportOptions
    reason: str | None


class Report(StrictModel):
    """Portable report model rendered by the comparison command in a later task."""

    schema_version: Literal[1] = 1
    suite_status: str
    provenance: ReportProvenance
    metrics: tuple[ReportMetric, ...]


def build_report(
    policy: SuitePolicy, cohorts: ComparisonCohorts, outcome: RegressionOutcome
) -> Report:
    """Build a stable, path-free model from policy, summaries, and verdicts."""
    policy_metrics = {metric.metric_id: metric for metric in policy.metrics}
    metrics = tuple(
        _build_metric(
            policy,
            policy_metrics[outcome_metric.metric_id],
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


def render_json_report(report: Report) -> str:
    """Render the report using the normative canonical JSON encoding."""
    return canonical_json_bytes(report).decode()


def render_markdown_report(report: Report) -> str:
    """Render the report as escaped, LF-only review Markdown."""
    rows = [
        "# Perfcheck report",
        "",
        f"Suite status: {_escape(report.suite_status)}",
        "",
        (
            "| Metric | Statistic | Status | Current | Baseline | Effect | CI | "
            "Threshold | Warning | Fingerprint | Reason |"
        ),
        "| --- | --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- | --- |",
    ]
    rows.extend(_markdown_metric(metric) for metric in report.metrics)
    rows.extend(
        (
            "",
            "## Exclusions",
            "",
            "| Metric | Cohort | Run | Reason |",
            "| --- | --- | --- | --- |",
        )
    )
    rows.extend(
        "| "
        + " | ".join(
            (
                _escape(metric.metric_id),
                _escape(exclusion.cohort),
                _escape(exclusion.source_run_id),
                _escape(exclusion.reason),
            )
        )
        + " |"
        for metric in report.metrics
        for exclusion in metric.exclusions
    )
    rows.extend(("", "## Provenance", "", "| Field | Value |", "| --- | --- |"))
    rows.extend(
        (
            f"| Policy ID | {_escape(report.provenance.policy_id)} |",
            f"| Suite ID | {_escape(report.provenance.suite_id)} |",
            f"| Policy SHA-256 | {_escape(report.provenance.policy_sha256)} |",
            (
                "| Algorithm manifest | "
                f"{_escape(report.provenance.algorithm_manifest.report)} |"
            ),
        )
    )
    return "\n".join(rows) + "\n"


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


def _markdown_metric(metric: ReportMetric) -> str:
    ci = (
        "-"
        if metric.diagnostic_lower_bound is None
        else (
            f"{_number(metric.diagnostic_lower_bound)} "
            f"to {_number(metric.diagnostic_upper_bound)}"
        )
    )
    return (
        "| "
        + " | ".join(
            (
                _escape(metric.metric_id),
                _escape(metric.statistic),
                _escape(metric.status),
                _cohort_values(metric.current),
                _cohort_values(metric.baseline),
                _number(metric.effect),
                ci,
                _number(metric.practical_threshold),
                _escape(str(metric.sample_size_warning)),
                _escape(metric.comparison_fingerprint),
                _escape(metric.reason or "-"),
            )
        )
        + " |"
    )


def _number(value: float | None) -> str:
    return "-" if value is None else f"{value:+.6f}"


def _cohort_values(cohort: ReportCohort) -> str:
    values = ", ".join(_number(sample.value) for sample in cohort.values)
    return f"{cohort.count}: [{values}]"


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("`", "\\`")
        .replace("\r\n", "<br>")
        .replace("\n", "<br>")
        .replace("\r", "<br>")
    )
