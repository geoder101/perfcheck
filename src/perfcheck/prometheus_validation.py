"""Matrix evidence validation after Prometheus ingress parsing."""

from __future__ import annotations

from math import isfinite
from typing import TYPE_CHECKING, assert_never

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

if TYPE_CHECKING:
    from perfcheck.prometheus_ingress import (
        MatrixSampleIngress,
        MatrixSeriesIngress,
        ParsedResponse,
        PrometheusEnvelopeIngress,
    )


def classify_success(
    query: RangeQuery, request: QueryProvenance, parsed: ParsedResponse
) -> CollectionResult:
    """Classify a validated Prometheus envelope into collection evidence."""
    if parsed.envelope is None:
        return _failure(
            FailureKind.MALFORMED_RESPONSE,
            "invalid Prometheus response structure",
            request,
            parsed.provenance,
        )
    match parsed.envelope.status:
        case "error":
            return _failure(
                FailureKind.API_ERROR,
                "Prometheus API returned an error",
                request,
                parsed.provenance,
            )
        case "success":
            return _classify_matrix(query, request, parsed.provenance, parsed.envelope)
        case _:
            assert_never(parsed.envelope.status)


def _classify_matrix(
    query: RangeQuery,
    request: QueryProvenance,
    response: ResponseProvenance,
    envelope: PrometheusEnvelopeIngress,
) -> CollectionResult:
    """Validate cardinality, policy labels, and samples from one matrix."""
    data = envelope.data
    if data is None:
        return _failure(
            FailureKind.MALFORMED_RESPONSE,
            "successful Prometheus response is missing matrix data",
            request,
            response,
        )
    if data.result_type != "matrix":
        return _failure(
            FailureKind.RESULT_TYPE, "expected matrix result type", request, response
        )
    if not data.result:
        return _failure(
            FailureKind.EMPTY_SERIES,
            "matrix returned zero series",
            request,
            response,
        )
    if len(data.result) == 1:
        return _validate_single_series(query, request, response, data.result[0])
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
    series: MatrixSeriesIngress,
) -> CollectionResult:
    """Enforce the policy label contract and finite, unique matrix samples."""
    expected_names = query.expected_label_names
    labels_are_valid = (
        tuple(sorted(series.metric)) == expected_names
        if expected_names is not None
        else series.metric == dict(query.expected_labels)
    )
    if not labels_are_valid:
        return _failure(
            FailureKind.UNEXPECTED_LABELS,
            "matrix labels differ from policy",
            request,
            response,
        )
    if series.histograms:
        return _failure(
            FailureKind.HISTOGRAM_SAMPLE,
            "matrix contains native histograms",
            request,
            response,
        )
    samples = _validate_samples(series.values)
    match samples:
        case CollectionFailure(kind=kind, message=message):
            return _failure(kind, message, request, response)
        case tuple() as validated_samples:
            return CollectionSuccess(
                request, response, series.metric, validated_samples, 1
            )
        case _:
            assert_never(samples)


def _validate_samples(
    values: tuple[MatrixSampleIngress, ...],
) -> tuple[PrometheusSample, ...] | CollectionFailure:
    samples: list[PrometheusSample] = []
    timestamps: set[float] = set()
    for raw_sample in values:
        timestamp, raw_value = raw_sample.root
        sample = _parse_sample(timestamp, raw_value)
        match sample:
            case CollectionFailure():
                return sample
            case PrometheusSample(timestamp=sample_timestamp):
                if sample_timestamp in timestamps:
                    return _failure(
                        FailureKind.DUPLICATE_TIMESTAMP,
                        "duplicate sample timestamp",
                        None,
                        None,
                    )
                timestamps.add(sample_timestamp)
                samples.append(sample)
            case _:
                assert_never(sample)
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
