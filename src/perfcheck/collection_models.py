"""Strict raw collection records for version-one run artifacts."""

from typing import TYPE_CHECKING, Literal, Self
from urllib.parse import urlsplit

from pydantic import AwareDatetime, Field, field_validator, model_validator

from perfcheck.artifact_validation import (
    contains_secret,
    validate_interval,
    validate_utc,
)
from perfcheck.errors import ArtifactSchemaCode, ArtifactSchemaError
from perfcheck.model_types import (
    CollectionFailureReason,
    FiniteFloat,
    HttpStatusCode,
    LabelName,
    MetricAvailability,
    MetricIdentifier,
    NonBlankText,
    PositiveInteger,
    Rfc3339UtcDatetime,
    StrictModel,
)

if TYPE_CHECKING:
    from datetime import datetime


class SourceInterval(StrictModel):
    """Immutable inclusive source bounds for raw and summary artifacts."""

    start: Rfc3339UtcDatetime
    end: Rfc3339UtcDatetime

    @field_validator("start", "end")
    @classmethod
    def validate_utc_timestamp(cls, value: datetime) -> datetime:
        """Require an RFC-3339 instant in UTC."""
        return validate_utc(value)

    @model_validator(mode="after")
    def validate_source_interval(self) -> Self:
        """Require a positive source interval."""
        validate_interval(self.start, self.end)
        return self


class Label(StrictModel):
    """One Prometheus matrix label from the validated response."""

    name: LabelName
    value: NonBlankText

    @field_validator("value")
    @classmethod
    def reject_sensitive_value(cls, value: str) -> str:
        """Prevent request credentials entering persisted label values."""
        if contains_secret(value):
            raise ArtifactSchemaError(ArtifactSchemaCode.CREDENTIAL_LABEL_VALUE)
        return value


class FloatSample(StrictModel):
    """One finite UTC timestamped sample from a matrix series."""

    timestamp: Rfc3339UtcDatetime
    value: FiniteFloat

    @field_validator("timestamp")
    @classmethod
    def validate_utc_timestamp(cls, value: datetime) -> datetime:
        """Require an RFC-3339 instant in UTC."""
        return validate_utc(value)


class LabelledMetricSeries(StrictModel):
    """The single labelled finite-float matrix series for one policy metric."""

    metric_id: MetricIdentifier
    labels: tuple[Label, ...] = ()
    samples: tuple[FloatSample, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_series(self) -> Self:
        """Require sorted unique labels and strictly increasing timestamps."""
        label_names = tuple(label.name for label in self.labels)
        if len(label_names) != len(set(label_names)):
            raise ArtifactSchemaError(ArtifactSchemaCode.DUPLICATE_LABEL)
        if label_names != tuple(sorted(label_names)):
            raise ArtifactSchemaError(ArtifactSchemaCode.LABEL_ORDER)
        timestamps = tuple(sample.timestamp for sample in self.samples)
        if timestamps != tuple(sorted(timestamps)) or len(timestamps) != len(
            set(timestamps)
        ):
            raise ArtifactSchemaError(ArtifactSchemaCode.INVALID_SAMPLE_ORDER)
        return self


class QueryProvenance(StrictModel):
    """Secret-free request and response provenance for one collection query."""

    endpoint_url: NonBlankText
    request_path: Literal["/api/v1/query_range"] = "/api/v1/query_range"
    query: NonBlankText
    start: AwareDatetime
    end: AwareDatetime
    step_seconds: PositiveInteger
    http_status: HttpStatusCode | None = None

    @field_validator("endpoint_url")
    @classmethod
    def validate_endpoint_url(cls, value: str) -> str:
        """Accept only credential-free HTTP(S) origins or base paths."""
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ArtifactSchemaError(ArtifactSchemaCode.INVALID_ENDPOINT_URL)
        return value

    @field_validator("query")
    @classmethod
    def reject_secret_query(cls, value: str) -> str:
        """Prevent embedded request credentials from being persisted."""
        if contains_secret(value):
            raise ArtifactSchemaError(ArtifactSchemaCode.CREDENTIAL_QUERY)
        return value

    @field_validator("start", "end")
    @classmethod
    def validate_utc_timestamp(cls, value: AwareDatetime) -> AwareDatetime:
        """Require an RFC-3339 instant in UTC."""
        return validate_utc(value)

    @model_validator(mode="after")
    def validate_request_interval(self) -> Self:
        """Require a positive request interval."""
        validate_interval(self.start, self.end)
        return self


class CollectionFailure(StrictModel):
    """A typed secret-free reason a policy metric is unavailable."""

    reason: CollectionFailureReason
    detail: NonBlankText

    @field_validator("detail")
    @classmethod
    def reject_secret_detail(cls, value: str) -> str:
        """Prevent credentials from entering failure diagnostics."""
        if contains_secret(value):
            raise ArtifactSchemaError(ArtifactSchemaCode.CREDENTIAL_DETAIL)
        return value


class MetricCollectionRecord(StrictModel):
    """One policy metric's available series or typed collection failure."""

    metric_id: MetricIdentifier
    availability: MetricAvailability
    provenance: QueryProvenance
    series: LabelledMetricSeries | None = None
    failure: CollectionFailure | None = None

    @model_validator(mode="after")
    def validate_availability(self) -> Self:
        """Make available and unavailable collection states disjoint."""
        available_is_valid = (
            self.availability is MetricAvailability.AVAILABLE
            and self.series is not None
            and self.failure is None
        )
        unavailable_is_valid = (
            self.availability is MetricAvailability.UNAVAILABLE
            and self.series is None
            and self.failure is not None
        )
        if not (available_is_valid or unavailable_is_valid):
            raise ArtifactSchemaError(ArtifactSchemaCode.INVALID_COLLECTION_RECORD)
        return self
