"""Artifact-oriented services used by the command-line boundary."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError
from rich.console import Console

from perfcheck.bootstrap import CohortBootstrapOptions
from perfcheck.errors import PerfcheckError
from perfcheck.model_types import MetricAvailability, StrEnum
from perfcheck.policy import comparison_fingerprint
from perfcheck.policy_models import SuitePolicy
from perfcheck.run_models import RunArtifact
from perfcheck.storage import (
    artifact_content_sha256,
    load_artifact,
    policy_content_sha256,
    summary_cache_path,
    write_artifact,
)
from perfcheck.summarize import MetricSummaryInput, summarize
from perfcheck.summary_models import SummaryArtifact, SummaryMetricRecord

if TYPE_CHECKING:
    from perfcheck.artifact_models import Artifact
    from perfcheck.collection_models import MetricCollectionRecord


class CliInputCode(StrEnum):
    """Stable command-boundary input diagnostics."""

    INVALID_POLICY_JSON = "invalid policy JSON"
    POLICY_HASH_MISMATCH = "policy hash mismatch"
    RUN_REQUIRED = "run input must be a raw run artifact"
    OUTPUT_PATHS_DISTINCT = "output paths must be distinct"
    OUTPUT_EXISTS = "output path already exists; use --force to replace it"
    AVAILABLE_SERIES_MISSING = "available metric is missing its series"
    UNAVAILABLE_FAILURE_MISSING = "unavailable metric is missing its failure"
    SUMMARY_CONTENT_HASH_MISMATCH = "summary content hash mismatch"
    SUMMARY_POLICY_HASH_MISMATCH = "summary policy hash mismatch"
    POLICY_MISMATCH = "policy mismatch"


_console = Console(stderr=True)


@dataclass(frozen=True, slots=True)
class CliInputError(PerfcheckError):
    """An input or output contract could not be satisfied."""

    code: CliInputCode

    def __str__(self) -> str:
        """Render the stable command diagnostic."""
        return self.code


def load_policy(path: Path) -> SuitePolicy:
    """Parse and verify one policy snapshot before using it for analysis."""
    try:
        policy = SuitePolicy.model_validate_json(path.read_bytes())
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise CliInputError(CliInputCode.INVALID_POLICY_JSON) from error
    if policy.policy_sha256 != policy_content_sha256(policy):
        raise CliInputError(CliInputCode.POLICY_HASH_MISMATCH)
    return policy


def load_raw(path: Path) -> RunArtifact:
    """Load one verified raw artifact under its declared policy identity."""
    artifact = load_artifact(path)
    match artifact:
        case RunArtifact() as raw:
            return raw
        case SummaryArtifact():
            raise CliInputError(CliInputCode.RUN_REQUIRED)


def effective_summary(
    path: Path, policy: SuitePolicy, write_cache: bool
) -> SummaryArtifact:
    """Load a summary or derive an in-memory policy-compatible raw summary."""
    artifact = _load_input_artifact(path)
    match artifact:
        case SummaryArtifact() as summary:
            _verify_summary(summary)
            _require_policy(summary.policy_sha256, policy)
            return summary
        case RunArtifact() as raw:
            _require_policy(raw.policy_sha256, policy)
            cache_path = summary_cache_path(path, policy.policy_sha256)
            summary = _cached_or_derived_summary(cache_path, raw, policy)
            if write_cache:
                write_artifact(cache_path, summary, force=True, source_run=raw)
            return summary


def summarize_raw(raw: RunArtifact, policy: SuitePolicy) -> SummaryArtifact:
    """Build a deterministic summary artifact from verified raw metric evidence."""
    _require_policy(raw.policy_sha256, policy)
    raw_records = {record.metric_id: record for record in raw.metric_records}
    records = tuple(
        _summarize_record(raw_records[metric.metric_id], raw, policy)
        for metric in policy.metrics
    )
    initial = SummaryArtifact(
        content_sha256="0" * 64,
        summary_id=f"{raw.run_id}.summary",
        source_run_id=raw.run_id,
        source_content_sha256=raw.content_sha256,
        source_interval=raw.source_interval,
        policy_sha256=policy.policy_sha256,
        policy_snapshot=policy,
        metric_records=records,
    )
    return initial.model_copy(
        update={"content_sha256": artifact_content_sha256(initial)}
    )


def options(seed: int | None, resamples: int | None) -> CohortBootstrapOptions | None:
    """Retain optional bootstrap overrides for regression's method validation."""
    if seed is None and resamples is None:
        return None
    return CohortBootstrapOptions(
        seed=42 if seed is None else seed,
        requested_resamples=10_000 if resamples is None else resamples,
    )


