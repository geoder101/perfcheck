from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path  # noqa: TC003 - pytest resolves fixture annotations.
from typing import TYPE_CHECKING, Final, assert_type

import anyio
import httpx2
import pytest
from pydantic import JsonValue, TypeAdapter, ValidationError
from typer.testing import CliRunner

from perfcheck.artifact_models import Artifact
from perfcheck.cli import app
from perfcheck.cli_services import summarize_raw
from perfcheck.collection_models import Label
from perfcheck.errors import ArtifactIntegrityError, ArtifactSchemaCode
from perfcheck.prometheus import (
    CollectionFailure,
    CollectionSuccess,
    FailureKind,
    PrometheusQueryRangeCollector,
    RangeQuery,
)
from perfcheck.storage import load_artifact, write_artifact
from perfcheck.summary_models import SummaryArtifact
from tests.cli_support import cli_policy, cli_run, write_cli_policy

if TYPE_CHECKING:
    from perfcheck.run_models import RunArtifact

_SECRET_MARKERS: Final = (
    "access_token=fixture",
    "api_key=fixture",
    "authorization:fixture",
    "bearer fixture",
    "password=fixture",
    "token=fixture",
)


def test_summarize_rejects_canonical_summary_as_run(tmp_path: Path) -> None:
    # Given: a real canonical summary with verified raw source evidence.
    policy = cli_policy()
    raw = cli_run(policy, 1, 10.0)
    source = tmp_path / "summary.json"
    output = tmp_path / "output.json"
    policy_path = tmp_path / "policy.json"
    write_cli_policy(policy_path, policy)
    write_artifact(source, summarize_raw(raw, policy), source_run=raw)

    # When: summarize receives the summary through its raw-run option.
    result = CliRunner().invoke(
        app,
        [
            "summarize",
            "--policy",
            str(policy_path),
            "--run",
            str(source),
            "--out",
            str(output),
        ],
    )

    # Then: the command retains its generic failure without publishing output.
    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr == "error: invalid command input\n"
    assert not output.exists()


def test_load_artifact_returns_verified_raw_without_source(tmp_path: Path) -> None:
    # Given: canonical raw evidence.
    raw = cli_run(cli_policy(), 1, 10.0)
    path = tmp_path / "run.json"
    write_artifact(path, raw)

    # When: the loader receives no source run.
    loaded = load_artifact(path)

    # Then: it returns the verified raw evidence.
    assert loaded == raw


@pytest.mark.parametrize("explicit_none", [False, True])
def test_load_artifact_requires_summary_source(
    tmp_path: Path, explicit_none: bool
) -> None:
    # Given: canonical summary evidence persisted with its real source.
    raw = cli_run(cli_policy(), 1, 10.0)
    path = tmp_path / "summary.json"
    write_artifact(path, summarize_raw(raw, raw.policy_snapshot), source_run=raw)

    # When: the source is omitted or explicitly None.
    # Then: the loader rejects it at the same integrity boundary.
    with pytest.raises(ArtifactIntegrityError) as caught:
        _ = (
            load_artifact(path, source_run=None)
            if explicit_none
            else load_artifact(path)
        )
    assert caught.value.detail == "source artifact required"


@pytest.mark.parametrize("supplied", [False, True])
def test_load_artifact_accepts_optional_source_variable(
    tmp_path: Path, supplied: bool
) -> None:
    # Given: a union-typed source variable and canonical raw evidence.
    raw = cli_run(cli_policy(), 1, 10.0)
    source: RunArtifact | None = raw if supplied else None
    path = tmp_path / "run.json"
    write_artifact(path, raw)

    # When: a caller explicitly supplies the union-typed variable.
    loaded = load_artifact(path, source_run=source)

    # Then: either branch returns the verified evidence with the union return type.
    _ = assert_type(loaded, Artifact)
    assert loaded == raw


