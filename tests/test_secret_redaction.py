from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
import httpx

from perfcheck.prometheus import (
    CollectionResult,
    CollectionSuccess,
    PrometheusQueryRangeCollector,
    RangeQuery,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    import pytest


_ROOT = Path(__file__).parents[1]
_SERVER = _ROOT / "tests/fixtures/mock_prometheus_server.py"
_PROMETHEUS_FIXTURE = _ROOT / "tests/fixtures/prometheus/matrix.json"


def test_token_echo_fixture_redacts_credentials_from_transport_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a local Prometheus fixture instructed to echo the bearer token.
    secret = "task-12-secret"  # noqa: S105 - deterministic redaction fixture value.
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", secret)
    with _server(secret) as endpoint:
        # When: an actual transport request reaches the hostile echo response.
        async def collect() -> CollectionResult:
            async with httpx.AsyncClient(timeout=5.0) as client:
                return await PrometheusQueryRangeCollector(client).collect(
                    RangeQuery(
                        prometheus_url=endpoint,
                        query="pass_metric",
                        start=datetime(2026, 7, 3, 10, tzinfo=UTC),
                        end=datetime(2026, 7, 3, 10, 10, tzinfo=UTC),
                        step_seconds=15,
                        expected_labels={},
                    )
                )

        result = anyio.run(collect)

    # Then: neither response provenance nor its representation retains the token.
    assert isinstance(result, CollectionSuccess)
    assert secret not in repr(result)
    assert result.response.warnings == ("token=[REDACTED]",)


def test_token_echo_fixture_keeps_collected_artifacts_secret_free(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: the local echo server, fixture policy, and credential-bearing environment.
    secret = "task-12-artifact-secret"  # noqa: S105 - deterministic fixture value.
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", secret)
    output_path = tmp_path / "run.json"
    policy_path = _ROOT / "tests/fixtures/policy-pass.json"
    with _server(secret) as endpoint:
        # When: the CLI writes a collected artifact using the local endpoint.
        result = subprocess.run(  # noqa: S603 - fixed local console script.
            [
                str(Path(sys.executable).parent / "perfcheck"),
                "collect",
                "--suite",
                str(policy_path),
                "--prometheus-url",
                endpoint,
                "--run-id",
                "redacted-run",
                "--start",
                "2026-07-03T10:00:00Z",
                "--end",
                "2026-07-03T10:10:00Z",
                "--out",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            env=os.environ.copy(),
            text=True,
        )

    # Then: the valid artifact and command output cannot disclose the bearer value.
    assert result.returncode == 0
    assert secret not in output_path.read_text(encoding="utf-8")
    assert secret not in result.stderr
    assert json.loads(output_path.read_text(encoding="utf-8"))["artifact_type"] == "run"


@contextmanager
def _server(secret: str) -> Generator[str]:
    process = subprocess.Popen(  # noqa: S603 - fixed local fixture server.
        [
            sys.executable,
            str(_SERVER),
            "--port",
            "0",
            "--fixture",
            str(_PROMETHEUS_FIXTURE),
            "--echo-token-body",
            secret,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    try:
        yield process.stdout.readline().strip()
    finally:
        process.terminate()
        process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()
