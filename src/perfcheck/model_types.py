"""Strict shared types and enumerations for versioned artifacts."""

import re
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, ClassVar, Final, Literal, NewType

from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler
from pydantic_core import core_schema

from perfcheck.errors import ArtifactSchemaCode, ArtifactSchemaError

if TYPE_CHECKING:
    from pydantic.annotated_handlers import GetJsonSchemaHandler
    from pydantic.json_schema import JsonSchemaValue

_OK_STATUS: Final = "pass"

PolicyId = NewType("PolicyId", str)
SuiteId = NewType("SuiteId", str)
MetricId = NewType("MetricId", str)
RunId = NewType("RunId", str)
SummaryId = NewType("SummaryId", str)
PolicyHash = NewType("PolicyHash", str)
ArtifactContentHash = NewType("ArtifactContentHash", str)
CompatibilityFingerprint = NewType("CompatibilityFingerprint", str)

type _Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")]
type _Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
type PolicyIdentifier = _Identifier
type SuiteIdentifier = _Identifier
type MetricIdentifier = Annotated[
    MetricId, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
]
type RunIdentifier = _Identifier
type SummaryIdentifier = _Identifier
type PolicySha256 = Annotated[str, _Sha256]
type ArtifactSha256 = Annotated[str, _Sha256]
type CompatibilitySha256 = Annotated[str, _Sha256]
type LabelName = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]
type NonBlankText = Annotated[str, Field(min_length=1, pattern=r"\S")]
type FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
type Fraction = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
type PositiveInteger = Annotated[int, Field(gt=0)]
type NonNegativeInteger = Annotated[int, Field(ge=0)]
type HttpStatusCode = Annotated[int, Field(ge=100, le=599)]

_RFC3339_UTC_INSTANT: Final[re.Pattern[str]] = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)"
)


def _validate_rfc3339_utc_text(value: str) -> str:
    if _RFC3339_UTC_INSTANT.fullmatch(value):
        return value
    raise ArtifactSchemaError(ArtifactSchemaCode.INVALID_TIMESTAMP_FORMAT)


class _Rfc3339UtcTimestamp:
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: type[datetime],
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        json_schema = core_schema.chain_schema(
            [
                core_schema.str_schema(strict=True),
                core_schema.no_info_plain_validator_function(
                    _validate_rfc3339_utc_text
                ),
                core_schema.datetime_schema(strict=False, tz_constraint="aware"),
            ]
        )
        return core_schema.json_or_python_schema(
            json_schema=json_schema,
            python_schema=core_schema.datetime_schema(
                strict=True, tz_constraint="aware"
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        _core_schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        return handler(core_schema.datetime_schema(tz_constraint="aware"))


type Rfc3339UtcDatetime = Annotated[datetime, _Rfc3339UtcTimestamp]


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


class MetricReason(StrEnum):
    """Why a run is withheld or omitted from one metric's comparison decision.

    These ad-hoc reason literals used to live as plain strings across the
    regression modules; centralizing them here gives the shared ``MetricExclusion``
    and ``MetricOutcome`` reason fields one typed vocabulary instead of string
    constants repeated at each call site.
    """

    METRIC_DISABLED = "metric_disabled"
    METRIC_INELIGIBLE = "metric_ineligible"
    METRIC_MISSING = "missing_metric"
    METRIC_UNAVAILABLE = "metric_unavailable"


class StrictModel(BaseModel):
    """Immutable, strict, forward-compatible public boundary model."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
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
