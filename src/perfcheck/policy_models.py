"""Strict version-one suite and metric policy models."""

from typing import Final, Literal, Self

from pydantic import Field, field_validator, model_validator

from perfcheck.errors import ArtifactSchemaCode, ArtifactSchemaError
from perfcheck.model_types import (
    V1_ALGORITHM_MANIFEST,
    AlgorithmManifest,
    ComparisonMode,
    Direction,
    FiniteFloat,
    Fraction,
    LabelName,
    MetricIdentifier,
    MetricUnit,
    NonBlankText,
    NonNegativeInteger,
    PolicyIdentifier,
    PolicySha256,
    PositiveInteger,
    Statistic,
    StrictModel,
    SuiteIdentifier,
)


class EligibilityPolicy(StrictModel):
    """Inclusive trim, coverage, and gap requirements for one metric."""

    warmup_seconds: NonNegativeInteger = 0
    cooldown_seconds: NonNegativeInteger = 0
    min_analysis_window_seconds: int = Field(default=300, ge=300)
    min_points: int = Field(default=20, ge=20)
    min_coverage: Fraction = Field(default=0.8, ge=0.8)
    max_gap_steps: NonNegativeInteger = 3


DEFAULT_ELIGIBILITY_POLICY: Final = EligibilityPolicy()


class MetricPolicy(StrictModel):
    """A named metric, query, and fixed comparison interpretation."""

    metric_id: MetricIdentifier
    query: NonBlankText
    expected_label_names: tuple[LabelName, ...] = ()
    unit: MetricUnit
    direction: Direction
    statistic: Statistic
    practical_threshold: FiniteFloat = Field(ge=0.0)
    step_seconds: PositiveInteger
    rate_window_seconds: PositiveInteger
    eligibility: EligibilityPolicy = DEFAULT_ELIGIBILITY_POLICY
    enabled: bool = True

    @field_validator("expected_label_names")
    @classmethod
    def validate_expected_label_names(
        cls, value: tuple[LabelName, ...]
    ) -> tuple[LabelName, ...]:
        """Require canonical unique label names for exact matrix validation."""
        if len(value) != len(set(value)):
            raise ArtifactSchemaError(ArtifactSchemaCode.DUPLICATE_LABEL_NAME)
        if value != tuple(sorted(value)):
            raise ArtifactSchemaError(ArtifactSchemaCode.LABEL_NAME_ORDER)
        return value


class SuitePolicy(StrictModel):
    """An immutable, hash-addressed version-one collection policy snapshot."""

    schema_version: Literal[1] = 1
    policy_id: PolicyIdentifier
    suite_id: SuiteIdentifier
    policy_sha256: PolicySha256
    prometheus_url: str | None = None
    metrics: tuple[MetricPolicy, ...] = Field(min_length=1)
    comparison_mode: ComparisonMode = ComparisonMode.AUTO
    min_current_runs: PositiveInteger = 5
    min_baseline_runs: PositiveInteger = 10
    min_baseline_reference_runs: PositiveInteger = 10
    nominal_alpha: FiniteFloat = Field(default=0.05, ge=0.05, le=0.05)
    algorithm_manifest: AlgorithmManifest = V1_ALGORITHM_MANIFEST

    @model_validator(mode="after")
    def validate_metrics(self) -> Self:
        """Reject duplicate metrics and policies with no enabled gate."""
        metric_ids = tuple(metric.metric_id for metric in self.metrics)
        if len(metric_ids) != len(set(metric_ids)):
            raise ArtifactSchemaError(ArtifactSchemaCode.DUPLICATE_METRIC_ID)
        if not any(metric.enabled for metric in self.metrics):
            raise ArtifactSchemaError(ArtifactSchemaCode.MISSING_ENABLED_METRIC)
        return self