def preflight_paths(paths: tuple[Path, ...], force: bool) -> None:
    """Reject existing or duplicate explicit destinations before any mutation."""
    if len(paths) != len(set(paths)):
        raise CliInputError(CliInputCode.OUTPUT_PATHS_DISTINCT)
    if not force and any(path.exists() for path in paths):
        raise CliInputError(CliInputCode.OUTPUT_EXISTS)


def write_report(path: Path, content: bytes, force: bool) -> None:
    """Atomically write one report without exposing a partial destination."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        temporary.write(content)
        temporary.flush()
        os.fsync(temporary.fileno())
    try:
        if force:
            temporary_path.replace(path)
        else:
            os.link(temporary_path, path)
            temporary_path.unlink()
    finally:
        temporary_path.unlink(missing_ok=True)


def _load_input_artifact(path: Path) -> Artifact:
    try:
        artifact = load_artifact(path)
    except PerfcheckError as error:
        try:
            summary = SummaryArtifact.model_validate_json(path.read_bytes())
        except (OSError, UnicodeDecodeError, ValidationError) as summary_error:
            raise error from summary_error
        _verify_summary(summary)
        return summary
    return artifact


def _cached_or_derived_summary(
    cache_path: Path, raw: RunArtifact, policy: SuitePolicy
) -> SummaryArtifact:
    if not cache_path.exists():
        _console.print(f"summary cache miss run={raw.run_id} hash={raw.content_sha256}")
        return summarize_raw(raw, policy)
    cached = load_artifact(cache_path, source_run=raw)
    match cached:
        case SummaryArtifact() as summary if (
            summary.policy_sha256 == policy.policy_sha256
        ):
            _console.print(
                f"summary cache hit run={raw.run_id} hash={raw.content_sha256}"
            )
            return summary
        case SummaryArtifact() | RunArtifact():
            _console.print(
                f"summary cache miss run={raw.run_id} hash={raw.content_sha256}"
            )
            return summarize_raw(raw, policy)


def _summarize_record(
    record: MetricCollectionRecord, raw: RunArtifact, policy: SuitePolicy
) -> SummaryMetricRecord:
    metric = next(
        metric for metric in policy.metrics if metric.metric_id == record.metric_id
    )
    match record.availability:
        case MetricAvailability.AVAILABLE:
            if record.series is None:
                raise CliInputError(CliInputCode.AVAILABLE_SERIES_MISSING)
            return SummaryMetricRecord(
                metric_id=record.metric_id,
                availability=MetricAvailability.AVAILABLE,
                summary=summarize(
                    MetricSummaryInput(
                        source_interval=raw.source_interval,
                        policy=metric,
                        compatibility_fingerprint=comparison_fingerprint(
                            policy, metric
                        ),
                        samples=record.series.samples,
                    )
                ),
            )
        case MetricAvailability.UNAVAILABLE:
            if record.failure is None:
                raise CliInputError(CliInputCode.UNAVAILABLE_FAILURE_MISSING)
            return SummaryMetricRecord(
                metric_id=record.metric_id,
                availability=MetricAvailability.UNAVAILABLE,
                failure=record.failure,
            )


def _verify_summary(summary: SummaryArtifact) -> None:
    if summary.content_sha256 != artifact_content_sha256(summary):
        raise CliInputError(CliInputCode.SUMMARY_CONTENT_HASH_MISMATCH)
    if summary.policy_sha256 != policy_content_sha256(summary.policy_snapshot):
        raise CliInputError(CliInputCode.SUMMARY_POLICY_HASH_MISMATCH)


def _require_policy(actual: str, policy: SuitePolicy) -> None:
    if actual != policy.policy_sha256:
        raise CliInputError(CliInputCode.POLICY_MISMATCH)