@pytest.mark.parametrize("nested_policy", [False, True])
@pytest.mark.parametrize("field", ["summary", "eligibility", "bootstrap", "report"])
def test_summary_rejects_non_v1_manifest_literal(
    field: str, nested_policy: bool
) -> None:
    # Given: real summary JSON with one invalid algorithm literal at either boundary.
    raw = cli_run(cli_policy(), 1, 10.0)
    summary = summarize_raw(raw, raw.policy_snapshot)
    payload = TypeAdapter(dict[str, JsonValue]).validate_json(summary.model_dump_json())
    owner = payload["policy_snapshot"] if nested_policy else payload
    assert isinstance(owner, dict)
    manifest = owner["algorithm_manifest"]
    assert isinstance(manifest, dict)
    manifest[field] = "unsupported-v2"

    # When: the summary crosses the ordinary JSON parsing boundary.
    # Then: the fixed literal field rejects the value before cross-field validation.
    with pytest.raises(ValidationError) as caught:
        _ = SummaryArtifact.model_validate_json(json.dumps(payload))
    location = ("policy_snapshot",) if nested_policy else ()
    assert [(error["loc"], error["type"]) for error in caught.value.errors()] == [
        ((*location, "algorithm_manifest", field), "literal_error")
    ]


@pytest.mark.parametrize("name", _SECRET_MARKERS)
def test_label_name_grammar_rejects_secret_marker_punctuation(name: str) -> None:
    # Given: a secret marker whose punctuation cannot occur in a label name.
    # When: it crosses the normal label parsing boundary.
    # Then: the name grammar rejects it, independently of secret detection.
    with pytest.raises(ValidationError) as caught:
        _ = Label(name=name, value="benign")
    assert [(error["loc"], error["type"]) for error in caught.value.errors()] == [
        (("name",), "string_pattern_mismatch")
    ]


@pytest.mark.parametrize(
    "name", ["password", "api_key", "authorization", "token", "secret"]
)
def test_label_accepts_legal_names_with_benign_values(name: str) -> None:
    # Given: a legal label name, even when it resembles a credential key.
    # When: it is parsed with a benign value.
    label = Label(name=name, value="benign")

    # Then: cleanup must not introduce new sensitive-key restrictions.
    assert label.name == name
    assert label.value == "benign"


@pytest.mark.parametrize("value", _SECRET_MARKERS)
def test_label_rejects_secret_values(value: str) -> None:
    # Given: an ordinary name with a credential-bearing value.
    # When: the label crosses the normal parsing boundary.
    # Then: the existing credential-value diagnostic remains intact.
    with pytest.raises(ValidationError) as caught:
        _ = Label(name="job", value=value)
    assert [(error["loc"], error["msg"]) for error in caught.value.errors()] == [
        (("value",), f"Value error, {ArtifactSchemaCode.CREDENTIAL_LABEL_VALUE}")
    ]


@pytest.mark.parametrize("explicit_null", [False, True])
def test_collector_rejects_success_without_matrix_data(explicit_null: bool) -> None:
    # Given: a real collector receiving success with missing or null matrix data.
    payload: dict[str, JsonValue] = {"status": "success"}
    if explicit_null:
        payload["data"] = None
    start = datetime(2026, 1, 1, tzinfo=UTC)
    query = RangeQuery(
        prometheus_url="https://metrics.example.test",
        query="up",
        start=start,
        end=start + timedelta(minutes=1),
        step_seconds=15,
        expected_labels={},
    )

    async def collect() -> CollectionSuccess | CollectionFailure:
        transport = httpx2.MockTransport(lambda _: httpx2.Response(200, json=payload))
        async with httpx2.AsyncClient(transport=transport) as client:
            return await PrometheusQueryRangeCollector(client).collect(query)

    # When: collection parses the upstream response through its real ingress.
    result = anyio.run(collect)

    # Then: both forms remain malformed responses, not impossible constructed states.
    assert isinstance(result, CollectionFailure)
    assert result.kind is FailureKind.MALFORMED_RESPONSE
