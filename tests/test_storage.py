from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import JsonValue

from perfcheck.errors import ArtifactIntegrityError
from perfcheck.models import RunArtifact, SummaryArtifact
from perfcheck.storage import (
    artifact_content_sha256,
    canonical_json_bytes,
    load_artifact,
    policy_content_sha256,
    summary_cache_path,
    write_artifact,
)


def _run_payload() -> JsonValue:
    return {
        "artifact_type": "run",
        "schema_version": 1,
        "content_sha256": "0" * 64,
        "run_id": "run-1",
        "suite_id": "suite-1",
        "source_interval": {
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-01T00:10:00Z",
        },
        "policy_sha256": "0" * 64,
        "policy_snapshot": {
            "schema_version": 1,
            "policy_id": "policy-1",
            "suite_id": "suite-1",
            "policy_sha256": "0" * 64,
            "metrics": [
                {
                    "metric_id": "cpu-system",
                    "query": "up",
                    "expected_label_names": ["job"],
                    "unit": "percent",
                    "direction": "higher_is_worse",
                    "statistic": "mean",
                    "practical_threshold": -0.0,
                    "step_seconds": 15,
                    "rate_window_seconds": 60,
                }
            ],
        },
        "metadata": {
            "test_name": "load-test",
            "git_sha": "abcdef",
            "environment": "ci",
            "scenario": "baseline",
            "target_topology": "single-node",
        },
        "metric_records": [
            {
                "metric_id": "cpu-system",
                "availability": "available",
                "provenance": {
                    "endpoint_url": "https://metrics.example.test/prometheus",
                    "request_path": "/api/v1/query_range",
                    "query": "up",
                    "start": "2026-01-01T00:00:00Z",
                    "end": "2026-01-01T00:10:00Z",
                    "step_seconds": 15,
                    "http_status": 200,
                    "prometheus_status": "success",
                },
                "series": {
                    "metric_id": "cpu-system",
                    "labels": [{"name": "job", "value": "api"}],
                    "samples": [
                        {"timestamp": "2026-01-01T00:00:00Z", "value": 2.25},
                        {"timestamp": "2026-01-01T00:00:15Z", "value": 2.5},
                    ],
                },
            }
        ],
    }


def _run() -> RunArtifact:
    payload = _run_payload()
    initial = RunArtifact.model_validate_json(json.dumps(payload))
    policy = initial.policy_snapshot.model_copy(
        update={"policy_sha256": policy_content_sha256(initial.policy_snapshot)}
    )
    with_policy = initial.model_copy(
        update={"policy_snapshot": policy, "policy_sha256": policy.policy_sha256}
    )
    return with_policy.model_copy(
        update={"content_sha256": artifact_content_sha256(with_policy)}
    )


def _summary(run: RunArtifact) -> SummaryArtifact:
    empty_hash = "0" * 64
    fingerprint = "d" * 64
    payload = f"""
    {{
      "artifact_type": "summary",
      "schema_version": 1,
      "content_sha256": "{empty_hash}",
      "summary_id": "summary-1",
      "source_run_id": "{run.run_id}",
      "source_content_sha256": "{run.content_sha256}",
      "source_interval": {{
        "start": "2026-01-01T00:00:00Z",
        "end": "2026-01-01T00:10:00Z"
      }},
      "policy_sha256": "{run.policy_sha256}",
      "policy_snapshot": {run.policy_snapshot.model_dump_json()},
      "metric_records": [
        {{
          "metric_id": "cpu-system",
          "availability": "available",
          "summary": {{
            "statistic": "mean",
            "value": 2.375,
            "point_count": 21,
            "compatibility_fingerprint": "{fingerprint}",
            "eligibility": {{
              "eligible": true,
              "reason": null,
              "analysis_start": "2026-01-01T00:00:00Z",
              "analysis_end": "2026-01-01T00:10:00Z",
              "retained_points": 21,
              "expected_points": 41,
              "coverage": 0.8
            }}
          }}
        }}
      ]
    }}
    """
    initial = SummaryArtifact.model_validate_json(payload)
    return initial.model_copy(
        update={"content_sha256": artifact_content_sha256(initial)}
    )


