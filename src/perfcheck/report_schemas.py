"""Portable report schemas exposed by the report facade."""

from typing import Literal

from perfcheck.model_types import (
    AlgorithmManifest,
    ComparisonMethod,
    CompatibilitySha256,
    Direction,
    MetricIdentifier,
    MetricUnit,
    PolicyIdentifier,
    PolicySha256,
    Statistic,
    Status,
    StrictModel,
    SuiteIdentifier,
)


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

    policy_id: PolicyIdentifier
    suite_id: SuiteIdentifier
    policy_sha256: PolicySha256
    algorithm_manifest: AlgorithmManifest


class ReportMetric(StrictModel):
    """Reviewable report representation of one regression metric."""

    metric_id: MetricIdentifier
    statistic: Statistic
    unit: MetricUnit
    direction: Direction
    enabled: bool
    status: Status
    method: ComparisonMethod | None
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
    comparison_fingerprint: CompatibilitySha256
    exclusions: tuple[ReportExclusion, ...]
    options: ReportOptions
    reason: str | None


class Report(StrictModel):
    """Portable report model rendered by the comparison command."""

    schema_version: Literal[1] = 1
    suite_status: str
    provenance: ReportProvenance
    metrics: tuple[ReportMetric, ...]
