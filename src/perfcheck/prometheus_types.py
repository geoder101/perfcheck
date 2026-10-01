"""Local typed outcomes until shared artifact models are available."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from pydantic import JsonValue


@unique
class FailureKind(StrEnum):
    """Stable reasons a metric cannot provide range-query evidence."""

    UNSAFE_ENDPOINT = "unsafe_endpoint"
    INVALID_REQUEST = "invalid_request"
    TIMEOUT = "timeout"
    TRANSPORT = "transport"
    HTTP_ERROR = "http_error"
    API_ERROR = "api_error"
    MALFORMED_RESPONSE = "malformed_response"
    RESULT_TYPE = "result_type"
    EMPTY_SERIES = "empty_series"
    MULTIPLE_SERIES = "multiple_series"
    UNEXPECTED_LABELS = "unexpected_labels"
    HISTOGRAM_SAMPLE = "histogram_sample"
    NONFINITE_SAMPLE = "nonfinite_sample"
    DUPLICATE_TIMESTAMP = "duplicate_timestamp"


@dataclass(frozen=True, slots=True)
class RangeQuery:
    """One policy-derived Prometheus matrix request."""

    prometheus_url: str
    query: str
    start: datetime
    end: datetime
    step_seconds: int
    expected_labels: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class QueryProvenance:
    """Secret-free request evidence retained for later artifacts."""

    endpoint: str
    query: str
    start: str
    end: str
    step: str
    limit: int
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class ResponseProvenance:
    """Sanitized response evidence, including Prometheus annotations."""

    status_code: int
    body: JsonValue | None
    warnings: tuple[str, ...]
    infos: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PrometheusSample:
    """One validated finite float range sample."""

    timestamp: float
    value: float


@dataclass(frozen=True, slots=True)
class CollectionSuccess:
    """A matrix with exactly one validated policy series."""

    request: QueryProvenance
    response: ResponseProvenance
    labels: Mapping[str, str]
    samples: tuple[PrometheusSample, ...]
    cardinality: int


@dataclass(frozen=True, slots=True)
class CollectionFailure:
    """Typed secret-free collection failure retained with partial evidence."""

    kind: FailureKind
    message: str
    request: QueryProvenance | None
    response: ResponseProvenance | None


type CollectionResult = CollectionSuccess | CollectionFailure
