"""Local CLI and wire fixtures for collection failure regressions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import httpx2
from typer.testing import CliRunner

from perfcheck.cli import app
from perfcheck.model_types import MetricId
from perfcheck.policy_models import SuitePolicy
from perfcheck.storage import policy_content_sha256
from tests.cli_support import cli_policy, write_cli_policy

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import pytest
    from pydantic import JsonValue
    from typer.testing import Result

SECRET: Final = "batch-a-bearer-secret"  # noqa: S105 - synthetic redaction fixture.
START: Final = 1767225600


def failure_policy(*, enabled: bool = True) -> SuitePolicy:
    base = cli_policy()
    metric = base.metrics[0]
    initial = SuitePolicy(
        policy_id=base.policy_id,
        suite_id=base.suite_id,
        policy_sha256=base.policy_sha256,
        min_baseline_reference_runs=base.min_baseline_reference_runs,
        prometheus_url="https://metrics.example.test/base",
        metrics=(
            metric,
            metric.model_copy(
                update={
                    "metric_id": MetricId("failed"),
                    "query": "failed_metric",
                    "enabled": enabled,
                }
            ),
        ),
    )
    return initial.model_copy(update={"policy_sha256": policy_content_sha256(initial)})


def matrix_response(values: JsonValue) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [{"metric": {}, "values": values}],
            },
        },
    )


def install_transport(
    monkeypatch: pytest.MonkeyPatch,
    failure: Callable[[httpx2.Request], httpx2.Response],
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["Authorization"] == f"Bearer {SECRET}"
        if b"failed_metric" in request.content:
            return failure(request)
        return matrix_response([[START + 15 * index, "2.5"] for index in range(41)])

    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", SECRET)
    monkeypatch.setattr(
        "perfcheck.collection_service.create_collection_client",
        lambda: httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )


def collect_cli(directory: Path, policy: SuitePolicy) -> Result:
    write_cli_policy(directory / "policy.json", policy)
    return CliRunner().invoke(
        app,
        [
            "collect",
            "--suite",
            str(directory / "policy.json"),
            "--run-id",
            "mixed-run",
            "--start",
            "2026-01-01T00:00:00Z",
            "--end",
            "2026-01-01T00:10:00Z",
            "--out",
            str(directory / "raw.json"),
        ],
    )
