from __future__ import annotations

import base64
from pathlib import Path  # noqa: TC003 - pytest resolves the fixture annotation.
from typing import TYPE_CHECKING, TypedDict

import httpx2
from pydantic import TypeAdapter
from typer.testing import CliRunner

from perfcheck.cli import app
from perfcheck.model_types import Direction, MetricId, MetricUnit, Statistic
from perfcheck.policy_models import MetricPolicy, SuitePolicy
from perfcheck.storage import policy_content_sha256

if TYPE_CHECKING:
    import pytest


class _MetricProvenancePayload(TypedDict):
    endpoint_url: str


class _MetricFailurePayload(TypedDict):
    detail: str
    reason: str


class _MetricRecordPayload(TypedDict):
    availability: str
    failure: _MetricFailurePayload | None
    metric_id: str
    provenance: _MetricProvenancePayload


class _RunPayload(TypedDict):
    artifact_type: str
    metric_records: list[_MetricRecordPayload]


_RUN_PAYLOAD = TypeAdapter(_RunPayload)


def _policy() -> SuitePolicy:
    initial = SuitePolicy(
        policy_id="policy-1",
        suite_id="suite-1",
        policy_sha256="0" * 64,
        prometheus_url="https://suite.example/base",
        min_baseline_reference_runs=1,
        metrics=(
            MetricPolicy(
                metric_id=MetricId("latency"),
                query="latency_seconds",
                unit=MetricUnit.SECONDS,
                direction=Direction.HIGHER_IS_WORSE,
                statistic=Statistic.MEAN,
                practical_threshold=0.0,
                step_seconds=15,
                rate_window_seconds=60,
            ),
            MetricPolicy(
                metric_id=MetricId("errors"),
                query="errors_total",
                unit=MetricUnit.COUNT,
                direction=Direction.HIGHER_IS_WORSE,
                statistic=Statistic.MEAN,
                practical_threshold=0.0,
                step_seconds=15,
                rate_window_seconds=60,
            ),
        ),
    )
    return initial.model_copy(update={"policy_sha256": policy_content_sha256(initial)})


def _write_policy(path: Path, policy: SuitePolicy) -> None:
    _ = path.write_text(policy.model_dump_json(), encoding="utf-8")


def _arguments(policy_path: Path, output_path: Path) -> list[str]:
    return [
        "collect",
        "--policy",
        str(policy_path),
        "--run-id",
        "run-1",
        "--start",
        "2026-01-01T00:00:00Z",
        "--end",
        "2026-01-01T00:01:00Z",
        "--out",
        str(output_path),
    ]


def _success_response() -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [{"metric": {}, "values": [[1767225600, "1.5"]]}],
            },
        },
    )


def _install_transport(
    monkeypatch: pytest.MonkeyPatch,
    requests: list[httpx2.Request],
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return _success_response()

    monkeypatch.setattr(
        "perfcheck.collection_service.create_collection_client",
        lambda: httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )


def test_collect_basic_scheme_without_password_exits_three_without_leaking(
    tmp_path: Path,
) -> None:
    # Given: a basic scheme flag and a credential-shaped username but no password.
    policy_path, output = tmp_path / "policy.json", tmp_path / "run.json"
    _write_policy(policy_path, _policy())

    # When: collect requests basic auth without a password.
    result = CliRunner().invoke(
        app,
        [
            *_arguments(policy_path, output),
            "--prometheus-auth-scheme",
            "basic",
            "--prometheus-auth-basic-user",
            "top-secret-user",
        ],
    )

    # Then: resolution fails with the input exit code and no credential leaks.
    assert result.exit_code == 3
    assert not output.exists()
    assert result.stderr == "error: basic auth requires a password\n"
    assert "top-secret-user" not in result.output


def test_collect_basic_scheme_without_username_keeps_env_password_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: a basic scheme flag and a password in the environment but no username.
    policy_path, output = tmp_path / "policy.json", tmp_path / "run.json"
    _write_policy(policy_path, _policy())
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BASIC_PASSWORD", "secretpass")

    # When: collect requests basic auth without a username.
    result = CliRunner().invoke(
        app,
        [
            *_arguments(policy_path, output),
            "--prometheus-auth-scheme",
            "basic",
        ],
    )

    # Then: resolution fails with the input exit code and the password is not leaked.
    assert result.exit_code == 3
    assert not output.exists()
    assert result.stderr == "error: basic auth requires a username\n"
    assert "secretpass" not in result.output


def test_collect_bearer_is_secret_free_in_artifact_and_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: a bearer token flag and a deterministic Prometheus response.
    policy_path, output = tmp_path / "policy.json", tmp_path / "run.json"
    _write_policy(policy_path, _policy())
    bearer_value = "top-secret-bearer"
    requests: list[httpx2.Request] = []
    _install_transport(monkeypatch, requests)

    # When: collect forwards the bearer token to the transport.
    result = CliRunner().invoke(
        app,
        [
            *_arguments(policy_path, output),
            "--prometheus-bearer-token",
            bearer_value,
        ],
    )

    # Then: the token reaches the wire but never the artifact or CLI output.
    assert result.exit_code == 0
    for request in requests:
        assert request.headers.get("authorization") == f"Bearer {bearer_value}"
    output_text = output.read_text(encoding="utf-8")
    assert bearer_value not in output_text
    assert bearer_value not in result.stdout
    assert bearer_value not in result.stderr


def test_collect_basic_is_secret_free_in_artifact_and_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: basic credentials as flags and a deterministic Prometheus response.
    policy_path, output = tmp_path / "policy.json", tmp_path / "run.json"
    _write_policy(policy_path, _policy())
    username, password = "svc", "top-secret-password"
    requests: list[httpx2.Request] = []
    _install_transport(monkeypatch, requests)

    # When: collect forwards the basic credentials to the transport.
    result = CliRunner().invoke(
        app,
        [
            *_arguments(policy_path, output),
            "--prometheus-auth-scheme",
            "basic",
            "--prometheus-auth-basic-user",
            username,
            "--prometheus-auth-basic-password",
            password,
        ],
    )

    # Then: the credentials reach the wire but never the artifact or CLI output.
    assert result.exit_code == 0
    credentials = f"{username}:{password}"
    expected = "Basic " + base64.b64encode(credentials.encode("ascii")).decode("ascii")
    for request in requests:
        assert request.headers.get("authorization") == expected
    output_text = output.read_text(encoding="utf-8")
    assert password not in output_text
    assert username not in output_text
    assert password not in result.stdout
    assert password not in result.stderr
