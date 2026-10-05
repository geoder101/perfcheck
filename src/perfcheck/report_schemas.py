"""Portable report schemas exposed by the report facade."""

from typing import Literal

from perfcheck.model_types import AlgorithmManifest, StrictModel


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
    """Portable report model rendered by the comparison command."""

    schema_version: Literal[1] = 1
    suite_status: str
    provenance: ReportProvenance
    metrics: tuple[ReportMetric, ...]
