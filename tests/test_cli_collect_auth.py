from __future__ import annotations

import base64
from pathlib import Path  # noqa: TC003 - pytest resolves the fixture annotation.
from typing import TypedDict

import httpx2
import pytest
from click import unstyle
from pydantic import TypeAdapter
from typer.testing import CliRunner

from perfcheck.cli import app
from perfcheck.model_types import Direction, MetricId, MetricUnit, Statistic
from perfcheck.policy_models import MetricPolicy, SuitePolicy
from perfcheck.storage import policy_content_sha256


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


def _assert_basic_header(requests: list[httpx2.Request], expected: str) -> None:
    assert len(requests) == 2
    for request in requests:
        assert request.headers.get("authorization") == expected


def test_collect_help_lists_auth_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the collect command with its documented auth flags and a wide terminal.
    monkeypatch.setenv("COLUMNS", "200")

    # When: collect help is requested.
    result = CliRunner().invoke(app, ["collect", "--help"])

    # Then: all four auth options are listed with their full names.
    assert result.exit_code == 0
    for option in (
        "--prometheus-auth-scheme",
        "--prometheus-bearer-token",
        "--prometheus-auth-basic-user",
        "--prometheus-auth-basic-password",
    ):
        assert option in unstyle(result.output)


def test_collect_flag_wins_over_env_for_bearer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: a bearer token in the environment and a different flag value.
    policy_path, output = tmp_path / "policy.json", tmp_path / "run.json"
    _write_policy(policy_path, _policy())
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", "env-token")
    requests: list[httpx2.Request] = []
    _install_transport(monkeypatch, requests)

    # When: collect receives both the env var and the flag.
    result = CliRunner().invoke(
        app,
        [
            *_arguments(policy_path, output),
            "--prometheus-bearer-token",
            "flag-token",
        ],
    )

    # Then: the flag wins and the outgoing header carries the flag value only.
    assert result.exit_code == 0
    _assert_basic_header(requests, "Bearer flag-token")


def test_collect_env_fallback_for_bearer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: a bearer token in the environment and no flag.
    policy_path, output = tmp_path / "policy.json", tmp_path / "run.json"
    _write_policy(policy_path, _policy())
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", "env-token")
    requests: list[httpx2.Request] = []
    _install_transport(monkeypatch, requests)

    # When: collect runs with only the env var set.
    result = CliRunner().invoke(app, _arguments(policy_path, output))

    # Then: the env token is forwarded as the Authorization header.
    assert result.exit_code == 0
    _assert_basic_header(requests, "Bearer env-token")


@pytest.mark.parametrize("password", ["s3cret", "123£"])
def test_collect_basic_env_vars_resolve(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, password: str
) -> None:
    # Given: basic auth credentials in the environment.
    policy_path, output = tmp_path / "policy.json", tmp_path / "run.json"
    _write_policy(policy_path, _policy())
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_AUTH_SCHEME", "basic")
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BASIC_USERNAME", "svc")
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BASIC_PASSWORD", password)
    requests: list[httpx2.Request] = []
    _install_transport(monkeypatch, requests)

    # When: collect runs with only the env vars set.
    result = CliRunner().invoke(app, _arguments(policy_path, output))

    # Then: the resolved Basic header encodes the env username and password.
    assert result.exit_code == 0
    expected = "Basic " + base64.b64encode(f"svc:{password}".encode()).decode("ascii")
    _assert_basic_header(requests, expected)


def test_collect_basic_flags_resolve(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: basic auth credentials passed as flags.
    policy_path, output = tmp_path / "policy.json", tmp_path / "run.json"
    _write_policy(policy_path, _policy())
    requests: list[httpx2.Request] = []
    _install_transport(monkeypatch, requests)

    # When: collect receives the scheme and credentials as flags.
    result = CliRunner().invoke(
        app,
        [
            *_arguments(policy_path, output),
            "--prometheus-auth-scheme",
            "basic",
            "--prometheus-auth-basic-user",
            "svc",
            "--prometheus-auth-basic-password",
            "s3cret",
        ],
    )

    # Then: the resolved Basic header encodes the flag username and password.
    assert result.exit_code == 0
    expected = "Basic " + base64.b64encode(b"svc:s3cret").decode("ascii")
    _assert_basic_header(requests, expected)


def test_collect_no_auth_by_default_sends_no_authorization_header(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: a suite endpoint and no auth flags or environment variables.
    policy_path, output = tmp_path / "policy.json", tmp_path / "run.json"
    _write_policy(policy_path, _policy())
    requests: list[httpx2.Request] = []
    _install_transport(monkeypatch, requests)

    # When: collect runs with no auth inputs at all.
    result = CliRunner().invoke(app, _arguments(policy_path, output))

    # Then: no Authorization header is sent for the default none scheme.
    assert result.exit_code == 0
    assert len(requests) == 2
    for request in requests:
        assert request.headers.get("authorization") is None


def test_collect_redacts_echoed_basic_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: an upstream echoes both the Basic header and its bare encoded payload.
    policy_path, output = tmp_path / "policy.json", tmp_path / "run.json"
    policy = _policy()
    policy = policy.model_copy(
        update={
            "metrics": tuple(
                metric.model_copy(update={"expected_label_names": ("echo",)})
                for metric in policy.metrics
            ),
        }
    )
    policy = policy.model_copy(update={"policy_sha256": policy_content_sha256(policy)})
    _write_policy(policy_path, policy)
    username, password = "alice", "123£"
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["authorization"] == f"Basic {encoded}"
        return httpx2.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {"echo": f"Basic {encoded}; payload={encoded}"},
                            "values": [[1767225600, "1.5"]],
                        }
                    ],
                },
            },
        )

    monkeypatch.setattr(
        "perfcheck.collection_service.create_collection_client",
        lambda: httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )

    # When: the real CLI collects and persists the response.
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

    # Then: collection succeeds with redacted labels and secret-free evidence.
    assert result.exit_code == 0, result.output
    persisted = output.read_text(encoding="utf-8")
    assert "[REDACTED]" in persisted
    for secret in (username, password, encoded):
        assert secret not in persisted + result.output