def test_canonical_bytes_and_hashes_are_stable_for_equivalent_artifacts() -> None:
    # Given: semantically identical validated run artifacts created from reordered JSON.
    run = _run()
    reordered = RunArtifact.model_validate_json(run.model_dump_json(indent=2))

    # When: their policy and artifact identities use canonical JSON bytes.
    run_bytes = canonical_json_bytes(run)
    reordered_bytes = canonical_json_bytes(reordered)

    # Then: key order, whitespace, and negative zero cannot change reproducible hashes.
    assert run_bytes == reordered_bytes
    assert b'"practical_threshold":0' in run_bytes
    assert artifact_content_sha256(run) == run.content_sha256
    assert policy_content_sha256(run.policy_snapshot) == run.policy_sha256


def test_write_and_load_round_trip_with_explicit_force_and_sibling_cache(
    tmp_path: Path,
) -> None:
    # Given: a validated run and its intended raw evidence path.
    run = _run()
    path = tmp_path / "raw.run.json"

    # When: it is stored, then explicitly replaced after a no-overwrite attempt.
    write_artifact(path, run)
    with pytest.raises(FileExistsError):
        write_artifact(path, run)
    write_artifact(path, run, force=True)

    # Then: the validated artifact round trips and its cache path is policy-specific.
    assert load_artifact(path) == run
    assert summary_cache_path(path, run.policy_sha256) == (
        tmp_path / f"raw.run.{run.policy_sha256[:12]}.summary.json"
    )


def test_load_rejects_corrupt_content_hash_before_returning_an_artifact(
    tmp_path: Path,
) -> None:
    # Given: a stored artifact whose JSON remains schema-valid but has a forged hash.
    run = _run()
    path = tmp_path / "run.json"
    write_artifact(path, run)
    forged = path.read_text(encoding="utf-8").replace(run.content_sha256, "f" * 64, 1)
    _ = path.write_text(forged, encoding="utf-8")

    # When: the persistence boundary loads the evidence.
    # Then: integrity fails before the artifact can reach compatibility work.
    with pytest.raises(ArtifactIntegrityError, match="content hash"):
        _ = load_artifact(path)


def test_write_preserves_original_when_replace_is_interrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a readable original artifact and a second valid artifact.
    original = _run()
    replacement = original.model_copy(update={"run_id": "run-2"})
    replacement = replacement.model_copy(
        update={"content_sha256": artifact_content_sha256(replacement)}
    )
    path = tmp_path / "run.json"
    write_artifact(path, original)

    # When: replacement fails at the atomic rename boundary.
    def fail_replace(_source: Path, _destination: Path) -> None:
        error_message = "simulated interruption"
        raise OSError(error_message)

    monkeypatch.setattr("perfcheck.storage.Path.replace", fail_replace)
    with pytest.raises(OSError, match="simulated interruption"):
        write_artifact(path, replacement, force=True)

    # Then: the prior complete artifact remains readable.
    assert load_artifact(path) == original


def test_summary_persistence_requires_and_verifies_its_source_run(
    tmp_path: Path,
) -> None:
    # Given: a summary whose declared source hash is derived from a valid raw run.
    run = _run()
    summary = _summary(run)
    path = tmp_path / "summary.json"

    # When: the summary crosses the persistence boundary with its source evidence.
    write_artifact(path, summary, source_run=run)

    # Then: loading verifies the source identity, while a missing source is rejected.
    assert load_artifact(path, source_run=run) == summary
    with pytest.raises(ArtifactIntegrityError, match="source artifact required"):
        _ = load_artifact(path)
    other_run = run.model_copy(update={"run_id": "run-2"})
    other_run = other_run.model_copy(
        update={"content_sha256": artifact_content_sha256(other_run)}
    )
    with pytest.raises(ArtifactIntegrityError, match="source hash mismatch"):
        _ = load_artifact(path, source_run=other_run)
