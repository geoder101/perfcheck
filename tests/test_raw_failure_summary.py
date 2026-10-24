from __future__ import annotations

from pathlib import Path  # noqa: TC003 - pytest resolves fixture annotations.
from typing import TYPE_CHECKING

import httpx2
from typer.testing import CliRunner

from perfcheck.cli import app
from perfcheck.model_types import MetricAvailability, Statistic
from perfcheck.policy import comparison_fingerprint
from perfcheck.run_models import RunArtifact
from perfcheck.storage import artifact_content_sha256, load_artifact
from perfcheck.summary_models import SummaryArtifact
from tests.collection_failure_support import (
    SECRET,
    collect_cli,
    failure_policy,
    install_transport,
)

if TYPE_CHECKING:
    import pytest


def test_summarize_mixed_raw_preserves_failure_source_and_healthy_scalar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: verified raw evidence collected from a healthy and failed HTTP query.
    policy = failure_policy()
    install_transport(monkeypatch, lambda _: httpx2.Response(502, text=SECRET))
    collected = collect_cli(tmp_path, policy)
    assert collected.exit_code == 4
    raw_path = tmp_path / "raw.json"
    raw_bytes = raw_path.read_bytes()
    raw = load_artifact(raw_path)
    assert isinstance(raw, RunArtifact)
    output = tmp_path / "summary.json"

    # When: the real summarize command consumes the mixed raw artifact.
    result = CliRunner().invoke(
        app,
        [
            "summarize",
            "--policy",
            str(tmp_path / "policy.json"),
            "--run",
            str(raw_path),
            "--out",
            str(output),
        ],
    )

    # Then: one valid scalar and the exact failure retain their original source.
    assert result.exit_code == 0, repr(result.exception)
    summary = load_artifact(output, source_run=raw)
    assert isinstance(summary, SummaryArtifact)
    assert summary.source_content_sha256 == raw.content_sha256
    assert summary.source_run_id == raw.run_id
    assert summary.source_interval == raw.source_interval
    assert summary.policy_snapshot == policy
    assert summary.content_sha256 == artifact_content_sha256(summary)
    healthy, failed = summary.metric_records
    assert healthy.metric_id == raw.metric_records[0].metric_id
    assert healthy.availability is MetricAvailability.AVAILABLE
    assert healthy.failure is None
    assert healthy.summary is not None
    assert healthy.summary.value == 2.5
    assert healthy.summary.statistic is Statistic.MEAN
    assert healthy.summary.point_count == 41
    assert healthy.summary.eligibility.eligible is True
    assert healthy.summary.eligibility.reason is None
    assert healthy.summary.compatibility_fingerprint == comparison_fingerprint(
        policy, policy.metrics[0]
    )
    assert failed.metric_id == raw.metric_records[1].metric_id
    assert failed.availability is MetricAvailability.UNAVAILABLE
    assert failed.summary is None
    assert failed.failure == raw.metric_records[1].failure
    assert raw_path.read_bytes() == raw_bytes
    assert SECRET not in output.read_text() + result.output
