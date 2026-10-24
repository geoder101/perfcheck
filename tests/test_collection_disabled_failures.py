from __future__ import annotations

from pathlib import Path  # noqa: TC003 - pytest resolves fixture annotations.

import httpx2
import pytest

from perfcheck.model_types import CollectionFailureReason, MetricAvailability
from perfcheck.run_models import RunArtifact
from perfcheck.storage import load_artifact
from tests.collection_failure_support import (
    SECRET,
    collect_cli,
    failure_policy,
    install_transport,
)


@pytest.mark.parametrize("enabled", [True, False], ids=["enabled", "disabled-only"])
def test_collect_exit_tracks_enabled_failures_without_dropping_evidence(
    enabled: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: only the failing metric changes its enabled policy flag.
    policy = failure_policy(enabled=enabled)
    install_transport(
        monkeypatch,
        lambda _: httpx2.Response(503, text=f"Bearer {SECRET}"),
    )

    # When: the CLI collects the healthy and failing metrics.
    result = collect_cli(tmp_path, policy)

    # Then: disabled failures remain evidence but do not fail CI.
    assert result.exit_code == (4 if enabled else 0), repr(result.exception)
    raw = load_artifact(tmp_path / "raw.json")
    assert isinstance(raw, RunArtifact)
    assert raw.policy_snapshot == policy
    healthy, failed = raw.metric_records
    assert healthy.availability is MetricAvailability.AVAILABLE
    assert failed.metric_id == "failed"
    assert failed.availability is MetricAvailability.UNAVAILABLE
    assert failed.failure is not None
    assert failed.failure.reason is CollectionFailureReason.TRANSPORT_ERROR
    assert failed.failure.detail == "Prometheus collection failed: http_error"
    assert failed.provenance.http_status == 503
    assert SECRET not in (tmp_path / "raw.json").read_text() + result.output
