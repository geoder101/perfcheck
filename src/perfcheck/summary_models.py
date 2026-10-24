"""Strict version-one summary artifact records."""

from typing import TYPE_CHECKING, Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from perfcheck.artifact_validation import (
    validate_utc,
)
from perfcheck.collection_models import CollectionFailure, SourceInterval
from perfcheck.errors import ArtifactSchemaCode, ArtifactSchemaError
from perfcheck.model_types import (
    V1_ALGORITHM_MANIFEST,
    AlgorithmManifest,
    ArtifactKind,
    ArtifactSha256,
    CompatibilitySha256,
    EligibilityReason,
    FiniteFloat,
    Fraction,
    MetricAvailability,
    MetricIdentifier,
    NonNegativeInteger,
    PolicySha256,
    PositiveInteger,
    Rfc3339UtcDatetime,
    RunIdentifier,
    Statistic,
    StrictModel,
    SummaryIdentifier,
)
from perfcheck.policy_models import SuitePolicy

if TYPE_CHECKING:
    from datetime import datetime

type NonNegativeFiniteFloat = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]


class EligibilityResult(StrictModel):
    """Persisted per-run eligibility evidence for a summarized metric."""

    eligible: bool
    reason: EligibilityReason | None
    analysis_start: Rfc3339UtcDatetime
    analysis_end: Rfc3339UtcDatetime
    retained_points: NonNegativeInteger
    expected_points: PositiveInteger
    coverage: Fraction
    analysis_duration_seconds: NonNegativeFiniteFloat = 0.0
    leading_gap_seconds: NonNegativeFiniteFloat = 0.0
    max_adjacent_gap_seconds: NonNegativeFiniteFloat = 0.0
    trailing_gap_seconds: NonNegativeFiniteFloat = 0.0
    max_allowed_gap_seconds: NonNegativeFiniteFloat = 0.0

    @field_validator("analysis_start", "analysis_end")
    @classmethod
    def validate_utc_timestamp(cls, value: datetime) -> datetime:
        """Require an RFC-3339 instant in UTC."""
        return validate_utc(value)

    @model_validator(mode="after")
    def validate_eligibility(self) -> Self:
        """Require reason and selected-value availability to agree."""
        if self.analysis_end < self.analysis_start:
            raise ArtifactSchemaError(ArtifactSchemaCode.INVALID_INTERVAL)
        if self.eligible != (self.reason is None):
            raise ArtifactSchemaError(ArtifactSchemaCode.ELIGIBILITY_REASON_MISMATCH)
        return self


class MetricSummary(StrictModel):
    """A selected statistic and eligibility record for one available metric."""

    statistic: Statistic
    value: FiniteFloat | None
    point_count: NonNegativeInteger
    compatibility_fingerprint: CompatibilitySha256
    eligibility: EligibilityResult

    @model_validator(mode="after")
    def validate_value_availability(self) -> Self:
        """Require values exactly when the metric is eligible."""
        if self.eligibility.eligible != (self.value is not None):
            raise ArtifactSchemaError(ArtifactSchemaCode.SUMMARY_VALUE_MISMATCH)
        return self


class SummaryMetricRecord(StrictModel):
    """A policy metric's retained availability/failure state in a summary."""

    metric_id: MetricIdentifier
    availability: MetricAvailability
    summary: MetricSummary | None = None
    failure: CollectionFailure | None = None

    @model_validator(mode="after")
    def validate_availability(self) -> Self:
        """Make summary availability states disjoint."""
        available_is_valid = (
            self.availability is MetricAvailability.AVAILABLE
            and self.summary is not None
            and self.failure is None
        )
        unavailable_is_valid = (
            self.availability is MetricAvailability.UNAVAILABLE
            and self.summary is None
            and self.failure is not None
        )
        if not (available_is_valid or unavailable_is_valid):
            raise ArtifactSchemaError(ArtifactSchemaCode.INVALID_SUMMARY_RECORD)
        return self


class SummaryArtifact(StrictModel):
    """A deterministic source-hashed per-run summary artifact."""

    artifact_type: Literal[ArtifactKind.SUMMARY] = ArtifactKind.SUMMARY
    schema_version: Literal[1] = 1
    content_sha256: ArtifactSha256
    summary_id: SummaryIdentifier
    source_run_id: RunIdentifier
    source_content_sha256: ArtifactSha256
    source_interval: SourceInterval
    policy_sha256: PolicySha256
    policy_snapshot: SuitePolicy
    algorithm_manifest: AlgorithmManifest = V1_ALGORITHM_MANIFEST
    metric_records: tuple[SummaryMetricRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        """Retain every policy metric with its exact statistic and manifest."""
        if self.policy_sha256 != self.policy_snapshot.policy_sha256:
            raise ArtifactSchemaError(ArtifactSchemaCode.POLICY_HASH_MISMATCH)
        expected = {metric.metric_id: metric for metric in self.policy_snapshot.metrics}
        record_ids = tuple(record.metric_id for record in self.metric_records)
        if len(record_ids) != len(set(record_ids)):
            raise ArtifactSchemaError(ArtifactSchemaCode.DUPLICATE_METRIC_RECORD)
        if set(record_ids) != set(expected):
            raise ArtifactSchemaError(ArtifactSchemaCode.METRIC_SET_MISMATCH)
        for record in self.metric_records:
            if (
                record.summary is not None
                and record.summary.statistic != expected[record.metric_id].statistic
            ):
                raise ArtifactSchemaError(ArtifactSchemaCode.STATISTIC_MISMATCH)
        return self
