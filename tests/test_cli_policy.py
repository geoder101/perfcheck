"""CLI tests for the policy authoring and verification command group."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from perfcheck.cli import app
from perfcheck.cli_services import load_policy
from perfcheck.policy_models import SuitePolicy
from perfcheck.storage import policy_content_sha256
from tests.cli_support import cli_policy, write_cli_policy

if TYPE_CHECKING:
    from pathlib import Path


def _unsigned_policy_path(directory: Path, policy: SuitePolicy) -> Path:
    body = policy.model_dump(mode="json")
    body.pop("policy_sha256", None)
    path = directory / "unsigned.json"
    _ = path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _stale_policy_path(directory: Path, policy: SuitePolicy) -> Path:
    body = policy.model_dump(mode="json")
    body["policy_sha256"] = "1" * 64
    path = directory / "stale.json"
    _ = path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_policy_check_accepts_a_valid_policy(tmp_path: Path) -> None:
    # Given: a canonical policy with a matching content hash.
    policy = cli_policy()
    policy_path = tmp_path / "policy.json"
    write_cli_policy(policy_path, policy)

    # When: the user verifies the policy before collecting.
    result = CliRunner().invoke(app, ["policy", "check", "--input", str(policy_path)])

    # Then: the policy validates and the identity is shown on stderr.
    assert result.exit_code == 0
    assert result.stdout == ""
    assert load_policy(policy_path).policy_id == "policy-1"


def test_policy_check_rejects_invalid_json(tmp_path: Path) -> None:
    # Given: a policy file that is not parseable JSON.
    policy_path = tmp_path / "broken.json"
    _ = policy_path.write_bytes(b"{not json")

    # When: the user verifies it.
    result = CliRunner().invoke(app, ["policy", "check", "--input", str(policy_path)])

    # Then: it fails the invalid-policy input contract without its message.
    assert result.exit_code == 3
    assert "invalid policy JSON" in result.output


def test_policy_check_rejects_a_stale_content_hash(tmp_path: Path) -> None:
    # Given: a policy whose content hash no longer matches its content.
    policy = cli_policy()
    policy_path = _stale_policy_path(tmp_path, policy)

    # When: the user verifies it.
    result = CliRunner().invoke(app, ["policy", "check", "--input", str(policy_path)])

    # Then: the mismatch is rejected as invalid command input.
    assert result.exit_code == 3
    assert "policy hash mismatch" in result.output


def test_policy_check_rejects_a_schema_failure(tmp_path: Path) -> None:
    # Given: JSON that is valid JSON but fails the policy schema.
    policy_path = tmp_path / "missing.json"
    _ = policy_path.write_text(json.dumps({}), encoding="utf-8")

    # When: the user verifies it.
    result = CliRunner().invoke(app, ["policy", "check", "--input", str(policy_path)])

    # Then: a schema failure fails the invalid-policy input contract.
    assert result.exit_code == 3
    assert "invalid policy JSON" in result.output


def test_policy_stamp_rebuilds_an_unsigned_policy(tmp_path: Path) -> None:
    # Given: a policy written without a content hash.
    policy = cli_policy()
    input_path = _unsigned_policy_path(tmp_path, policy)
    unsigned_bytes = input_path.read_bytes()

    # When: the user stamps it in place.
    result = CliRunner().invoke(
        app, ["policy", "stamp", "--input", str(input_path), "--force"]
    )

    # Then: the file is rewritten in canonical form and is now accepted as-is.
    assert result.exit_code == 0
    assert input_path.read_bytes() != unsigned_bytes
    assert load_policy(input_path).policy_id == "policy-1"
    stamped = SuitePolicy.model_validate_json(input_path.read_bytes())
    assert stamped.policy_sha256 == policy_content_sha256(stamped)


def test_policy_stamp_requires_force_to_replace_existing_input(
    tmp_path: Path,
) -> None:
    # Given: an unsigned policy and a stamp without replacement permission.
    policy = cli_policy()
    input_path = _unsigned_policy_path(tmp_path, policy)
    unsigned_bytes = input_path.read_bytes()

    # When: the user stamps in place without --force.
    result = CliRunner().invoke(app, ["policy", "stamp", "--input", str(input_path)])

    # Then: the replacement is refused and the unsigned file is preserved.
    assert result.exit_code == 3
    assert input_path.read_bytes() == unsigned_bytes


def test_policy_stamp_writes_a_different_output_path(tmp_path: Path) -> None:
    # Given: an unsigned policy and an unused destination.
    policy = cli_policy()
    input_path = _unsigned_policy_path(tmp_path, policy)
    unsigned_bytes = input_path.read_bytes()
    stamped_path = tmp_path / "stamped.json"

    # When: the user stamps to a different path.
    result = CliRunner().invoke(
        app,
        [
            "policy",
            "stamp",
            "--input",
            str(input_path),
            "--output",
            str(stamped_path),
        ],
    )

    # Then: only the destination is written and it is accepted as-is.
    assert result.exit_code == 0
    assert input_path.read_bytes() == unsigned_bytes
    assert stamped_path.read_bytes() != unsigned_bytes
    assert load_policy(stamped_path).policy_id == "policy-1"


def test_policy_stamp_replaces_output_only_with_force(tmp_path: Path) -> None:
    # Given: an unsigned policy, an existing destination, and no permission.
    policy = cli_policy()
    input_path = _unsigned_policy_path(tmp_path, policy)
    destination = tmp_path / "existing.json"
    sentinel = b"keep-existing\x00\xff"
    _ = destination.write_bytes(sentinel)

    # When: the user stamps to that destination without --force.
    result = CliRunner().invoke(
        app,
        [
            "policy",
            "stamp",
            "--input",
            str(input_path),
            "--output",
            str(destination),
        ],
    )

    # Then: the replacement is refused and the existing bytes are preserved.
    assert result.exit_code == 3
    assert destination.read_bytes() == sentinel


def test_policy_stamp_prints_canonical_json_to_stdout(tmp_path: Path) -> None:
    # Given: an unsigned policy.
    policy = cli_policy()
    input_path = _unsigned_policy_path(tmp_path, policy)

    # When: the user stamps to stdout.
    result = CliRunner().invoke(
        app, ["policy", "stamp", "--input", str(input_path), "--stdout"]
    )

    # Then: stdout is a stamped policy whose hash matches its content.
    assert result.exit_code == 0
    body = SuitePolicy.model_validate_json(result.stdout)
    assert body.policy_sha256 == policy_content_sha256(body)
