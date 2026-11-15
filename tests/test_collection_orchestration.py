from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import parse_qs

import anyio
import httpx2
import pytest

from perfcheck import collection_service
from perfcheck.collection_auth import AuthConfig, AuthScheme
from perfcheck.collection_models import SourceInterval
from perfcheck.model_types import (
    CollectionFailureReason,
    Direction,
    MetricAvailability,
    MetricId,
    MetricUnit,
    RunId,
    Statistic,
)
from perfcheck.policy_models import MetricPolicy, SuitePolicy

if TYPE_CHECKING:
    from perfcheck.run_models import RunArtifact


def policy(count: int) -> SuitePolicy:
    return SuitePolicy(
        policy_id="orchestration",
        suite_id="orchestration",
        policy_sha256="a" * 64,
        prometheus_url="https://prometheus.example",
        metrics=tuple(
            MetricPolicy(
                metric_id=MetricId(f"metric_{index}"),
                query=f"metric_{index}",
                unit=MetricUnit.MILLISECONDS,
                direction=Direction.HIGHER_IS_WORSE,
                statistic=Statistic.MEAN,
                practical_threshold=5.0,
                step_seconds=15,
                rate_window_seconds=60,
            )
            for index in range(count)
        ),
    )


def interval() -> SourceInterval:
    start = datetime(2026, 10, 1, tzinfo=UTC)
    return SourceInterval(start=start, end=start + timedelta(minutes=1))


def assert_records(run: RunArtifact, suite: SuitePolicy, partial_failure: bool) -> None:
    assert tuple(record.metric_id for record in run.metric_records) == tuple(
        metric.metric_id for metric in suite.metrics
    )
    for index, record in enumerate(run.metric_records):
        assert record.provenance.query == suite.metrics[index].query
        if partial_failure and index == 2:
            assert record.availability is MetricAvailability.UNAVAILABLE
            assert record.failure is not None
            assert record.failure.reason is CollectionFailureReason.TRANSPORT_ERROR
            assert record.provenance.http_status == 503
        else:
            assert record.availability is MetricAvailability.AVAILABLE
            assert record.series is not None
            assert record.series.samples[0].value == float(index + 1)


@pytest.fixture
def factory_clients(monkeypatch: pytest.MonkeyPatch) -> list[httpx2.AsyncClient]:
    clients: list[httpx2.AsyncClient] = []
    factory = collection_service.create_collection_client

    def tracked_factory() -> httpx2.AsyncClient:
        client = factory()
        clients.append(client)
        return client

    monkeypatch.setattr(collection_service, "create_collection_client", tracked_factory)
    return clients


@pytest.mark.parametrize("partial_failure", [False, True])
def test_collect_run_bounds_overlap_and_preserves_policy_order(
    monkeypatch: pytest.MonkeyPatch,
    factory_clients: list[httpx2.AsyncClient],
    partial_failure: bool,
) -> None:
    # Given: seven requests, more than the source's current four-request limit.
    suite = policy(7)
    bounds = interval()

    async def scenario() -> None:
        releases = [anyio.Event() for _ in suite.metrics]
        finished = [anyio.Event() for _ in suite.metrics]
        saturated = anyio.Event()
        active: set[int] = set()
        completed: list[int] = []
        peak = 0

        async def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal peak
            query = parse_qs(request.content.decode())["query"][0]
            index = int(query.removeprefix("metric_"))
            active.add(index)
            peak = max(peak, len(active))
            if len(active) >= 4:
                saturated.set()
            try:
                await releases[index].wait()
                if partial_failure and index == 2:
                    return httpx2.Response(503)
                return httpx2.Response(
                    200,
                    json={
                        "status": "success",
                        "data": {
                            "resultType": "matrix",
                            "result": [
                                {
                                    "metric": {},
                                    "values": [
                                        [bounds.start.timestamp(), str(index + 1)]
                                    ],
                                }
                            ],
                        },
                    },
                )
            finally:
                active.remove(index)
                completed.append(index)
                finished[index].set()

        transport = httpx2.MockTransport(respond)

        async def send(
            self: httpx2.AsyncHTTPTransport, request: httpx2.Request
        ) -> httpx2.Response:
            del self
            return await transport.handle_async_request(request)

        monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", send)

        async def release_out_of_order() -> None:
            await saturated.wait()
            for _ in suite.metrics:
                # Quiescence proves queued tasks had a chance to exceed the bound.
                await anyio.wait_all_tasks_blocked()
                assert len(active) <= 4
                index = max(active)
                releases[index].set()
                await finished[index].wait()

        # When: requests finish in an explicitly controlled non-policy order.
        run: RunArtifact | None = None
        with anyio.fail_after(5):
            async with transport, anyio.create_task_group() as tasks:
                _ = tasks.start_soon(release_out_of_order)
                run = await collection_service.collect_run(
                    suite, RunId("bounded-run"), bounds, None
                )

        # Then: overlap reaches exactly four and every result retains its identity.
        assert peak == 4
        assert sorted(completed) == list(range(7))
        assert completed != list(range(7))
        assert run is not None
        assert_records(run, suite, partial_failure)

    anyio.run(scenario)
    assert len(factory_clients) == 1
    assert factory_clients[0].is_closed


