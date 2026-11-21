from __future__ import annotations

import http.client
import socket
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import pytest

from tests.e2e.support import (
    FixtureServerStartupError,
    mock_prometheus_endpoint,
    perfcheck_executable,
)

_ROOT = Path(__file__).parents[2]
_PROMETHEUS_FIXTURE = _ROOT / "tests/fixtures/prometheus/matrix.json"


@pytest.mark.parametrize(
    ("platform", "expected_relative_path"),
    [
        ("posix", Path("bin/perfcheck")),
        ("nt", Path("Scripts/perfcheck.exe")),
    ],
)
def test_perfcheck_executable_uses_generated_platform_layout(
    tmp_path: Path, platform: Literal["nt", "posix"], expected_relative_path: Path
) -> None:
    # Given: a virtual-environment root on a selected supported platform.

    # When: its generated perfcheck executable is resolved.
    executable = perfcheck_executable(tmp_path, platform=platform)

    # Then: it follows the wheel's Unix or Windows console-script layout.
    assert executable == tmp_path / expected_relative_path


def test_mock_prometheus_endpoint_serves_health_then_stops() -> None:
    # Given: the real local Prometheus fixture and an ephemeral listener.
    with mock_prometheus_endpoint(_PROMETHEUS_FIXTURE) as endpoint:
        parsed_endpoint = urlparse(endpoint)
        assert parsed_endpoint.hostname == "127.0.0.1"
        assert parsed_endpoint.port is not None

        # When: its health endpoint is requested while the context is open.
        connection = http.client.HTTPConnection(
            parsed_endpoint.hostname, parsed_endpoint.port, timeout=1
        )
        connection.request("GET", "/healthz")
        response = connection.getresponse()
        _ = response.read()
        connection.close()

        # Then: the fixture responds successfully.
        assert response.status == 200

    # When: the context has completed cleanup.

    # Then: the endpoint no longer accepts connections.
    with (
        pytest.raises(
            ConnectionRefusedError,
            match=r"(?i)(connection refused|actively refused)",
        ),
        socket.create_connection(
            (parsed_endpoint.hostname, parsed_endpoint.port), timeout=5
        ),
    ):
        pass


def test_mock_prometheus_endpoint_includes_stderr_when_startup_fails(
    tmp_path: Path,
) -> None:
    # Given: a fixture path that the subprocess cannot read.

    # When: the fixture server fails before announcing its endpoint.
    with (
        pytest.raises(FixtureServerStartupError) as error,
        mock_prometheus_endpoint(tmp_path / "missing.json"),
    ):
        pass

    # Then: the startup error contains the subprocess diagnostic stream.
    assert "missing.json" in error.value.stderr
