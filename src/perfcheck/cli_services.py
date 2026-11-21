"""Artifact-oriented services used by the command-line boundary."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final, assert_never, cast, override

from pydantic import ValidationError
from rich.console import Console

from perfcheck.bootstrap import CohortBootstrapOptions
from perfcheck.errors import PerfcheckError
from perfcheck.model_types import MetricAvailability
from perfcheck.policy import comparison_fingerprint
from perfcheck.policy_models import SuitePolicy
from perfcheck.run_models import RunArtifact
from perfcheck.storage import (
    artifact_content_sha256,
    canonical_json_bytes_dict,
    load_artifact,
    policy_content_sha256,
    summary_cache_path,
    write_artifact,
    write_bytes,
)
from perfcheck.summarize import MetricSummaryInput, summarize
from perfcheck.summary_models import SummaryArtifact, SummaryMetricRecord

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import JsonValue

    from perfcheck.artifact_models import Artifact
    from perfcheck.collection_models import MetricCollectionRecord


class CliInputCode(StrEnum):
    """Stable command-boundary input diagnostics."""

    INVALID_POLICY_JSON = "invalid policy JSON"
    POLICY_HASH_MISMATCH = "policy hash mismatch"
    REPORT_REQUIRED = "at least one of --report-json or --report-md is required"
    OUTPUT_PATHS_DISTINCT = "output paths must be distinct"
    OUTPUT_EXISTS = "output path already exists; use --force to replace it"
    AVAILABLE_SERIES_MISSING = "available metric is missing its series"
    UNAVAILABLE_FAILURE_MISSING = "unavailable metric is missing its failure"
    SUMMARY_CONTENT_HASH_MISMATCH = "summary content hash mismatch"
    SUMMARY_POLICY_HASH_MISMATCH = "summary policy hash mismatch"
    POLICY_MISMATCH = "policy mismatch"


_console = Console(stderr=True)


SCHEMA_KEY: Final[str] = "$schema"

SCHEMA_VERSIONS: Final[dict[int, str]] = {
    1: "schemas/v1/perfcheck-policy.schema.json",
}
CURRENT_SCHEMA_VERSION: Final[int] = 1

_SCHEMA_POINTER_MAJOR_RE: Final = re.compile(r"/v(\d+)")


def schema_pointer(path: Path) -> str | None:
    """Return the top-level ``$schema`` pointer from a policy file, or ``None``."""
    try:
        parsed = cast("JsonValue", json.loads(path.read_text(encoding="utf-8")))
    except OSError, ValueError:
        return None
    if not isinstance(parsed, dict):
        return None
    pointer = parsed.get(SCHEMA_KEY)
    return pointer if isinstance(pointer, str) else None


def warn_schema_pointer(pointer: str | None) -> None:
    """Warn on stderr when a policy ``$schema`` pointer is unknown or older."""
    if pointer is None:
        return
    major = _schema_pointer_major(pointer)
    if major is None or major not in SCHEMA_VERSIONS or major < CURRENT_SCHEMA_VERSION:
        template = (
            "warning: policy $schema pointer {!r} is unknown or older "
            "than the current schema version {}"
        )
        _console.print(template.format(pointer, CURRENT_SCHEMA_VERSION))


def _schema_pointer_major(pointer: str | None) -> int | None:
    """Extract the ``v<major>`` major version from a pointer, or ``None``."""
    if pointer is None:
        return None
    match = _SCHEMA_POINTER_MAJOR_RE.search(pointer)
    if match is None:
        return None
    return int(match.group(1))


@dataclass(frozen=True, slots=True)
class CliInputError(PerfcheckError):
    """An input or output contract could not be satisfied."""

    code: CliInputCode

    @override
    def __str__(self) -> str:
        """Render the stable command diagnostic."""
        return self.code


def load_policy(path: Path) -> SuitePolicy:
    """Parse and verify one policy snapshot before using it for analysis."""
    try:
        parsed = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
        body = {key: value for key, value in dict(parsed).items() if key != SCHEMA_KEY}
        policy = SuitePolicy.model_validate_json(json.dumps(body))
    except (
        OSError,
        UnicodeDecodeError,
        TypeError,
        ValueError,
        ValidationError,
    ) as error:
        raise CliInputError(CliInputCode.INVALID_POLICY_JSON) from error
    if policy.policy_sha256 != policy_content_sha256(policy):
        raise CliInputError(CliInputCode.POLICY_HASH_MISMATCH)
    return policy


def stamp_policy(path: Path) -> bytes:
    """Validate one policy and return canonical JSON stamped with its content hash.

    The input policy may be unsigned or carry a stale ``policy_sha256``: the
    returned canonical JSON always carries the correct self-referential hash,
    so ``load_policy`` accepts it unchanged. A top-level ``$schema`` pointer is
    captured before validation and re-injected verbatim into the canonical
    output; it never affects validation or the policy content hash. Invalid JSON
    or a schema failure fails the same way ``collect`` and ``compare`` reject a
    policy.
    """
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = cast("JsonValue", json.loads(raw))
        pointer: JsonValue | None = None
        body: dict[str, JsonValue] = {}
        if isinstance(parsed, dict):
            pointer = parsed.get(SCHEMA_KEY)
            body = {key: value for key, value in parsed.items() if key != SCHEMA_KEY}
        candidate = SuitePolicy.model_validate_json(
            json.dumps({**body, "policy_sha256": "0" * 64})
        )
    except (OSError, TypeError, ValueError, ValidationError) as error:
        raise CliInputError(CliInputCode.INVALID_POLICY_JSON) from error
    stamped = candidate.model_dump(mode="json")
    stamped["policy_sha256"] = policy_content_sha256(candidate)
    if pointer is not None:
        stamped[SCHEMA_KEY] = pointer
    return canonical_json_bytes_dict(stamped)


def load_raw(path: Path) -> RunArtifact:
    """Load one verified raw artifact under its declared policy identity."""
    return load_artifact(path)


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
        case _:
            assert_never(artifact)


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
    if len(paths) != len({path.resolve() for path in paths}):
        raise CliInputError(CliInputCode.OUTPUT_PATHS_DISTINCT)
    if not force and any(path.exists() for path in paths):
        raise CliInputError(CliInputCode.OUTPUT_EXISTS)


def write_report(path: Path, content: bytes, force: bool) -> None:
    """Atomically write one report without exposing a partial destination."""
    write_bytes(path, content, force=force)


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
        case _:
            assert_never(cached)


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
        case _:
            assert_never(record.availability)


def _verify_summary(summary: SummaryArtifact) -> None:
    if summary.content_sha256 != artifact_content_sha256(summary):
        raise CliInputError(CliInputCode.SUMMARY_CONTENT_HASH_MISMATCH)
    if summary.policy_sha256 != policy_content_sha256(summary.policy_snapshot):
        raise CliInputError(CliInputCode.SUMMARY_POLICY_HASH_MISMATCH)


def _require_policy(actual: str, policy: SuitePolicy) -> None:
    if actual != policy.policy_sha256:
        raise CliInputError(CliInputCode.POLICY_MISMATCH)
