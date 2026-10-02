"""Policy-derived comparison fingerprints and cohort eligibility selection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from typing import TYPE_CHECKING, Final

from perfcheck.model_types import ComparisonMethod, ComparisonMode

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from perfcheck.policy_models import MetricPolicy, SuitePolicy

_RECOMMENDED_MINIMUM_CURRENT_RUNS: Final = 5
_RECOMMENDED_MINIMUM_BASELINE_RUNS: Final = 10


class ComparabilityReason(StrEnum):
    """Stable reasons a cohort cannot produce a comparison decision."""

    POLICY_SHA256_MISMATCH = "policy_sha256_mismatch"
    METRIC_FINGERPRINT_MISMATCH = "metric_fingerprint_mismatch"
    DUPLICATE_SOURCE_RUN_ID = "duplicate_source_run_id"
    DUPLICATE_SOURCE_CONTENT_SHA256 = "duplicate_source_content_sha256"
    OVERLAPPING_SOURCE_INTERVAL = "overlapping_source_interval"
    INSUFFICIENT_CURRENT_RUNS = "insufficient_current_runs"
    INSUFFICIENT_BASELINE_RUNS = "insufficient_baseline_runs"
    BASELINE_REFERENCE_REQUIRES_ONE_CURRENT_RUN = (
        "baseline_reference_requires_one_current_run"
    )


@dataclass(frozen=True, slots=True)
class ComparisonInput:
    """Validated comparison provenance needed before a decision can run."""

    source_run_id: str
    source_content_sha256: str
    interval_start: datetime
    interval_end: datetime
    policy_sha256: str
    metric_fingerprints: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComparisonSelection:
    """A validated mode choice or one exact inconclusive reason."""

    method: ComparisonMethod | None
    reason: ComparabilityReason | None
    alpha_effective: float
    small_cohort_warning: bool


def comparison_fingerprint(policy: SuitePolicy, metric: MetricPolicy) -> str:
    """Hash the metric fields that must remain identical across compared runs."""
    payload = {
        "benchmark_id": policy.suite_id,
        "metric_name": metric.metric_id,
        "query": metric.query,
        "expected_label_names": metric.expected_label_names,
        "unit": metric.unit,
        "direction": metric.direction,
        "statistic": metric.statistic,
        "step_seconds": metric.step_seconds,
        "rate_window_seconds": metric.rate_window_seconds,
        "eligibility": metric.eligibility.model_dump(mode="json"),
        "policy_version": policy.schema_version,
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def select_comparison(
    policy: SuitePolicy,
    current: Sequence[ComparisonInput],
    baseline: Sequence[ComparisonInput],
) -> ComparisonSelection:
    """Reject incomparable cohorts before deterministically selecting a method."""
    alpha_effective = policy.nominal_alpha / _enabled_gate_count(policy)
    mismatch = _comparability_mismatch(policy, current, baseline)
    if mismatch is not None:
        return ComparisonSelection(
            method=None,
            reason=mismatch,
            alpha_effective=alpha_effective,
            small_cohort_warning=False,
        )

    match policy.comparison_mode:
        case ComparisonMode.AUTO:
            return _select_auto(policy, current, baseline, alpha_effective)
        case ComparisonMode.BASELINE_REFERENCE:
            return _select_baseline_reference(
                policy, current, baseline, alpha_effective
            )
        case ComparisonMode.COHORT_BOOTSTRAP:
            return _select_cohort_bootstrap(policy, current, baseline, alpha_effective)


def _enabled_gate_count(policy: SuitePolicy) -> int:
    return sum(metric.enabled for metric in policy.metrics)


def _comparability_mismatch(
    policy: SuitePolicy,
    current: Sequence[ComparisonInput],
    baseline: Sequence[ComparisonInput],
) -> ComparabilityReason | None:
    inputs = (*current, *baseline)
    expected_fingerprints = tuple(
        comparison_fingerprint(policy, metric) for metric in policy.metrics
    )
    if any(
        comparison_input.policy_sha256 != policy.policy_sha256
        for comparison_input in inputs
    ):
        return ComparabilityReason.POLICY_SHA256_MISMATCH
    if any(
        comparison_input.metric_fingerprints != expected_fingerprints
        for comparison_input in inputs
    ):
        return ComparabilityReason.METRIC_FINGERPRINT_MISMATCH
    source_run_ids = tuple(
        comparison_input.source_run_id for comparison_input in inputs
    )
    if len(source_run_ids) != len(set(source_run_ids)):
        return ComparabilityReason.DUPLICATE_SOURCE_RUN_ID
    source_content_hashes = tuple(
        comparison_input.source_content_sha256 for comparison_input in inputs
    )
    if len(source_content_hashes) != len(set(source_content_hashes)):
        return ComparabilityReason.DUPLICATE_SOURCE_CONTENT_SHA256
    if _has_overlapping_intervals(inputs):
        return ComparabilityReason.OVERLAPPING_SOURCE_INTERVAL
    return None


def _has_overlapping_intervals(inputs: Sequence[ComparisonInput]) -> bool:
    ordered = tuple(
        sorted(inputs, key=lambda comparison_input: comparison_input.interval_start)
    )
    return any(
        later.interval_start <= earlier.interval_end
        for earlier, later in pairwise(ordered)
    )


def _select_auto(
    policy: SuitePolicy,
    current: Sequence[ComparisonInput],
    baseline: Sequence[ComparisonInput],
    alpha_effective: float,
) -> ComparisonSelection:
    if len(current) == 1:
        return _select_baseline_reference(policy, current, baseline, alpha_effective)
    return _select_cohort_bootstrap(policy, current, baseline, alpha_effective)


def _select_baseline_reference(
    policy: SuitePolicy,
    current: Sequence[ComparisonInput],
    baseline: Sequence[ComparisonInput],
    alpha_effective: float,
) -> ComparisonSelection:
    if len(current) != 1:
        return ComparisonSelection(
            method=None,
            reason=ComparabilityReason.BASELINE_REFERENCE_REQUIRES_ONE_CURRENT_RUN,
            alpha_effective=alpha_effective,
            small_cohort_warning=False,
        )
    if len(baseline) < policy.min_baseline_reference_runs:
        return ComparisonSelection(
            method=None,
            reason=ComparabilityReason.INSUFFICIENT_BASELINE_RUNS,
            alpha_effective=alpha_effective,
            small_cohort_warning=False,
        )
    return ComparisonSelection(
        ComparisonMethod.BASELINE_REFERENCE,
        None,
        alpha_effective,
        _small_cohort_warning(current, baseline),
    )


def _select_cohort_bootstrap(
    policy: SuitePolicy,
    current: Sequence[ComparisonInput],
    baseline: Sequence[ComparisonInput],
    alpha_effective: float,
) -> ComparisonSelection:
    if len(current) < policy.min_current_runs:
        return ComparisonSelection(
            method=None,
            reason=ComparabilityReason.INSUFFICIENT_CURRENT_RUNS,
            alpha_effective=alpha_effective,
            small_cohort_warning=False,
        )
    if len(baseline) < policy.min_baseline_runs:
        return ComparisonSelection(
            method=None,
            reason=ComparabilityReason.INSUFFICIENT_BASELINE_RUNS,
            alpha_effective=alpha_effective,
            small_cohort_warning=False,
        )
    return ComparisonSelection(
        ComparisonMethod.COHORT_BOOTSTRAP,
        None,
        alpha_effective,
        _small_cohort_warning(current, baseline),
    )


def _small_cohort_warning(
    current: Sequence[ComparisonInput], baseline: Sequence[ComparisonInput]
) -> bool:
    return (
        len(current) < _RECOMMENDED_MINIMUM_CURRENT_RUNS
        or len(baseline) < _RECOMMENDED_MINIMUM_BASELINE_RUNS
    )
