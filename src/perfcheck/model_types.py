"""Strict shared types and enumerations for versioned artifacts."""

from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

_OK_STATUS: Final = "pass"

type ArtifactHash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
type Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")]
type LabelName = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]
type NonBlankText = Annotated[str, Field(min_length=1, pattern=r"\S")]
type FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
type Fraction = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
type PositiveInteger = Annotated[int, Field(gt=0)]
type NonNegativeInteger = Annotated[int, Field(ge=0)]
type HttpStatusCode = Annotated[int, Field(ge=100, le=599)]


class ArtifactKind(StrEnum):
    """Persisted artifact discriminator values."""

    RUN = "run"
    SUMMARY = "summary"


class ComparisonMode(StrEnum):
    """Policy-selected comparison modes."""

    AUTO = "auto"
    BASELINE_REFERENCE = "baseline_reference"
    COHORT_BOOTSTRAP = "cohort_bootstrap"


class ComparisonMethod(StrEnum):
    """Methods recorded in comparison outcomes."""

    BASELINE_REFERENCE = "baseline_reference"
    COHORT_BOOTSTRAP = "cohort_bootstrap"


class Status(StrEnum):
    """Possible decision outcomes."""

    PASS = _OK_STATUS
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class Direction(StrEnum):
    """The direction in which a metric worsens."""

    HIGHER_IS_WORSE = "higher_is_worse"
    LOWER_IS_WORSE = "lower_is_worse"


class Statistic(StrEnum):
    """Supported per-run summary statistics."""

    MEAN = "mean"
    P50 = "p50"
    P90 = "p90"
    P95 = "p95"
    P99 = "p99"
    MIN = "min"
    MAX = "max"
    STD = "std"
    FIRST = "first"
    LAST = "last"
    DELTA = "delta"
    SLOPE = "slope"


class MetricUnit(StrEnum):
    """Explicit units allowed by the version-one policy contract."""

    BYTES = "bytes"
    BYTES_PER_SECOND = "bytes_per_second"
    COUNT = "count"
    MILLISECONDS = "milliseconds"
    PERCENT = "percent"
    REQUESTS_PER_SECOND = "requests_per_second"
    SECONDS = "seconds"


class MetricAvailability(StrEnum):
    """Collection availability retained from raw through summary artifacts."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class PrometheusStatus(StrEnum):
    """Prometheus API response statuses that can be persisted safely."""

    SUCCESS = "success"
    ERROR = "error"


class CollectionFailureReason(StrEnum):
    """Known unavailable-metric causes."""

    INVALID_RESPONSE = "invalid_response"
    MULTIPLE_SERIES = "multiple_series"
    NO_SERIES = "no_series"
    NONFINITE_VALUE = "nonfinite_value"
    TIMEOUT = "timeout"
    TRANSPORT_ERROR = "transport_error"
    UNEXPECTED_LABELS = "unexpected_labels"


class EligibilityReason(StrEnum):
    """Known reasons a collected metric cannot participate in comparison."""

    ANALYSIS_WINDOW_TOO_SHORT = "analysis_window_too_short"
    COVERAGE_TOO_LOW = "coverage_too_low"
    DUPLICATE_TIMESTAMP = "duplicate_timestamp"
    EMPTY_SERIES = "empty_series"
    GAP_TOO_LARGE = "gap_too_large"
    INSUFFICIENT_POINTS = "insufficient_points"
    NONFINITE_VALUE = "nonfinite_value"
    STATISTIC_REQUIRES_MORE_POINTS = "statistic_requires_more_points"


class StrictModel(BaseModel):
    """Immutable, strict, forward-compatible public boundary model."""

    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
    )


class AlgorithmManifest(StrictModel):
    """The only algorithm suite supported by the version-one contract."""

    summary: Literal["linear-quantile-v1"] = "linear-quantile-v1"
    eligibility: Literal["trim-coverage-gap-v1"] = "trim-coverage-gap-v1"
    bootstrap: Literal["pcg64-percentile-v1"] = "pcg64-percentile-v1"
    report: Literal["canonical-json-markdown-v1"] = "canonical-json-markdown-v1"


V1_ALGORITHM_MANIFEST: Final = AlgorithmManifest()
