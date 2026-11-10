from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import anyio

from perfcheck.collection_service import create_collection_client
from perfcheck.prometheus import (
    CollectionResult,
    CollectionSuccess,
    PrometheusQueryRangeCollector,
    RangeQuery,
)
from tests.e2e.support import mock_prometheus_endpoint, perfcheck_executable

if TYPE_CHECKING:
    import pytest


_ROOT = Path(__file__).parents[1]
_PROMETHEUS_FIXTURE = _ROOT / "tests/fixtures/prometheus/matrix.json"
_CREDENTIAL = "unsafe-bearer-value"


def test_token_echo_fixture_redacts_credentials_from_transport_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a local Prometheus fixture instructed to echo the bearer token.
    secret = _CREDENTIAL
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", secret)
    with mock_prometheus_endpoint(
        _PROMETHEUS_FIXTURE, echo_token_body=secret
    ) as endpoint:
        # When: an actual transport request reaches the hostile echo response.
        async def collect() -> CollectionResult:
            async with create_collection_client() as client:
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
    assert result.response.warnings == ("api_key=[REDACTED]",)
    assert result.response.infos == ("x-api-key=[REDACTED]",)


def test_token_echo_fixture_keeps_collected_artifacts_secret_free(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: the local echo server, fixture policy, and credential-bearing environment.
    secret = _CREDENTIAL
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", secret)
    output_path = tmp_path / "run.json"
    baseline_path = tmp_path / "baseline.json"
    report_json_path = tmp_path / "report.json"
    report_markdown_path = tmp_path / "report.md"
    policy_path = _ROOT / "tests/fixtures/policy-pass.json"
    console = perfcheck_executable(Path(sys.executable).parent.parent)
    with mock_prometheus_endpoint(
        _PROMETHEUS_FIXTURE, echo_token_body=secret
    ) as endpoint:
        # When: the CLI writes a collected artifact using the local endpoint.
        result = subprocess.run(  # noqa: S603 - fixed local console script.
            [
                str(console),
                "collect",
                "--policy",
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
            encoding="utf-8",
        )
        baseline_result = subprocess.run(  # noqa: S603 - fixed local console script.
            [
                str(console),
                "collect",
                "--policy",
                str(policy_path),
                "--prometheus-url",
                endpoint,
                "--run-id",
                "redacted-baseline",
                "--start",
                "2026-07-03T10:00:00Z",
                "--end",
                "2026-07-03T10:10:00Z",
                "--out",
                str(baseline_path),
            ],
            check=False,
            capture_output=True,
            env=os.environ.copy(),
            text=True,
            encoding="utf-8",
        )

    compare_result = subprocess.run(  # noqa: S603 - fixed local console script.
        [
            str(console),
            "compare",
            "--policy",
            str(policy_path),
            "--current",
            str(output_path),
            "--baseline",
            str(baseline_path),
            "--report-json",
            str(report_json_path),
            "--report-md",
            str(report_markdown_path),
        ],
        check=False,
        capture_output=True,
        env=os.environ.copy(),
        text=True,
        encoding="utf-8",
    )

    # Then: artifact and command streams cannot disclose the bearer value.
    assert result.returncode == 0
    assert baseline_result.returncode == 0
    assert compare_result.returncode == 2
    evidence = (
        output_path.read_text(encoding="utf-8"),
        baseline_path.read_text(encoding="utf-8"),
        report_json_path.read_text(encoding="utf-8"),
        report_markdown_path.read_text(encoding="utf-8"),
        result.stdout,
        result.stderr,
        compare_result.stdout,
        compare_result.stderr,
    )
    assert all(secret not in value for value in evidence)
    assert json.loads(output_path.read_text(encoding="utf-8"))["artifact_type"] == "run"
