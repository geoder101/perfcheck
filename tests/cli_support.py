"""Small, valid evidence builders for focused CLI tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, Literal, assert_never

from perfcheck.cli_services import summarize_raw
from perfcheck.collection_models import (
    FloatSample,
    LabelledMetricSeries,
    MetricCollectionRecord,
    QueryProvenance,
    SourceInterval,
)
from perfcheck.model_types import (
    Direction,
    MetricAvailability,
    MetricId,
    MetricUnit,
    Statistic,
)
from perfcheck.policy_models import MetricPolicy, SuitePolicy
from perfcheck.run_models import RunArtifact, RunMetadata
from perfcheck.storage import (
    artifact_content_sha256,
    policy_content_sha256,
    summary_cache_path,
    write_artifact,
)

if TYPE_CHECKING:
    from pathlib import Path

_BASE: Final = datetime(2026, 1, 1, tzinfo=UTC)
type SummaryInputKind = Literal[
    "tampered", "other-policy", "corrupt-cache", "source-mismatch"
]


def cli_policy() -> SuitePolicy:
    initial = SuitePolicy(
        policy_id="policy-1",
        suite_id="suite-1",
        policy_sha256="0" * 64,
        min_baseline_reference_runs=1,
        metrics=(
            MetricPolicy(
                metric_id=MetricId("latency"),
                query="latency_seconds",
                unit=MetricUnit.SECONDS,
                direction=Direction.HIGHER_IS_WORSE,
                statistic=Statistic.MEAN,
                practical_threshold=0.0,
                step_seconds=15,
                rate_window_seconds=60,
            ),
        ),
    )
    return initial.model_copy(update={"policy_sha256": policy_content_sha256(initial)})


def cli_run(policy: SuitePolicy, index: int, value: float) -> RunArtifact:
    interval = SourceInterval(
        start=_BASE + timedelta(hours=index),
        end=_BASE + timedelta(hours=index, minutes=10),
    )
    initial = RunArtifact(
        content_sha256="0" * 64,
        run_id=f"run-{index}",
        suite_id=policy.suite_id,
        source_interval=interval,
        policy_sha256=policy.policy_sha256,
        policy_snapshot=policy,
        metadata=RunMetadata(
            test_name="load-test",
            git_sha="abcdef",
            environment="ci",
            scenario="baseline",
            target_topology="single-node",
        ),
        metric_records=(
            MetricCollectionRecord(
                metric_id=MetricId("latency"),
                availability=MetricAvailability.AVAILABLE,
                provenance=QueryProvenance(
                    endpoint_url="https://metrics.example.test",
                    query="latency_seconds",
                    start=interval.start,
                    end=interval.end,
                    step_seconds=15,
                ),
                series=LabelledMetricSeries(
                    metric_id=MetricId("latency"),
                    samples=tuple(
                        FloatSample(
                            timestamp=interval.start + timedelta(seconds=15 * sample),
                            value=value,
                        )
                        for sample in range(41)
                    ),
                ),
            ),
        ),
    )
    return initial.model_copy(
        update={"content_sha256": artifact_content_sha256(initial)}
    )


def write_cli_policy(path: Path, policy: SuitePolicy) -> None:
    _ = path.write_text(policy.model_dump_json(), encoding="utf-8")


def write_cli_summary(path: Path, raw: RunArtifact) -> None:
    write_artifact(path, summarize_raw(raw, raw.policy_snapshot), source_run=raw)


def compare_inputs(directory: Path, *, multi_run: bool = False) -> list[str]:
    policy = cli_policy()
    policy_path = directory / "policy.json"
    write_cli_policy(policy_path, policy)
    arguments = ["compare", "--policy", str(policy_path)]
    counts = (
        (policy.min_current_runs, policy.min_baseline_runs) if multi_run else (1, 1)
    )
    index = 0
    for cohort, count in zip(("current", "baseline"), counts, strict=True):
        for member in range(count):
            index += 1
            path = directory / f"{cohort}-{member}.json"
            value = 9.0 if multi_run else 11.0
            write_artifact(
                path, cli_run(policy, index, value if cohort == "current" else 10.0)
            )
            arguments.extend([f"--{cohort}", str(path)])
    return arguments


def rejected_summary_input(
    directory: Path,
    kind: SummaryInputKind,
) -> tuple[list[str], Path]:
    arguments = compare_inputs(directory)
    policy = cli_policy()
    raw = cli_run(policy, 1, 11.0)
    path = directory / "current-0.json"
    match kind:
        case "tampered":
            summary = summarize_raw(raw, raw.policy_snapshot)
            summary = summary.model_copy(update={"summary_id": "token=fixture-secret"})
            _ = path.write_text(summary.model_dump_json(), encoding="utf-8")
        case "other-policy":
            other = policy.model_copy(update={"policy_id": "token=fixture-secret"})
            other = other.model_copy(
                update={"policy_sha256": policy_content_sha256(other)}
            )
            raw = cli_run(other, 1, 11.0)
            write_artifact(path, summarize_raw(raw, other), force=True, source_run=raw)
        case "corrupt-cache":
            path = summary_cache_path(path, policy.policy_sha256)
            _ = path.write_bytes(b'{"token":"fixture-secret"}')
        case "source-mismatch":
            path = summary_cache_path(path, policy.policy_sha256)
            write_cli_summary(path, cli_run(policy, 99, 10.0))
        case _:
            assert_never(kind)
    return arguments, path
