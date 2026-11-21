from __future__ import annotations

import http.client
import socket
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import ClassVar, Literal
from urllib.parse import urlencode, urlparse

import pytest
from examples._support import FixtureServerStartupError, mock_prometheus_endpoint
from examples.fixtures.mock_prometheus import LoopbackHTTPServer as ExampleServer
from pydantic import BaseModel, ConfigDict, Field

from tests.fixtures.mock_prometheus_server import LoopbackHTTPServer as SuiteServer

_ROOT = Path(__file__).parents[1]
_FIXTURE = _ROOT / "examples/fixtures/prometheus-matrix.json"


@pytest.mark.parametrize("server_type", [ExampleServer, SuiteServer])
def test_loopback_fixture_binds_without_dns(
    monkeypatch: pytest.MonkeyPatch, server_type: type[ExampleServer | SuiteServer]
) -> None:
    # Given: a runner whose resolver must not be consulted by local fixtures.
    def reject_dns(_name: str) -> str:
        pytest.fail("loopback fixtures must not perform reverse DNS")

    monkeypatch.setattr(socket, "getfqdn", reject_dns)

    # When: a fixture binds its ephemeral numeric loopback address.
    with server_type(("127.0.0.1", 0), BaseHTTPRequestHandler) as server:
        # Then: readiness has a real local port without depending on DNS.
        assert server.server_name == "localhost"
        assert server.server_port > 0


class _MatrixSeries(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    values: tuple[tuple[float, str], ...]


class _MatrixData(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    result_type: Literal["matrix"] = Field(alias="resultType")
    result: tuple[_MatrixSeries, ...]


class _MatrixResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    status: Literal["success"]
    data: _MatrixData


class _ErrorResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    status: Literal["error"]


def test_fixture_server_returns_deterministic_matrix_for_known_query() -> None:
    # Given: the self-contained fixture server and one known query.
    with mock_prometheus_endpoint(_FIXTURE) as endpoint:
        parsed = urlparse(endpoint)
        assert parsed.hostname is not None
        assert parsed.port is not None
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=1)

        # When: the fixed range-query request reaches the loopback fixture.
        connection.request(
            "POST",
            "/api/v1/query_range",
            body=urlencode(
                {"query": "pass_metric", "start": "2026-07-01T10:00:00+00:00"}
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = connection.getresponse()
        payload = _MatrixResponse.model_validate_json(response.read())
        connection.close()

    # Then: the fixture emits the sanitized deterministic Prometheus matrix.
    assert response.status == 200
    assert payload.status == "success"
    assert payload.data.result_type == "matrix"
    assert payload.data.result[0].values == tuple(
        (1782900000.0 + (15 * index), "10.0") for index in range(41)
    )


def test_fixture_server_rejects_unknown_query() -> None:
    # Given: the self-contained fixture server and an unknown query.
    with mock_prometheus_endpoint(_FIXTURE) as endpoint:
        parsed = urlparse(endpoint)
        assert parsed.hostname is not None
        assert parsed.port is not None
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=1)

        # When: the unknown range query is sent.
        connection.request(
            "POST",
            "/api/v1/query_range",
            body=urlencode(
                {"query": "unknown_metric", "start": "2026-07-01T10:00:00+00:00"}
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = connection.getresponse()
        payload = _ErrorResponse.model_validate_json(response.read())
        connection.close()

    # Then: it fails deterministically without echoing request data.
    assert (response.status, payload.status) == (400, "error")


def test_fixture_server_reports_readiness_failure_without_credential_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: a missing fixture and a fake parent bearer token.
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", "fake-bearer-token")

    # When: fixture startup cannot announce readiness before its timeout.
    with (
        pytest.raises(FixtureServerStartupError) as error,
        mock_prometheus_endpoint(tmp_path / "missing.json", readiness_timeout=0.5),
    ):
        pass

    # Then: the stable startup error discloses neither token nor child diagnostics.
    assert "fake-bearer-token" not in str(error.value)
