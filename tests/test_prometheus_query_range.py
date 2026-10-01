from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING

import anyio
import httpx

if TYPE_CHECKING:
    import pytest

from perfcheck.prometheus import (
    CollectionFailure,
    CollectionSuccess,
    FailureKind,
    PrometheusQueryRangeCollector,
    RangeQuery,
)


def _query(*, url: str = "https://prometheus.example/base") -> RangeQuery:
    return RangeQuery(
        prometheus_url=url,
        query="sum(rate(http_requests_total[1m]))",
        start=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        end=datetime(2026, 10, 1, 12, 1, tzinfo=UTC),
        step_seconds=15,
        expected_labels={"job": "api"},
    )


def _response() -> dict[str, object]:
    return {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"job": "api"},
                    "values": [[1760000000, "1.25"], [1760000015, "1.5"]],
                }
            ],
        },
    }


def test_collect_posts_complete_form_to_base_path_endpoint() -> None:
    # Given: a mock-only Prometheus transport and a base-path URL.
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://prometheus.example/base/api/v1/query_range"
        assert request.headers["content-type"] == "application/x-www-form-urlencoded"
        assert request.extensions["timeout"]["read"] == 30
        assert request.content == (
            b"query=sum%28rate%28http_requests_total%5B1m%5D%29%29"
            b"&start=2026-10-01T12%3A00%3A00Z&end=2026-10-01T12%3A01%3A00Z"
            b"&step=15&limit=0&timeout=30s"
        )
        return httpx.Response(200, json=_response())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    collector = PrometheusQueryRangeCollector(client)

    # When: a matrix is collected.
    result = anyio.run(lambda: collector.collect(_query()))

    # Then: complete, typed series evidence is retained.
    assert isinstance(result, CollectionSuccess)
    assert result.request.timeout_seconds == 30
    assert result.cardinality == 1
    assert result.samples[0].value == 1.25


def test_collect_uses_override_url_and_bearer_token_without_retaining_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: an override endpoint, bearer token, and hostile echo response.
    credential = "unsafe-bearer-value"
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", credential)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://override.example/p/api/v1/query_range"
        assert request.headers["authorization"] == f"Bearer {credential}"
        body = _response()
        body["warnings"] = [f"token={credential}"]
        body["diagnostics"] = {"authorization": credential, "nested": [credential]}
        return httpx.Response(200, json=body)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    collector = PrometheusQueryRangeCollector(client)

    # When: the override is supplied.
    result = anyio.run(
        lambda: collector.collect(
            _query(url="https://suite.example"),
            prometheus_url_override="https://override.example/p",
        )
    )

    # Then: all persisted evidence is recursively token-safe.
    assert isinstance(result, CollectionSuccess)
    assert credential not in repr(result)
    match result.response.body:
        case {"diagnostics": {"[REDACTED]": str() as authorization}}:
            assert authorization == "[REDACTED]"
        case _:
            raise AssertionError
    assert result.response.warnings == ("token=[REDACTED]",)


def test_collect_redacts_bearer_value_from_query_provenance_and_hostile_json_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a bearer value echoed through the query and an untrusted JSON key.
    credential = "query-provenance-credential"
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", credential)

    def handler(_: httpx.Request) -> httpx.Response:
        body = _response()
        body[credential] = {"nested": credential}
        return httpx.Response(200, json=body)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    collector = PrometheusQueryRangeCollector(client)
    query = _query()
    query = RangeQuery(
        prometheus_url=query.prometheus_url,
        query=f'{query.query}{{credential="{credential}"}}',
        start=query.start,
        end=query.end,
        step_seconds=query.step_seconds,
        expected_labels=query.expected_labels,
    )

    # When: collection retains request and response provenance.
    result = anyio.run(lambda: collector.collect(query))

    # Then: neither secret-bearing values nor hostile keys survive evidence.
    assert isinstance(result, CollectionSuccess)
    assert credential not in repr(result)
    assert "[REDACTED]" in result.request.query
    match result.response.body:
        case {"[REDACTED]": {"nested": "[REDACTED]"}}:
            pass
        case _:
            raise AssertionError


def test_collect_rejects_unsafe_endpoint_before_transport() -> None:
    # Given: URLs that cannot safely become an API endpoint.
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: _unexpected()))
    collector = PrometheusQueryRangeCollector(client)

    # When: URL resolution sees malformed authorities, userinfo, a query, or a fragment.
    results = tuple(
        anyio.run(lambda url=url: collector.collect(_query(url=url)))
        for url in (
            "https://:443",
            "https://[malformed",
            "https://user:pass@prometheus.example",
            "https://prometheus.example?token=secret",
            "https://prometheus.example#fragment",
        )
    )

    # Then: every result is a typed configuration failure.
    for result in results:
        assert isinstance(result, CollectionFailure)
        assert result.kind is FailureKind.UNSAFE_ENDPOINT


def test_collect_rejects_non_utc_timestamps_before_transport() -> None:
    # Given: an otherwise-valid request with a non-UTC time zone.
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: _unexpected()))
    collector = PrometheusQueryRangeCollector(client)
    non_utc = timezone(timedelta(hours=2))
    query = RangeQuery(
        prometheus_url="https://prometheus.example",
        query="up",
        start=datetime(2026, 10, 1, 12, 0, tzinfo=non_utc),
        end=datetime(2026, 10, 1, 12, 1, tzinfo=non_utc),
        step_seconds=15,
        expected_labels={"job": "api"},
    )

    # When: collection validates its UTC request boundary.
    result = anyio.run(lambda: collector.collect(query))

    # Then: no transport runs and the result is typed.
    assert isinstance(result, CollectionFailure)
    assert result.kind is FailureKind.INVALID_REQUEST


def _unexpected() -> httpx.Response:
    raise AssertionError