class TransportCrashError(RuntimeError):
    pass


def test_collect_run_closes_factory_client_when_a_worker_raises(
    monkeypatch: pytest.MonkeyPatch,
    factory_clients: list[httpx2.AsyncClient],
) -> None:
    # Given: a crashing worker and an in-flight sibling needing cancellation.
    async def scenario() -> None:
        sibling_entered = anyio.Event()
        sibling_exited = anyio.Event()
        release = anyio.Event()

        async def respond(request: httpx2.Request) -> httpx2.Response:
            query = parse_qs(request.content.decode())["query"][0]
            if query == "metric_0":
                await sibling_entered.wait()
                raise TransportCrashError
            sibling_entered.set()
            try:
                await release.wait()
                pytest.fail("sibling must be cancelled, not released")
            finally:
                sibling_exited.set()

        async with httpx2.MockTransport(respond) as transport:

            async def send(
                self: httpx2.AsyncHTTPTransport, request: httpx2.Request
            ) -> httpx2.Response:
                del self
                return await transport.handle_async_request(request)

            monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", send)

            # When: a transport exception escapes the collection classification.
            with anyio.fail_after(5), pytest.raises(ExceptionGroup) as raised:
                _ = await collection_service.collect_run(
                    policy(2), RunId("crashed-run"), interval(), None
                )

        # Then: the actual crash propagates and the sibling has finished cleanup.
        assert len(raised.value.exceptions) == 1
        assert isinstance(raised.value.exceptions[0], TransportCrashError)
        assert sibling_exited.is_set()

    anyio.run(scenario)
    assert len(factory_clients) == 1
    assert factory_clients[0].is_closed


def test_collect_run_forwards_resolved_auth_config_to_transport(
    monkeypatch: pytest.MonkeyPatch,
    factory_clients: list[httpx2.AsyncClient],
) -> None:
    # Given: a resolved bearer configuration supplied by the caller and a
    # transport that records the Authorization header it receives.
    suite = policy(1)
    captured: dict[str, str] = {}

    async def scenario() -> None:
        async def respond(request: httpx2.Request) -> httpx2.Response:
            captured["authorization"] = request.headers.get("authorization", "")
            return httpx2.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "resultType": "matrix",
                        "result": [
                            {
                                "metric": {},
                                "values": [[interval().start.timestamp(), "1"]],
                            }
                        ],
                    },
                },
            )

        async def send(
            self: httpx2.AsyncHTTPTransport, request: httpx2.Request
        ) -> httpx2.Response:
            del self
            return await httpx2.MockTransport(respond).handle_async_request(request)

        monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", send)

        # When: collect_run is invoked with a non-default resolved config.
        run = await collection_service.collect_run(
            suite,
            RunId("auth-run"),
            interval(),
            None,
            auth_config=AuthConfig(AuthScheme.BEARER, bearer_token="tok"),  # noqa: S106
        )

        # Then: the transport authenticated with the resolved bearer config.
        assert run is not None
        assert captured["authorization"] == "Bearer tok"
        assert_records(run, suite, partial_failure=False)

    anyio.run(scenario)
    assert len(factory_clients) == 1
    assert factory_clients[0].is_closed
