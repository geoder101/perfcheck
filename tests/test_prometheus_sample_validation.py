from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import anyio
import httpx
import pytest

if TYPE_CHECKING:
    from pydantic import JsonValue

from perfcheck.prometheus import (
    CollectionFailure,
    FailureKind,
    PrometheusQueryRangeCollector,
    RangeQuery,
)


def _query() -> RangeQuery:
    return RangeQuery(
        prometheus_url="https://prometheus.example",
        query="up",
        start=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        end=datetime(2026, 10, 1, 12, 1, tzinfo=UTC),
        step_seconds=15,
        expected_labels={"job": "api"},
    )


def _result_for(payload: JsonValue, *, status_code: int = 200) -> CollectionFailure:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(status_code, json=payload)
        )
    )
    result = anyio.run(lambda: PrometheusQueryRangeCollector(client).collect(_query()))
    assert isinstance(result, CollectionFailure)
    return result


_INVALID_MATRIX_CASES: tuple[tuple[JsonValue, FailureKind], ...] = (
    (
        {"status": "success", "data": {"resultType": "vector", "result": []}},
        FailureKind.RESULT_TYPE,
    ),
    (
        {"status": "success", "data": {"resultType": "string", "result": []}},
        FailureKind.RESULT_TYPE,
    ),
    (
        {"status": "success", "data": {"resultType": "matrix", "result": []}},
        FailureKind.EMPTY_SERIES,
    ),
    (
        {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {"metric": {"job": "api"}, "values": [[1, "1"]]},
                    {"metric": {"job": "api"}, "values": [[1, "1"]]},
                ],
            },
        },
        FailureKind.MULTIPLE_SERIES,
    ),
    (
        {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [{"metric": {"job": "other"}, "values": [[1, "1"]]}],
            },
        },
        FailureKind.UNEXPECTED_LABELS,
    ),
    (
        {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"job": "api"},
                        "histograms": [[1, {}]],
                        "values": [],
                    }
                ],
            },
        },
        FailureKind.HISTOGRAM_SAMPLE,
    ),
    (
        {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [{"metric": {"job": "api"}, "values": [[1, "NaN"]]}],
            },
        },
        FailureKind.NONFINITE_SAMPLE,
    ),
    (
        {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [{"metric": {"job": "api"}, "values": [[1]]}],
            },
        },
        FailureKind.MALFORMED_RESPONSE,
    ),
    (
        {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [{"metric": {"job": "api"}, "values": [[1, "1"], [1, "2"]]}],
            },
        },
        FailureKind.DUPLICATE_TIMESTAMP,
    ),
    (
        {"status": "error", "errorType": "bad_data", "error": "bad query"},
        FailureKind.API_ERROR,
    ),
)


@pytest.mark.parametrize(
    ("payload", "kind"),
    _INVALID_MATRIX_CASES,
)
def test_collect_classifies_invalid_matrix_evidence(
    payload: JsonValue, kind: FailureKind
) -> None:
    # Given: a malformed or unsupported Prometheus payload.

    # When: collection parses the payload.
    result = _result_for(payload)

    # Then: it retains a precise typed failure rather than selecting data.
    assert result.kind is kind


def test_collect_classifies_http_and_timeout_failures() -> None:
    # Given: explicit HTTP and transport timeout failure responses.
    api_failure = _result_for({"status": "error", "error": "server token=top-secret"})
    http_failure = _result_for(
        {"status": "error", "error": "unavailable"}, status_code=503
    )
    timeout_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(
                httpx.ReadTimeout("late", request=request)
            )
        )
    )

    # When: collection encounters them.
    timeout = anyio.run(
        lambda: PrometheusQueryRangeCollector(timeout_client).collect(_query())
    )

    # Then: both failures are typed and secret-safe.
    assert api_failure.kind is FailureKind.API_ERROR
    assert http_failure.kind is FailureKind.HTTP_ERROR
    assert isinstance(timeout, CollectionFailure)
    assert timeout.kind is FailureKind.TIMEOUT
