from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import anyio
import httpx2
import pytest

if TYPE_CHECKING:
    from pydantic import JsonValue

from perfcheck.prometheus import (
    CollectionFailure,
    CollectionResult,
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
    async def collect() -> CollectionResult:
        transport = httpx2.MockTransport(
            lambda _: httpx2.Response(status_code, json=payload)
        )
        async with httpx2.AsyncClient(transport=transport) as client:
            return await PrometheusQueryRangeCollector(client).collect(_query())

    result = anyio.run(collect)
    assert isinstance(result, CollectionFailure)
    return result


def _result_for_bytes(payload: bytes) -> CollectionFailure:
    async def collect() -> CollectionResult:
        transport = httpx2.MockTransport(
            lambda _: httpx2.Response(200, content=payload)
        )
        async with httpx2.AsyncClient(transport=transport) as client:
            return await PrometheusQueryRangeCollector(client).collect(_query())

    result = anyio.run(collect)
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


@pytest.mark.parametrize(
    "payload",
    [
        b'{"status":"success","data":',
        b'{"status":"success"}',
        b'{"status":"success","data":{"resultType":"matrix"}}',
        b'{"status":"success","data":{"resultType":"matrix","result":[{"metric":{"job":"api"},"values":[[1]]}]}}',
    ],
)
def test_collect_classifies_invalid_ingress_shapes_as_malformed_response(
    payload: bytes,
) -> None:
    # Given: invalid JSON or a required Prometheus matrix field is absent.

    # When: raw response bytes cross the collection ingress boundary.
    result = _result_for_bytes(payload)

    # Then: a declared, non-throwing collection failure is retained.
    assert result.kind is FailureKind.MALFORMED_RESPONSE


def test_collect_rejects_unknown_dynamic_label_name() -> None:
    # Given: an upstream series includes a label that policy did not select.
    payload: JsonValue = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"job": "api", "untrusted_label": "value"},
                    "values": [[1, "1"]],
                }
            ],
        },
    }

    # When: the typed dynamic label map is compared with policy.
    result = _result_for(payload)

    # Then: it becomes a typed label-contract failure.
    assert result.kind is FailureKind.UNEXPECTED_LABELS


def test_collect_classifies_http_and_timeout_failures() -> None:
    # Given: explicit HTTP and transport timeout failure responses.
    api_failure = _result_for({"status": "error", "error": "server token=top-secret"})
    http_failure = _result_for(
        {"status": "error", "error": "unavailable"}, status_code=503
    )

    # When: collection encounters them.
    async def collect_timeout() -> CollectionResult:
        transport = httpx2.MockTransport(
            lambda request: (_ for _ in ()).throw(
                httpx2.ReadTimeout("late", request=request)
            )
        )
        async with httpx2.AsyncClient(transport=transport) as client:
            return await PrometheusQueryRangeCollector(client).collect(_query())

    timeout = anyio.run(collect_timeout)

    # Then: both failures are typed and secret-safe.
    assert api_failure.kind is FailureKind.API_ERROR
    assert http_failure.kind is FailureKind.HTTP_ERROR
    assert isinstance(timeout, CollectionFailure)
    assert timeout.kind is FailureKind.TIMEOUT


def test_collect_classifies_connect_failure() -> None:
    # Given: a transport that cannot establish a Prometheus connection.
    async def collect() -> CollectionFailure:
        def handler(request: httpx2.Request) -> httpx2.Response:
            message = "connection refused"
            raise httpx2.ConnectError(message, request=request)

        transport = httpx2.MockTransport(handler)
        async with httpx2.AsyncClient(transport=transport) as client:
            result = await PrometheusQueryRangeCollector(client).collect(_query())
        assert isinstance(result, CollectionFailure)
        return result

    # When: collection attempts the range request.
    result = anyio.run(collect)

    # Then: the connection fault retains the typed transport classification.
    assert result.kind is FailureKind.TRANSPORT
