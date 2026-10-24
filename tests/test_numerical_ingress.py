from datetime import timedelta

import anyio
import httpx2
import pytest

from perfcheck.prometheus import (
    CollectionFailure,
    CollectionSuccess,
    FailureKind,
    PrometheusQueryRangeCollector,
    RangeQuery,
)
from tests.cli_support import cli_policy, cli_run


@pytest.mark.parametrize(
    ("raw_value", "message"),
    [
        ("not-a-number", "sample value is not a float"),
        ("1e309", "sample values must be finite"),
        ("NaN", "sample values must be finite"),
    ],
)
def test_collector_classifies_invalid_sample_strings(
    raw_value: str, message: str
) -> None:
    # Given: a valid matrix with only its sample string replaced.
    start = cli_run(cli_policy(), 1, 1.0).source_interval.start
    query = RangeQuery(
        prometheus_url="https://metrics.example.test",
        query="latency_seconds",
        start=start,
        end=start + timedelta(minutes=10),
        step_seconds=15,
        expected_labels={},
    )

    def respond(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {"metric": {}, "values": [[start.timestamp(), raw_value]]},
                    ],
                },
            },
        )

    async def collect() -> CollectionSuccess | CollectionFailure:
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(respond),
            timeout=httpx2.Timeout(connect=5, read=30, write=10, pool=10),
        ) as client:
            return await PrometheusQueryRangeCollector(client).collect(query)

    # When: the real collector parses the HTTP-level fake response.
    result = anyio.run(collect)

    # Then: invalid arithmetic strings have a precise safe failure classification.
    assert isinstance(result, CollectionFailure)
    assert result.kind is FailureKind.NONFINITE_SAMPLE
    assert result.message == message
