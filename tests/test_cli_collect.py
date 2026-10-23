from __future__ import annotations

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
        "--suite",
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


def test_collect_is_exposed_as_a_cli_command() -> None:
    # Given: the publishable command application.

    # When: command help is requested.
    result = CliRunner().invoke(app, ["--help"])

    # Then: portable Prometheus collection is available to callers.
    assert result.exit_code == 0
    assert "collect" in result.output


def test_collect_preserves_existing_destination_without_collection_side_effects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: valid collection inputs, an occupied output, and an injected transport.
    policy_path, output = tmp_path / "policy.json", tmp_path / "run.json"
    _write_policy(policy_path, _policy())
    original = b"keep-run\x00\xff"
    _ = output.write_bytes(original)
    requests: list[httpx2.Request] = []
    clients: list[httpx2.AsyncClient] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return _success_response()

    def create_client() -> httpx2.AsyncClient:
        client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        clients.append(client)
        return client

    monkeypatch.setattr(
        "perfcheck.collection_service.create_collection_client", create_client
    )

    # When: collect targets the existing artifact.
    result = CliRunner().invoke(app, _arguments(policy_path, output))

    # Then: refusal preserves bytes without creating clients, requests, or files.
    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr == "error: invalid command input\n"
    assert output.read_bytes() == original
    assert clients == []
    assert requests == []
    assert set(tmp_path.iterdir()) == {policy_path, output}


def test_collect_prefers_safe_override_and_writes_a_complete_portable_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: a suite endpoint, a safe override, and a deterministic Prometheus response.
    policy = _policy()
    policy_path = tmp_path / "policy.json"
    output_path = tmp_path / "run.json"
    _write_policy(policy_path, policy)

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url == "https://override.example/p/api/v1/query_range"
        return _success_response()

    monkeypatch.setattr(
        "perfcheck.collection_service.create_collection_client",
        lambda: httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )

    # When: collect receives an override that wins over the suite policy URL.
    result = CliRunner().invoke(
        app,
        [
            *_arguments(policy_path, output_path),
            "--prometheus-url",
            "https://override.example/p",
        ],
    )

    # Then: it atomically persists every policy metric with query provenance.
    assert result.exit_code == 0
    payload = _RUN_PAYLOAD.validate_json(output_path.read_bytes())
    assert payload["artifact_type"] == "run"
    assert {record["metric_id"] for record in payload["metric_records"]} == {
        "latency",
        "errors",
    }
    assert {
        record["provenance"]["endpoint_url"] for record in payload["metric_records"]
    } == {"https://override.example/p"}


def test_collect_writes_redacted_unavailable_record_and_exits_four(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: a policy metric whose transport request times out after receiving a token.
    policy = _policy()
    policy_path = tmp_path / "policy.json"
    output_path = tmp_path / "run.json"
    _write_policy(policy_path, policy)
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", "unsafe-bearer")

    def handler(request: httpx2.Request) -> httpx2.Response:
        if b"errors_total" in request.content:
            message = "unsafe-bearer"
            raise httpx2.ReadTimeout(message, request=request)
        return _success_response()

    monkeypatch.setattr(
        "perfcheck.collection_service.create_collection_client",
        lambda: httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )

    # When: one enabled metric has a transport failure.
    result = CliRunner().invoke(app, _arguments(policy_path, output_path))

    # Then: CI sees code 4 and the schema-valid artifact retains its typed failure.
    assert result.exit_code == 4
    output = output_path.read_text(encoding="utf-8")
    assert "unsafe-bearer" not in output
    payload = _RUN_PAYLOAD.validate_json(output)
    failures = [
        record
        for record in payload["metric_records"]
        if record["availability"] == "unavailable"
    ]
    assert len(failures) == 1
    assert failures[0]["metric_id"] == "errors"
    assert failures[0]["failure"] == {
        "detail": "Prometheus collection failed: timeout",
        "reason": "timeout",
    }


def test_collect_rejects_an_unsafe_override_without_creating_output(
    tmp_path: Path,
) -> None:
    # Given: an otherwise valid suite policy and a userinfo-bearing override.
    policy_path = tmp_path / "policy.json"
    output_path = tmp_path / "run.json"
    _write_policy(policy_path, _policy())

    # When: the invalid override crosses the command boundary.
    result = CliRunner().invoke(
        app,
        [
            *_arguments(policy_path, output_path),
            "--prometheus-url",
            "https://user:secret@prometheus.example",
        ],
    )

    # Then: the shared endpoint resolver rejects it before any write.
    assert result.exit_code == 3
    assert not output_path.exists()


def test_collect_propagates_unexpected_failures_without_rendering_secrets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: an unexpected implementation failure containing a credential-shaped value.
    policy_path = tmp_path / "policy.json"
    output_path = tmp_path / "run.json"
    _write_policy(policy_path, _policy())

    def fail(_: Path) -> SuitePolicy:
        raise RuntimeError("token=" + "top-secret")

    monkeypatch.setattr("perfcheck.cli.load_policy", fail)

    # When: collect crosses the real command process boundary.
    result = CliRunner().invoke(app, _arguments(policy_path, output_path))

    # Then: the unexpected failure is not swallowed or rendered to command output.
    assert result.exit_code == 1
    assert isinstance(result.exception, RuntimeError)
    assert result.stdout == ""
    assert "top-secret" not in result.output


def test_collect_sanitizes_os_error_at_the_cli_boundary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: a filesystem error whose message includes a credential-shaped value.
    policy_path = tmp_path / "policy.json"
    output_path = tmp_path / "run.json"

    def fail(_: Path) -> SuitePolicy:
        raise OSError("token=" + "top-secret")

    monkeypatch.setattr("perfcheck.cli.load_policy", fail)

    # When: the command converts expected input failures to the CLI contract.
    result = CliRunner().invoke(app, _arguments(policy_path, output_path))

    # Then: it preserves the input exit code without exposing exception text.
    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr == "error: invalid command input\n"
    assert "top-secret" not in result.output
