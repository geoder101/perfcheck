"""CLI tests for the policy authoring and verification command group."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

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


def _schema_policy_path(directory: Path, policy: SuitePolicy, pointer: str) -> Path:
    body = policy.model_dump(mode="json")
    body["$schema"] = pointer
    path = directory / "schema.json"
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


def test_policy_with_schema_pointer_loads_and_hashes_identically(
    tmp_path: Path,
) -> None:
    # Given: the same policy written with and without a top-level $schema pointer.
    policy = cli_policy()
    plain_path = tmp_path / "plain.json"
    write_cli_policy(plain_path, policy)
    schema_path = _schema_policy_path(
        tmp_path, policy, "schemas/v1/perfcheck-policy.schema.json"
    )

    # When: both policies load.
    plain = load_policy(plain_path)
    with_schema = load_policy(schema_path)

    # Then: the pointer is ignored for validation and never changes identity.
    assert plain.policy_id == with_schema.policy_id == "policy-1"
    assert with_schema.policy_sha256 == plain.policy_sha256
    assert with_schema.policy_sha256 == policy_content_sha256(policy)


def test_policy_stamp_preserves_schema_pointer_verbatim(tmp_path: Path) -> None:
    # Given: an unsigned policy carrying a top-level $schema pointer.
    policy = cli_policy()
    pointer = "schemas/v1/perfcheck-policy.schema.json"
    input_path = _schema_policy_path(tmp_path, policy, pointer)

    # When: the user stamps it to stdout.
    result = CliRunner().invoke(
        app, ["policy", "stamp", "--input", str(input_path), "--stdout"]
    )

    # Then: the canonical output re-injects the pointer verbatim as the first key
    # and still hashes the body only.
    assert result.exit_code == 0
    stamped = cast("dict[str, object]", json.loads(result.stdout))
    assert next(iter(stamped.keys())) == "$schema"
    assert stamped["$schema"] == pointer
    body = {key: value for key, value in stamped.items() if key != "$schema"}
    model = SuitePolicy.model_validate_json(json.dumps(body))
    assert model.policy_sha256 == policy_content_sha256(model)
    assert model.policy_sha256 == policy_content_sha256(policy)


def test_policy_check_warns_on_unknown_schema_version(tmp_path: Path) -> None:
    # Given: a valid policy pointing at an unknown schema major version.
    policy = cli_policy()
    input_path = _schema_policy_path(
        tmp_path, policy, "schemas/v9/perfcheck-policy.schema.json"
    )

    # When: the user checks it.
    result = CliRunner().invoke(app, ["policy", "check", "--input", str(input_path)])

    # Then: it is still valid (exit 0) but warns about the unknown version.
    assert result.exit_code == 0
    assert "is valid" in result.output
    assert "warning:" in result.output
    assert "v9" in result.output


def test_policy_check_warns_on_older_schema_version(tmp_path: Path) -> None:
    # Given: a valid policy pointing at an older schema major version.
    policy = cli_policy()
    input_path = _schema_policy_path(
        tmp_path, policy, "schemas/v0/perfcheck-policy.schema.json"
    )

    # When: the user checks it.
    result = CliRunner().invoke(app, ["policy", "check", "--input", str(input_path)])

    # Then: it is still valid (exit 0) but warns about the older version.
    assert result.exit_code == 0
    assert "is valid" in result.output
    assert "warning:" in result.output
    assert "v0" in result.output


def test_policy_check_warns_on_pointer_without_version(tmp_path: Path) -> None:
    # Given: a valid policy whose $schema pointer has no extractable major version.
    policy = cli_policy()
    input_path = _schema_policy_path(tmp_path, policy, "perfcheck-policy.schema.json")

    # When: the user checks it.
    result = CliRunner().invoke(app, ["policy", "check", "--input", str(input_path)])

    # Then: it is still valid (exit 0) but warns about the missing major version.
    assert result.exit_code == 0
    assert "is valid" in result.output
    assert "warning:" in result.output
    assert "perfcheck-policy.schema.json" in result.output


def test_policy_check_does_not_warn_on_current_or_absent_pointer(
    tmp_path: Path,
) -> None:
    # Given: a valid policy pointing at the current version, and one with no pointer.
    policy = cli_policy()
    current_path = _schema_policy_path(
        tmp_path, policy, "schemas/v1/perfcheck-policy.schema.json"
    )
    plain_path = tmp_path / "plain.json"
    _ = plain_path.write_text(policy.model_dump_json(), encoding="utf-8")

    # When: the user checks both.
    current_result = CliRunner().invoke(
        app, ["policy", "check", "--input", str(current_path)]
    )
    plain_result = CliRunner().invoke(
        app, ["policy", "check", "--input", str(plain_path)]
    )

    # Then: neither warns; both still report the policy valid.
    for result in (current_result, plain_result):
        assert result.exit_code == 0
        assert "is valid" in result.output
        assert "warning:" not in result.output


def test_policy_with_schema_pointer_still_rejects_a_stale_hash(
    tmp_path: Path,
) -> None:
    # Given: a policy carrying a $schema pointer but a content hash that no
    # longer matches its body.
    policy = cli_policy()
    body = policy.model_dump(mode="json")
    body["$schema"] = "schemas/v1/perfcheck-policy.schema.json"
    body["policy_sha256"] = "1" * 64
    input_path = tmp_path / "schema.json"
    _ = input_path.write_text(json.dumps(body), encoding="utf-8")

    # When: the user checks it.
    result = CliRunner().invoke(app, ["policy", "check", "--input", str(input_path)])

    # Then: the authoring aid does not mask the mismatch; the hash failure wins.
    assert result.exit_code == 3
    assert "policy hash mismatch" in result.output


def test_policy_with_schema_pointer_still_rejects_a_schema_failure(
    tmp_path: Path,
) -> None:
    # Given: JSON that carries a $schema pointer but is missing required fields.
    input_path = tmp_path / "missing.json"
    _ = input_path.write_text(
        json.dumps({"$schema": "schemas/v1/perfcheck-policy.schema.json"}),
        encoding="utf-8",
    )

    # When: the user checks it.
    result = CliRunner().invoke(app, ["policy", "check", "--input", str(input_path)])

    # Then: stripping the pointer does not rescue an otherwise-invalid policy.
    assert result.exit_code == 3
    assert "invalid policy JSON" in result.output


def test_policy_stamp_without_pointer_has_no_schema_key(tmp_path: Path) -> None:
    # Given: an unsigned policy with no top-level $schema pointer.
    policy = cli_policy()
    input_path = _unsigned_policy_path(tmp_path, policy)

    # When: the user stamps it to stdout.
    result = CliRunner().invoke(
        app, ["policy", "stamp", "--input", str(input_path), "--stdout"]
    )

    # Then: the canonical output is valid and carries no $schema key.
    assert result.exit_code == 0
    stamped = cast("dict[str, object]", json.loads(result.stdout))
    assert "$schema" not in stamped
    body = SuitePolicy.model_validate_json(result.stdout)
    assert body.policy_sha256 == policy_content_sha256(body)


def test_policy_check_warns_on_non_numeric_schema_version(tmp_path: Path) -> None:
    # Given: a valid policy whose $schema pointer names a non-numeric major.
    policy = cli_policy()
    input_path = _schema_policy_path(
        tmp_path, policy, "schemas/vX/perfcheck-policy.schema.json"
    )

    # When: the user checks it.
    result = CliRunner().invoke(app, ["policy", "check", "--input", str(input_path)])

    # Then: it is still valid (exit 0) but warns about the unparseable version.
    assert result.exit_code == 0
    assert "is valid" in result.output
    assert "warning:" in result.output
    assert "vX" in result.output
