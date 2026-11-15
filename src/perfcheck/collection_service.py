"""Bounded conversion of Prometheus query outcomes into portable run evidence."""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Final, assert_never, override

import anyio
import httpx2

from perfcheck.collection_auth import AuthConfig
from perfcheck.collection_models import (
    CollectionFailure,
    FloatSample,
    Label,
    LabelledMetricSeries,
    MetricCollectionRecord,
    QueryProvenance,
    SourceInterval,
)
from perfcheck.errors import PerfcheckError
from perfcheck.model_types import CollectionFailureReason, MetricAvailability, RunId
from perfcheck.prometheus import (
    CollectionFailure as PrometheusCollectionFailure,
)
from perfcheck.prometheus import (
    CollectionSuccess,
    FailureKind,
    PrometheusQueryRangeCollector,
    RangeQuery,
    resolve_endpoint,
)
from perfcheck.run_models import RunArtifact, RunMetadata
from perfcheck.storage import artifact_content_sha256

if TYPE_CHECKING:
    from perfcheck.policy_models import MetricPolicy, SuitePolicy

_MAX_CONCURRENT_REQUESTS: Final = 4
_HTTP_LIMITS: Final = httpx2.Limits(
    max_connections=200,
    max_keepalive_connections=40,
    keepalive_expiry=30.0,
)
_HTTP_TIMEOUT: Final = httpx2.Timeout(connect=5.0, read=30.0, write=10.0, pool=10.0)
_SOCKET_OPTIONS: Final = ((socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),)
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CollectionInputError(PerfcheckError):
    """A collection-specific command input cannot become portable evidence."""

    code: CollectionInputCode

    @override
    def __str__(self) -> str:
        """Render the stable collection input diagnostic."""
        return self.code


class CollectionInputCode(StrEnum):
    """Stable input diagnostics for portable Prometheus collection."""

    INVALID_INTERVAL = "start and end must be RFC-3339 UTC instants"
    INVALID_PROMETHEUS_URL = "invalid Prometheus URL"


async def _log_request(request: httpx2.Request) -> None:
    """Record request metadata without paths, queries, headers, or credentials."""
    _LOGGER.info(
        "Prometheus request method=%s host=%s", request.method, request.url.host
    )


async def _log_response(response: httpx2.Response) -> None:
    """Record response metadata without retaining request-sensitive values."""
    _LOGGER.info(
        "Prometheus response method=%s host=%s status=%s",
        response.request.method,
        response.request.url.host,
        response.status_code,
    )


def create_collection_client() -> httpx2.AsyncClient:
    """Create the caller-owned async client used for the bounded collection run."""
    transport = httpx2.AsyncHTTPTransport(
        http2=True,
        retries=3,
        limits=_HTTP_LIMITS,
        socket_options=_SOCKET_OPTIONS,
    )
    return httpx2.AsyncClient(
        http2=True,
        transport=transport,
        timeout=_HTTP_TIMEOUT,
        limits=_HTTP_LIMITS,
        follow_redirects=True,
        event_hooks={"request": [_log_request], "response": [_log_response]},
    )


async def collect_run(
    policy: SuitePolicy,
    run_id: RunId,
    interval: SourceInterval,
    prometheus_url_override: str | None,
    *,
    auth_config: AuthConfig = AuthConfig.NONE,
) -> RunArtifact:
    """Collect every policy metric and retain partial failures in one valid run.

    The caller supplies the resolved ``AuthConfig``; this function never reads
    environment variables or policy for auth. The resolved configuration is
    forwarded to the transport only and is never serialized into the run
    artifact, provenance, or logs.
    """
    selected_url = prometheus_url_override or policy.prometheus_url
    if selected_url is None or resolve_endpoint(selected_url) is None:
        raise CollectionInputError(CollectionInputCode.INVALID_PROMETHEUS_URL)
    records: list[MetricCollectionRecord | None] = [None] * len(policy.metrics)
    limiter = anyio.CapacityLimiter(_MAX_CONCURRENT_REQUESTS)
    async with create_collection_client() as client:
        collector = PrometheusQueryRangeCollector(client)

        async def collect_metric(index: int, metric: MetricPolicy) -> None:
            async with limiter:
                result = await collector.collect(
                    RangeQuery(
                        prometheus_url=selected_url,
                        query=metric.query,
                        start=interval.start,
                        end=interval.end,
                        step_seconds=metric.step_seconds,
                        expected_labels={},
                        expected_label_names=metric.expected_label_names,
                    ),
                    auth_config=auth_config,
                )
            records[index] = _record(metric, interval, selected_url, result)

        async with anyio.create_task_group() as task_group:
            for index, metric in enumerate(policy.metrics):
                _ = task_group.start_soon(collect_metric, index, metric)
    metric_records = tuple(record for record in records if record is not None)
    initial = RunArtifact(
        content_sha256="0" * 64,
        run_id=run_id,
        suite_id=policy.suite_id,
        source_interval=interval,
        policy_sha256=policy.policy_sha256,
        policy_snapshot=policy,
        metadata=RunMetadata(
            test_name=policy.policy_id,
            git_sha="unknown",
            environment="unknown",
            scenario="prometheus-collection",
            target_topology="unknown",
        ),
        metric_records=metric_records,
    )
    return initial.model_copy(
        update={"content_sha256": artifact_content_sha256(initial)}
    )


