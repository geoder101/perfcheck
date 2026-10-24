from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from perfcheck.cli_services import summarize_raw
from perfcheck.collection_models import (
    CollectionFailure,
    FloatSample,
    LabelledMetricSeries,
    MetricCollectionRecord,
    QueryProvenance,
    SourceInterval,
)
from perfcheck.model_types import (
    CollectionFailureReason,
    ComparisonMode,
    Direction,
    MetricAvailability,
    MetricId,
    MetricUnit,
    Statistic,
)
from perfcheck.policy_models import MetricPolicy, SuitePolicy
from perfcheck.run_models import RunArtifact, RunMetadata
from perfcheck.storage import artifact_content_sha256, policy_content_sha256

if TYPE_CHECKING:
    from perfcheck.summary_models import SummaryArtifact


def boundary_metric(name: str, *, enabled: bool = True) -> MetricPolicy:
    return MetricPolicy(
        metric_id=MetricId(name),
        query=f"{name}_seconds",
        unit=MetricUnit.SECONDS,
        direction=Direction.HIGHER_IS_WORSE,
        statistic=Statistic.MEAN,
        practical_threshold=5.0,
        step_seconds=15,
        rate_window_seconds=60,
        enabled=enabled,
    )


def boundary_policy(
    metrics: tuple[MetricPolicy, ...],
    mode: ComparisonMode = ComparisonMode.COHORT_BOOTSTRAP,
) -> SuitePolicy:
    initial = SuitePolicy(
        policy_id="boundary-policy",
        suite_id="boundary-suite",
        policy_sha256="0" * 64,
        metrics=metrics,
        comparison_mode=mode,
        min_current_runs=3,
        min_baseline_runs=4,
        min_baseline_reference_runs=6,
    )
    return SuitePolicy.model_validate(
        initial.model_dump() | {"policy_sha256": policy_content_sha256(initial)}
    )


def boundary_summary(
    policy: SuitePolicy, index: int, values: tuple[float | None, ...]
) -> SummaryArtifact:
    interval = SourceInterval(
        start=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index),
        end=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index, minutes=10),
    )
    records: list[MetricCollectionRecord] = []
    for metric, value in zip(policy.metrics, values, strict=True):
        provenance = QueryProvenance(
            endpoint_url="https://metrics.example.test",
            query=metric.query,
            start=interval.start,
            end=interval.end,
            step_seconds=metric.step_seconds,
        )
        if value is None:
            records.append(
                MetricCollectionRecord(
                    metric_id=metric.metric_id,
                    availability=MetricAvailability.UNAVAILABLE,
                    provenance=provenance,
                    failure=CollectionFailure(
                        reason=CollectionFailureReason.TIMEOUT,
                        detail="request timed out",
                    ),
                )
            )
        else:
            records.append(
                MetricCollectionRecord(
                    metric_id=metric.metric_id,
                    availability=MetricAvailability.AVAILABLE,
                    provenance=provenance,
                    series=LabelledMetricSeries(
                        metric_id=metric.metric_id,
                        samples=tuple(
                            FloatSample(
                                timestamp=interval.start + timedelta(seconds=15 * n),
                                value=value,
                            )
                            for n in range(41)
                        ),
                    ),
                )
            )
    initial = RunArtifact(
        content_sha256="0" * 64,
        run_id=f"run-{index:02}",
        suite_id=policy.suite_id,
        source_interval=interval,
        policy_sha256=policy.policy_sha256,
        policy_snapshot=policy,
        metadata=RunMetadata(
            test_name="boundary-test",
            git_sha="abcdef",
            environment="ci",
            scenario="comparison",
            target_topology="single-node",
        ),
        metric_records=tuple(records),
    )
    raw = RunArtifact.model_validate(
        initial.model_dump() | {"content_sha256": artifact_content_sha256(initial)}
    )
    return summarize_raw(raw, policy)
