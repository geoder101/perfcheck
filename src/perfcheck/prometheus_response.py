"""Prometheus response parsing and recursive evidence redaction."""

from __future__ import annotations

from math import isfinite
from typing import TYPE_CHECKING, Final

from pydantic import JsonValue, TypeAdapter, ValidationError

if TYPE_CHECKING:
    import httpx

from perfcheck.prometheus_types import (
    CollectionFailure,
    CollectionResult,
    CollectionSuccess,
    FailureKind,
    PrometheusSample,
    QueryProvenance,
    RangeQuery,
    ResponseProvenance,
)

_SENSITIVE_KEYS: Final = frozenset({"authorization", "token", "password", "secret"})
_JSON_VALUE_ADAPTER: Final[TypeAdapter[JsonValue]] = TypeAdapter(JsonValue)


def response_provenance(
    response: httpx.Response, token: str | None
) -> ResponseProvenance:
    """Parse and recursively redact an untrusted JSON response."""
    try:
        body = _JSON_VALUE_ADAPTER.validate_json(response.content)
    except ValidationError:
        body = None
    sanitized_body = redact_json(body, token) if body is not None else None
    return ResponseProvenance(
        status_code=response.status_code,
        body=sanitized_body,
        warnings=_annotations(sanitized_body, "warnings"),
        infos=_annotations(sanitized_body, "infos"),
    )


def classify_success(
    query: RangeQuery,
    request: QueryProvenance,
    response: ResponseProvenance,
) -> CollectionResult:
    """Validate the Prometheus API envelope and exact matrix series contract."""
    match response.body:
        case dict() as envelope:
            return _classify_envelope(query, request, response, envelope)
        case _:
            return _failure(
                FailureKind.MALFORMED_RESPONSE,
                "invalid JSON envelope",
                request,
                response,
            )


def redact_text(value: str, token: str | None) -> str:
    """Replace an exact bearer token wherever hostile text echoes it."""
    return value.replace(token, "[REDACTED]") if token else value


def redact_json(value: JsonValue, token: str | None) -> JsonValue:
    """Recursively remove secrets from arbitrary hostile server JSON."""
    match value:
        case str() as text:
            return redact_text(text, token)
        case list() as values:
            return [redact_json(item, token) for item in values]
        case dict() as mapping:
            return {
                _redacted_key(key, token): "[REDACTED]"
                if key.lower() in _SENSITIVE_KEYS
                else redact_json(item, token)
                for key, item in mapping.items()
            }
        case _:
            return value


def _redacted_key(key: str, token: str | None) -> str:
    """Sanitize untrusted JSON keys before retaining response evidence."""
    return "[REDACTED]" if key.lower() in _SENSITIVE_KEYS else redact_text(key, token)


def _annotations(body: JsonValue | None, key: str) -> tuple[str, ...]:
    match body:
        case dict() as envelope:
            match envelope.get(key):
                case list() as values if all(
                    isinstance(value, str) for value in values
                ):
                    return tuple(value for value in values if isinstance(value, str))
                case _:
                    return ()
        case _:
            return ()


def _classify_envelope(
    query: RangeQuery,
    request: QueryProvenance,
    response: ResponseProvenance,
    envelope: dict[str, JsonValue],
) -> CollectionResult:
    if envelope.get("status") != "success":
        return _failure(
            FailureKind.API_ERROR, "Prometheus API returned an error", request, response
        )
    match envelope.get("data"):
        case dict() as data:
            return _classify_matrix(query, request, response, data)
        case _:
            return _failure(
                FailureKind.MALFORMED_RESPONSE,
                "missing API data object",
                request,
                response,
            )


def _classify_matrix(
    query: RangeQuery,
    request: QueryProvenance,
    response: ResponseProvenance,
    data: dict[str, JsonValue],
) -> CollectionResult:
    if data.get("resultType") != "matrix":
        return _failure(
            FailureKind.RESULT_TYPE, "expected matrix result type", request, response
        )
    match data.get("result"):
        case list() as series:
            return _validate_series(query, request, response, series)
        case _:
            return _failure(
                FailureKind.MALFORMED_RESPONSE,
                "matrix result is missing",
                request,
                response,
            )


def _validate_series(
    query: RangeQuery,
    request: QueryProvenance,
    response: ResponseProvenance,
    series: list[JsonValue],
) -> CollectionResult:
    match len(series):
        case 0:
            return _failure(
                FailureKind.EMPTY_SERIES,
                "matrix returned zero series",
                request,
                response,
            )
        case 1:
            return _validate_single_series(query, request, response, series[0])
        case _:
            return _failure(
                FailureKind.MULTIPLE_SERIES,
                "matrix returned multiple series",
                request,
                response,
            )


def _validate_single_series(
    query: RangeQuery,
    request: QueryProvenance,
    response: ResponseProvenance,
    series: JsonValue,
) -> CollectionResult:
    match series:
        case {"metric": dict() as labels, "values": list() as values}:
            parsed_labels = _string_labels(labels)
            if parsed_labels is None or parsed_labels != dict(query.expected_labels):
                return _failure(
                    FailureKind.UNEXPECTED_LABELS,
                    "matrix labels differ from policy",
                    request,
                    response,
                )
            if series.get("histograms"):
                return _failure(
                    FailureKind.HISTOGRAM_SAMPLE,
                    "matrix contains native histograms",
                    request,
                    response,
                )
            samples = _validate_samples(values)
            if isinstance(samples, CollectionFailure):
                return _failure(samples.kind, samples.message, request, response)
            return CollectionSuccess(request, response, parsed_labels, samples, 1)
        case _:
            return _failure(
                FailureKind.MALFORMED_RESPONSE,
                "invalid matrix series",
                request,
                response,
            )


def _string_labels(labels: dict[str, JsonValue]) -> dict[str, str] | None:
    if not all(isinstance(value, str) for value in labels.values()):
        return None
    return {key: value for key, value in labels.items() if isinstance(value, str)}


def _validate_samples(
    values: list[JsonValue],
) -> tuple[PrometheusSample, ...] | CollectionFailure:
    samples: list[PrometheusSample] = []
    timestamps: set[float] = set()
    for raw_value in values:
        match raw_value:
            case [int() | float() as timestamp, str() as raw_sample]:
                sample = _parse_sample(timestamp, raw_sample)
                if isinstance(sample, CollectionFailure):
                    return sample
                if sample.timestamp in timestamps:
                    return _failure(
                        FailureKind.DUPLICATE_TIMESTAMP,
                        "duplicate sample timestamp",
                        None,
                        None,
                    )
                timestamps.add(sample.timestamp)
                samples.append(sample)
            case _:
                return _failure(
                    FailureKind.MALFORMED_RESPONSE, "invalid matrix sample", None, None
                )
    return tuple(samples)


def _parse_sample(
    timestamp: float, raw_value: str
) -> PrometheusSample | CollectionFailure:
    try:
        value = float(raw_value)
    except ValueError:
        return _failure(
            FailureKind.NONFINITE_SAMPLE, "sample value is not a float", None, None
        )
    numeric_timestamp = float(timestamp)
    if not isfinite(numeric_timestamp) or not isfinite(value):
        return _failure(
            FailureKind.NONFINITE_SAMPLE, "sample values must be finite", None, None
        )
    return PrometheusSample(numeric_timestamp, value)


def _failure(
    kind: FailureKind,
    message: str,
    request: QueryProvenance | None,
    response: ResponseProvenance | None,
) -> CollectionFailure:
    return CollectionFailure(kind, message, request, response)
