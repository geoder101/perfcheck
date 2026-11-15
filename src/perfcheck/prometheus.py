"""Injected Prometheus range-query collection API."""

import base64
from datetime import UTC, datetime, timedelta
from typing import Final, assert_never
from urllib.parse import urlsplit, urlunsplit

import httpx2

from perfcheck.collection_auth import AuthConfig, AuthScheme
from perfcheck.prometheus_response import (
    classify_success,
    redact_text,
    response_provenance,
)
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

__all__ = [
    "CollectionFailure",
    "CollectionResult",
    "CollectionSuccess",
    "FailureKind",
    "PrometheusQueryRangeCollector",
    "PrometheusSample",
    "QueryProvenance",
    "RangeQuery",
    "ResponseProvenance",
    "resolve_endpoint",
]

_API_PATH: Final = "/api/v1/query_range"
_DEFAULT_TIMEOUT_SECONDS: Final = 30
_MIN_SUCCESS_STATUS: Final = 200
_MAX_SUCCESS_STATUS: Final = 300


class PrometheusQueryRangeCollector:
    """Collect range matrices through the caller-owned async HTTP client."""

    _client: httpx2.AsyncClient

    def __init__(self, client: httpx2.AsyncClient) -> None:
        """Retain a caller-owned client so tests can inject MockTransport."""
        self._client = client

    async def collect(
        self,
        range_query: RangeQuery,
        *,
        prometheus_url_override: str | None = None,
        auth_config: AuthConfig = AuthConfig.NONE,
    ) -> CollectionResult:
        """Collect and classify one policy metric without local aggregation.

        Authentication is resolved by the caller and passed explicitly; the
        transport never reads environment variables and never serializes the
        resolved configuration. Secrets flow only into redaction.
        """
        selected_url = prometheus_url_override or range_query.prometheus_url
        endpoint = resolve_endpoint(selected_url)
        if endpoint is None:
            return CollectionFailure(
                kind=FailureKind.UNSAFE_ENDPOINT,
                message=(
                    "Prometheus URL must be an HTTP(S) origin or base path without "
                    "credentials, query, or fragment"
                ),
                request=None,
                response=None,
            )
        secrets = _auth_secrets(auth_config)
        request = _build_request_provenance(range_query, endpoint, secrets)
        if request is None:
            return CollectionFailure(
                kind=FailureKind.INVALID_REQUEST,
                message=(
                    "range query requires UTC start/end, positive step, and nonempty "
                    "query"
                ),
                request=None,
                response=None,
            )
        headers = _auth_headers(auth_config)
        try:
            response = await self._client.post(
                endpoint,
                data={
                    "query": range_query.query,
                    "start": request.start,
                    "end": request.end,
                    "step": request.step,
                    "limit": str(request.limit),
                    "timeout": f"{request.timeout_seconds}s",
                },
                headers=headers,
            )
        except httpx2.TimeoutException:
            return CollectionFailure(
                FailureKind.TIMEOUT, "Prometheus request timed out", request, None
            )
        except httpx2.TransportError as error:
            return CollectionFailure(
                FailureKind.TRANSPORT,
                redact_text(str(error), secrets),
                request,
                None,
            )
        parsed_response = response_provenance(response, secrets)
        status_code = parsed_response.provenance.status_code
        if not _MIN_SUCCESS_STATUS <= status_code < _MAX_SUCCESS_STATUS:
            return CollectionFailure(
                FailureKind.HTTP_ERROR,
                f"Prometheus returned HTTP {status_code}",
                request,
                parsed_response.provenance,
            )
        return classify_success(range_query, request, parsed_response)


def resolve_endpoint(raw_url: str) -> str | None:
    """Return the canonical query_range endpoint for a safe base URL."""
    try:
        parts = urlsplit(raw_url)
        hostname = parts.hostname
        _ = parts.port
    except ValueError:
        return None
    if (
        parts.scheme not in {"http", "https"}
        or not parts.netloc
        or hostname is None
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        return None
    base_path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, f"{base_path}{_API_PATH}", "", ""))


def _build_request_provenance(
    query: RangeQuery, endpoint: str, secrets: tuple[str, ...]
) -> QueryProvenance | None:
    """Validate request data at the transport boundary."""
    if (
        not query.query
        or query.start.tzinfo is None
        or query.end.tzinfo is None
        or query.start.utcoffset() != timedelta(0)
        or query.end.utcoffset() != timedelta(0)
        or query.start > query.end
        or query.step_seconds <= 0
    ):
        return None
    return QueryProvenance(
        endpoint=endpoint,
        query=redact_text(query.query, secrets),
        start=_format_utc(query.start),
        end=_format_utc(query.end),
        step=str(query.step_seconds),
        limit=0,
        timeout_seconds=_DEFAULT_TIMEOUT_SECONDS,
    )


def _auth_secrets(auth_config: AuthConfig) -> tuple[str, ...]:
    """Exact secret strings to scrub for the resolved auth scheme.

    Only the fields populated for ``scheme`` are present, so filtering the three
    candidate fields yields ``(token,)`` for bearer, ``(username, password)`` for
    basic, and ``()`` for none.
    """
    return tuple(
        value
        for value in (
            auth_config.bearer_token,
            auth_config.basic_username,
            auth_config.basic_password,
        )
        if value is not None
    )


def _auth_headers(auth_config: AuthConfig) -> dict[str, str]:
    """Build the Authorization header for the resolved auth scheme."""
    match auth_config.scheme:
        case AuthScheme.NONE:
            return {}
        case AuthScheme.BEARER:
            return {"Authorization": f"Bearer {auth_config.bearer_token}"}
        case AuthScheme.BASIC:
            credentials = f"{auth_config.basic_username}:{auth_config.basic_password}"
            encoded = base64.b64encode(credentials.encode("ascii")).decode("ascii")
            return {"Authorization": f"Basic {encoded}"}
        case _:
            assert_never(auth_config.scheme)


def _format_utc(value: datetime) -> str:
    """Serialize an aware timestamp as a Prometheus RFC-3339 UTC instant."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
