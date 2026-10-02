from __future__ import annotations

from typer.testing import CliRunner

from perfcheck.cli import app
from perfcheck.policy_models import SuitePolicy
from perfcheck.run_models import RunArtifact
from perfcheck.summary_models import SummaryArtifact


def test_v1_scope_exposes_only_supported_commands_and_artifact_contracts() -> None:
    # Given: the publishable CLI and its three version-one artifact schemas.
    forbidden_scope = (
        "grafana",
        "database",
        "dsl",
        "html",
        "raw_point_gate",
    )
    schema_text = "\n".join(
        (
            SuitePolicy.model_json_schema().__repr__(),
            RunArtifact.model_json_schema().__repr__(),
            SummaryArtifact.model_json_schema().__repr__(),
        )
    ).lower()

    # When: callers inspect the command boundary and serialized schemas.
    result = CliRunner().invoke(app, ["--help"])

    # Then: v1 contains its documented commands and no deferred integrations.
    assert result.exit_code == 0
    assert all(
        command in result.output for command in ("collect", "summarize", "compare")
    )
    assert all(name not in result.output.lower() for name in forbidden_scope)
    assert all(name not in schema_text for name in forbidden_scope)
