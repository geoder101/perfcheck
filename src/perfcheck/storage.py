"""Canonical, verified, atomic persistence for versioned artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, assert_never, cast, overload

from pydantic import ValidationError

from perfcheck.artifact_models import ARTIFACT_ADAPTER, Artifact
from perfcheck.errors import ArtifactIntegrityError
from perfcheck.run_models import RunArtifact
from perfcheck.summary_models import SummaryArtifact

if TYPE_CHECKING:
    from pydantic import JsonValue

    from perfcheck.model_types import StrictModel
    from perfcheck.policy_models import SuitePolicy


def canonical_json_bytes(value: StrictModel, *, omit_field: str | None = None) -> bytes:
    """Serialize a validated public model into its reproducible JSON representation."""
    excluded = {omit_field} if omit_field is not None else None
    payload = value.model_dump(mode="json", exclude=excluded)
    return f"{_encode_json(payload)}\n".encode()


def canonical_json_bytes_dict(payload: dict[str, object]) -> bytes:
    """Serialize a plain JSON-compatible dict into canonical bytes.

    Reuses the model encoder so custom float/int encoding matches
    :func:`canonical_json_bytes`; callers own the payload shape.
    """
    encoded = _encode_json(cast("JsonValue", payload))
    return f"{encoded}\n".encode()


def policy_content_sha256(policy: SuitePolicy) -> str:
    """Return the policy identity derived without its self-referential hash field."""
    return _sha256(canonical_json_bytes(policy, omit_field="policy_sha256"))


def artifact_content_sha256(artifact: Artifact) -> str:
    """Return the artifact identity derived without its self-referential hash field."""
    return _sha256(canonical_json_bytes(artifact, omit_field="content_sha256"))


def summary_cache_path(raw_path: Path, policy_sha256: str) -> Path:
    """Derive the immutable policy-keyed sibling location for a run summary cache."""
    return raw_path.with_name(f"{raw_path.stem}.{policy_sha256[:12]}.summary.json")


def write_artifact(
    path: Path,
    artifact: Artifact,
    *,
    force: bool = False,
    source_run: RunArtifact | None = None,
) -> None:
    """Persist one preflight-verified artifact without exposing partial output."""
    verify_artifact(artifact, source_run=source_run)
    write_bytes(path, canonical_json_bytes(artifact), force=force)


@overload
def load_artifact(path: Path, *, source_run: None = None) -> RunArtifact: ...


@overload
def load_artifact(path: Path, *, source_run: RunArtifact) -> Artifact: ...


def load_artifact(path: Path, *, source_run: RunArtifact | None = None) -> Artifact:
    """Load schema-valid evidence and verify stored identities before returning it."""
    try:
        artifact = ARTIFACT_ADAPTER.validate_json(path.read_bytes())
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
    ) as error:
        raise ArtifactIntegrityError(str(path), "invalid artifact JSON") from error
    verify_artifact(artifact, source_run=source_run)
    return artifact


def verify_artifact(
    artifact: Artifact, *, source_run: RunArtifact | None = None
) -> None:
    """Verify an artifact, its policy, and an optionally supplied summary source."""
    _verify_policy(artifact.policy_snapshot)
    actual_content_hash = artifact_content_sha256(artifact)
    if artifact.content_sha256 != actual_content_hash:
        raise ArtifactIntegrityError(
            artifact_identity(artifact), "content hash mismatch"
        )
    match artifact:
        case SummaryArtifact():
            match source_run:
                case None:
                    raise ArtifactIntegrityError(
                        artifact.summary_id, "source artifact required"
                    )
                case RunArtifact():
                    verify_artifact(source_run)
                    _verify_summary_source(artifact, source_run)
                case _:
                    assert_never(source_run)
        case RunArtifact():
            return
        case _:
            assert_never(artifact)


def artifact_identity(artifact: Artifact) -> str:
    """Return the stable identifier used to contextualize persistence errors."""
    match artifact:
        case RunArtifact(run_id=run_id):
            return run_id
        case SummaryArtifact(summary_id=summary_id):
            return summary_id
        case _:
            assert_never(artifact)


def _encode_json(value: JsonValue) -> str:  # noqa: PLR0911
    """Render each JSON value variant with recursive key ordering."""
    match value:
        case None:
            return "null"
        case bool() as boolean:
            return "true" if boolean else "false"
        case str() as text:
            return json.dumps(text, ensure_ascii=False, separators=(",", ":"))
        case int() as integer:
            return str(integer)
        case float() as number:
            return _encode_float(number)
        case list() as items:
            return f"[{','.join(_encode_json(item) for item in items)}]"
        case dict() as fields:
            return (
                "{"
                + ",".join(
                    f"{json.dumps(key, ensure_ascii=False, separators=(',', ':'))}:"
                    + _encode_json(fields[key])
                    for key in sorted(fields)
                )
                + "}"
            )
        case _:
            assert_never(value)


def _encode_float(value: float) -> str:
    if value == 0:
        return "0"
    return format(value, ".17g")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _verify_policy(policy: SuitePolicy) -> None:
    actual_policy_hash = policy_content_sha256(policy)
    if policy.policy_sha256 != actual_policy_hash:
        raise ArtifactIntegrityError(policy.policy_id, "policy hash mismatch")


def _verify_summary_source(summary: SummaryArtifact, source_run: RunArtifact) -> None:
    source_content_hash = artifact_content_sha256(source_run)
    if (
        summary.source_run_id != source_run.run_id
        or summary.source_content_sha256 != source_content_hash
    ):
        raise ArtifactIntegrityError(summary.summary_id, "source hash mismatch")


def write_bytes(path: Path, data: bytes, *, force: bool) -> None:
    """Atomically write bytes without exposing a partial destination.

    The temporary file is cleaned up unless publication itself failed; a cleanup
    failure on an already-published file is surfaced rather than swallowed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    publication_succeeded = False
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            _ = temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
        if force:
            _ = temporary_path.replace(path)
        else:
            os.link(temporary_path, path)
            _ = temporary_path.unlink()
        publication_succeeded = True
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                if publication_succeeded:
                    raise
