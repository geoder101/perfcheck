"""Narrow typed excerpts of the real capstone JSON report, not another engine."""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class CohortExcerpt(BaseModel):
    """Actual eligible run count in a report cohort."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    count: int


class OptionsExcerpt(BaseModel):
    """Recorded numerical provenance; reference has no stochastic options."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    requested_alpha: float | None
    effective_alpha: float | None
    effective_seed: int | None
    requested_resamples: int | None
    effective_resamples: int | None


class MetricExcerpt(BaseModel):
    """Fields a learner needs to audit the selected decision."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    metric_id: str
    status: str
    method: str
    direction: str
    unit: str
    statistic: str
    baseline: CohortExcerpt
    current: CohortExcerpt
    effect: float | None
    decision_lower_bound: float | None
    practical_threshold: float
    reference_quantile: float | None
    reference_anomaly: bool | None
    sample_size_warning: bool
    options: OptionsExcerpt


class CapstoneReport(BaseModel):
    """Parse the report at the display boundary without a production API dependency."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    suite_status: str
    metrics: tuple[MetricExcerpt, ...] = Field(min_length=1)
