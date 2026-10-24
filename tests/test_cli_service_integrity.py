from __future__ import annotations

from typing import TYPE_CHECKING, Literal, assert_never

import pytest
from typer.testing import CliRunner

from perfcheck.cli import app
from perfcheck.cli_services import (
    CliInputCode,
    CliInputError,
    effective_summary,
    summarize_raw,
)
from perfcheck.storage import (
    artifact_content_sha256,
    canonical_json_bytes,
    policy_content_sha256,
    summary_cache_path,
    write_artifact,
)
from perfcheck.summary_models import SummaryArtifact
from tests.cli_support import cli_policy, cli_run, compare_inputs

if TYPE_CHECKING:
    from pathlib import Path

    from perfcheck.policy_models import SuitePolicy

type Corruption = Literal["content", "snapshot-policy", "supplied-policy"]
type CacheKind = Literal["matching-summary", "other-policy-summary", "raw-run"]


def other_policy() -> SuitePolicy:
    policy = cli_policy().model_copy(update={"policy_id": "fixture-secret"})
    return policy.model_copy(update={"policy_sha256": policy_content_sha256(policy)})


def rejected_summary(kind: Corruption) -> tuple[SummaryArtifact, CliInputCode]:
    policy = cli_policy()
    summary = summarize_raw(cli_run(policy, 1, 10.0), policy)
    match kind:
        case "content":
            return (
                summary.model_copy(update={"summary_id": "fixture-secret"}),
                CliInputCode.SUMMARY_CONTENT_HASH_MISMATCH,
            )
        case "snapshot-policy":
            snapshot = policy.model_copy(update={"policy_id": "fixture-secret"})
            summary = summary.model_copy(update={"policy_snapshot": snapshot})
            summary = summary.model_copy(
                update={"content_sha256": artifact_content_sha256(summary)}
            )
            return summary, CliInputCode.SUMMARY_POLICY_HASH_MISMATCH
        case "supplied-policy":
            other = other_policy()
            return (
                summarize_raw(cli_run(other, 1, 10.0), other),
                CliInputCode.POLICY_MISMATCH,
            )
        case _:
            assert_never(kind)


@pytest.mark.parametrize("kind", ["content", "snapshot-policy", "supplied-policy"])
def test_direct_summary_rejects_each_independent_integrity_failure(
    tmp_path: Path, kind: Corruption
) -> None:
    # Given: schema-valid direct summary JSON with exactly one integrity failure.
    summary, reason = rejected_summary(kind)
    path = tmp_path / "summary.json"
    payload = summary.model_dump_json().encode()
    assert SummaryArtifact.model_validate_json(payload) == summary
    _ = path.write_bytes(payload)
    # When: the service loads the direct summary without requiring a raw sibling.
    with pytest.raises(CliInputError) as caught:
        _ = effective_summary(path, cli_policy(), write_cache=True)
    # Then: each reachable validation seam has its own reason and no mutations.
    assert caught.value.code is reason
    assert path.read_bytes() == payload
    assert set(tmp_path.iterdir()) == {path}


@pytest.mark.parametrize("kind", ["content", "snapshot-policy", "supplied-policy"])
def test_compare_sanitizes_direct_summary_integrity_failures(
    tmp_path: Path, kind: Corruption
) -> None:
    # Given: comparison inputs with a schema-valid but untrusted direct summary.
    arguments = compare_inputs(tmp_path)
    summary, _ = rejected_summary(kind)
    current = tmp_path / "current-0.json"
    _ = current.write_text(summary.model_dump_json(), encoding="utf-8")
    originals = {path: path.read_bytes() for path in tmp_path.iterdir()}
    # When: comparison requests both reports, JSON stdout, and cache writes.
    result = CliRunner().invoke(
        app,
        [
            *arguments,
            "--report-json",
            str(tmp_path / "report.json"),
            "--report-md",
            str(tmp_path / "report.md"),
            "--json",
            "--write-summary-cache",
        ],
    )
    # Then: safe diagnostics expose no secret or output and preserve every input.
    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr == "error: invalid command input\n"
    assert {path: path.read_bytes() for path in tmp_path.iterdir()} == originals


@pytest.mark.parametrize("write_cache", [False, True])
def test_direct_valid_summary_needs_no_source_or_cache(
    tmp_path: Path, write_cache: bool
) -> None:
    # Given: a verified direct summary with no raw source file beside it.
    policy = cli_policy()
    expected = summarize_raw(cli_run(policy, 1, 10.0), policy)
    path = tmp_path / "summary.json"
    payload = b"\n " + expected.model_dump_json().encode()
    _ = path.write_bytes(payload)
    # When: the direct summary is loaded with either cache-write preference.
    actual = effective_summary(path, policy, write_cache=write_cache)
    # Then: it returns unchanged without publishing an extra cache or rewriting it.
    assert actual == expected
    assert {entry: entry.read_bytes() for entry in tmp_path.iterdir()} == {
        path: payload
    }


@pytest.mark.parametrize(
    "kind", ["matching-summary", "other-policy-summary", "raw-run"]
)
@pytest.mark.parametrize("write_cache", [False, True])
def test_valid_cache_variants_are_reused_or_derived_under_requested_policy(
    tmp_path: Path, kind: CacheKind, write_cache: bool
) -> None:
    # Given: valid source evidence and a schema-valid sibling cache variant.
    policy = cli_policy()
    raw = cli_run(policy, 1, 10.0)
    path = tmp_path / "raw.json"
    write_artifact(path, raw)
    cache = summary_cache_path(path, policy.policy_sha256)
    expected = summarize_raw(raw, policy)
    match kind:
        case "matching-summary":
            cached = expected.model_copy(update={"summary_id": "cached-summary"})
            cached = cached.model_copy(
                update={"content_sha256": artifact_content_sha256(cached)}
            )
            write_artifact(cache, cached, source_run=raw)
            expected = cached
        case "other-policy-summary":
            other = other_policy()
            cached = summarize_raw(cli_run(other, 1, 10.0), other)
            cached = cached.model_copy(
                update={"source_content_sha256": raw.content_sha256}
            )
            cached = cached.model_copy(
                update={"content_sha256": artifact_content_sha256(cached)}
            )
            write_artifact(cache, cached, source_run=raw)
        case "raw-run":
            write_artifact(cache, raw)
        case _:
            assert_never(kind)
    original = b"\n " + cache.read_bytes()
    _ = cache.write_bytes(original)
    # When: the service resolves raw evidence under the supplied policy.
    actual = effective_summary(path, policy, write_cache=write_cache)
    # Then: only a matching summary is reused; writes require explicit permission.
    assert actual == expected
    assert cache.read_bytes() == (
        canonical_json_bytes(expected) if write_cache else original
    )
    assert set(tmp_path.iterdir()) == {path, cache}