def has_enabled_failure(policy: SuitePolicy, run: RunArtifact) -> bool:
    """Report whether an enabled metric was retained as unavailable."""
    enabled_metrics = {metric.metric_id for metric in policy.metrics if metric.enabled}
    return any(
        record.metric_id in enabled_metrics
        and record.availability is MetricAvailability.UNAVAILABLE
        for record in run.metric_records
    )


def _record(
    metric: MetricPolicy,
    interval: SourceInterval,
    endpoint_url: str,
    result: CollectionSuccess | PrometheusCollectionFailure,
) -> MetricCollectionRecord:
    match result:
        case CollectionSuccess() as success:
            try:
                series = LabelledMetricSeries(
                    metric_id=metric.metric_id,
                    labels=tuple(
                        Label(name=name, value=value)
                        for name, value in sorted(success.labels.items())
                    ),
                    samples=tuple(
                        FloatSample(
                            timestamp=datetime.fromtimestamp(sample.timestamp, UTC),
                            value=sample.value,
                        )
                        for sample in success.samples
                    ),
                )
            except ValueError, OverflowError, OSError:
                kind = (
                    FailureKind.MALFORMED_RESPONSE
                    if success.samples
                    else FailureKind.EMPTY_SERIES
                )
                return _record(
                    metric,
                    interval,
                    endpoint_url,
                    PrometheusCollectionFailure(
                        kind,
                        "matrix cannot form raw evidence",
                        success.request,
                        success.response,
                    ),
                )
            return MetricCollectionRecord(
                metric_id=metric.metric_id,
                availability=MetricAvailability.AVAILABLE,
                provenance=_provenance(metric, interval, endpoint_url, success),
                series=series,
            )
        case PrometheusCollectionFailure() as failure:
            return MetricCollectionRecord(
                metric_id=metric.metric_id,
                availability=MetricAvailability.UNAVAILABLE,
                provenance=_provenance(metric, interval, endpoint_url, failure),
                failure=CollectionFailure(
                    reason=_failure_reason(failure.kind),
                    detail=f"Prometheus collection failed: {failure.kind}",
                ),
            )
        case _:
            assert_never(result)


def _provenance(
    metric: MetricPolicy,
    interval: SourceInterval,
    endpoint_url: str,
    result: CollectionSuccess | PrometheusCollectionFailure,
) -> QueryProvenance:
    response = result.response
    return QueryProvenance(
        endpoint_url=endpoint_url,
        query=metric.query,
        start=interval.start,
        end=interval.end,
        step_seconds=metric.step_seconds,
        http_status=response.status_code if response is not None else None,
    )


def _failure_reason(kind: FailureKind) -> CollectionFailureReason:
    reason = CollectionFailureReason.INVALID_RESPONSE
    match kind:
        case FailureKind.TIMEOUT:
            reason = CollectionFailureReason.TIMEOUT
        case FailureKind.TRANSPORT | FailureKind.HTTP_ERROR:
            reason = CollectionFailureReason.TRANSPORT_ERROR
        case FailureKind.EMPTY_SERIES:
            reason = CollectionFailureReason.NO_SERIES
        case FailureKind.MULTIPLE_SERIES:
            reason = CollectionFailureReason.MULTIPLE_SERIES
        case FailureKind.UNEXPECTED_LABELS:
            reason = CollectionFailureReason.UNEXPECTED_LABELS
        case FailureKind.NONFINITE_SAMPLE:
            reason = CollectionFailureReason.NONFINITE_VALUE
        case (
            FailureKind.UNSAFE_ENDPOINT
            | FailureKind.INVALID_REQUEST
            | FailureKind.API_ERROR
            | FailureKind.MALFORMED_RESPONSE
            | FailureKind.RESULT_TYPE
            | FailureKind.HISTOGRAM_SAMPLE
            | FailureKind.DUPLICATE_TIMESTAMP
        ):
            pass
        case _:
            assert_never(kind)
    return reason
