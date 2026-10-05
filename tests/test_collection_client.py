from __future__ import annotations

from datetime import UTC, datetime

import anyio
import httpx2

from perfcheck.collection_service import create_collection_client
from perfcheck.prometheus import (
    CollectionFailure,
    CollectionSuccess,
    PrometheusQueryRangeCollector,
    RangeQuery,
)


def test_collection_client_enables_transport_defaults() -> None:
    # Given: the production collection client factory.
    async def inspect() -> tuple[
        float | None, float | None, float | None, float | None, bool
    ]:
        async with create_collection_client() as client:
            return (
                client.timeout.connect,
                client.timeout.read,
                client.timeout.write,
                client.timeout.pool,
                client.follow_redirects,
            )

    # When: its concrete HTTP transport is constructed.
    result = anyio.run(inspect)

    # Then: split timeouts and redirects are enabled on the public client contract.
    assert result == (5.0, 30.0, 10.0, 10.0, True)


def test_mock_client_closes_after_collection_success_and_failure() -> None:
    # Given: mock clients for one successful and one transport-failure request.
    async def collect() -> tuple[bool, bool]:
        query = RangeQuery(
            prometheus_url="https://prometheus.example/base",
            query="sum(rate(http_requests_total[1m]))",
            start=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
            end=datetime(2026, 10, 1, 12, 1, tzinfo=UTC),
            step_seconds=15,
            expected_labels={"job": "api"},
        )
        successful_client = httpx2.AsyncClient(
            transport=httpx2.MockTransport(
                lambda _: httpx2.Response(
                    200,
                    json={
                        "status": "success",
                        "data": {
                            "resultType": "matrix",
                            "result": [
                                {
                                    "metric": {"job": "api"},
                                    "values": [
                                        [1760000000, "1.25"],
                                        [1760000015, "1.5"],
                                    ],
                                }
                            ],
                        },
                    },
                )
            )
        )
        failing_client = httpx2.AsyncClient(
            transport=httpx2.MockTransport(
                lambda request: (_ for _ in ()).throw(
                    httpx2.ConnectError("connection refused", request=request)
                )
            )
        )
        async with successful_client:
            successful = await PrometheusQueryRangeCollector(successful_client).collect(
                query
            )
        async with failing_client:
            failed = await PrometheusQueryRangeCollector(failing_client).collect(query)
        assert isinstance(successful, CollectionSuccess)
        assert isinstance(failed, CollectionFailure)
        return successful_client.is_closed, failing_client.is_closed

    # When: both outcomes leave their deterministic context managers.
    closed = anyio.run(collect)

    # Then: neither mock transport client remains open.
    assert closed == (True, True)
