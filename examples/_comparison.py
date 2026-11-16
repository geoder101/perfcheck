"""Faithful, transparent mirror of the perfcheck comparison core, teaching only.

This module is an educational reimplementation of the ``perfcheck`` ``compare``
decision flow. It is **not** production code, **not** evidence, and **not** a
public API: the supported product surface remains the ``perfcheck`` CLI. The
mirror reproduces production's decisions and seeded draw in substance so a reader
can follow the algorithm top to bottom, but it never imports or calls the
internal ``perfcheck`` modules.

The flow mirrors ``src/perfcheck``:

* ``oriented`` multiplies values by ``1``/``-1`` so a positive effect always
  means a worsening metric (see ``bootstrap_sampling.oriented_float64_values``).
* ``eligible_cohort`` classifies each run as kept / missing / unavailable /
  ineligible (see ``regression_cohorts.eligible_metric_cohort``).
* ``select_comparison`` rejects incomparable cohorts then routes to a method
  with the recommended minima (see ``policy.select_comparison``).
* ``bootstrap_cohort`` draws interleaved PCG64 current-then-baseline means and
  selects a linear lower bound (see ``bootstrap_sampling.bootstrap_metric``).
* ``reference_cohort`` takes the advisory baseline tail (see
  ``bootstrap_reference.reference_metric``).
* ``evaluate_flow`` dispatches disabled -> excluded -> inconclusive ->
  reference -> cohort (see ``regression_metrics.evaluate_metric``).
* ``aggregate_status`` reduces enabled outcomes with FAIL>INCONCLUSIVE>PASS
  (see ``regression_aggregation.aggregate_status``).
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from itertools import pairwise
from typing import TYPE_CHECKING, Final, assert_never

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

type FloatVector = npt.NDArray[np.float64]

_DEFAULT_SEED: Final = 42
_MINIMUM_RESAMPLES_PER_ENABLED_METRIC: Final = 2_000
_DEFAULT_REQUESTED_RESAMPLES: Final = 10_000
_DIAGNOSTIC_QUANTILES: Final = (0.025, 0.975)
_RECOMMENDED_MINIMUM_CURRENT_RUNS: Final = 5
_RECOMMENDED_MINIMUM_BASELINE_RUNS: Final = 10
_OK_STATUS: Final = "pass"
_POLICY_SHA256: Final = "a" * 64
_FINGERPRINT: Final = "c" * 64
_YEAR_DAYS: Final = 365
_BASE_INSTANT: Final = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)


class Direction(StrEnum):
    """The direction in which a metric worsens (educational mirror vocabulary)."""

    HIGHER_IS_WORSE = "higher_is_worse"
    LOWER_IS_WORSE = "lower_is_worse"


class Status(StrEnum):
    """Possible decision outcomes (educational mirror vocabulary)."""

    PASS = _OK_STATUS
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class MetricReason(StrEnum):
    """Why a run is withheld or a metric is skipped (educational mirror)."""

    METRIC_DISABLED = "metric_disabled"
    METRIC_INELIGIBLE = "metric_ineligible"
    METRIC_MISSING = "missing_metric"
    METRIC_UNAVAILABLE = "metric_unavailable"


class Cohort(StrEnum):
    """The source cohort of a metric exclusion (educational mirror)."""

    CURRENT = "current"
    BASELINE = "baseline"


class ComparisonMode(StrEnum):
    """Policy-selected comparison modes (educational mirror vocabulary)."""

    AUTO = "auto"
    BASELINE_REFERENCE = "baseline_reference"
    COHORT_BOOTSTRAP = "cohort_bootstrap"


class ComparisonMethod(StrEnum):
    """Methods recorded in comparison outcomes (educational mirror)."""

    BASELINE_REFERENCE = "baseline_reference"
    COHORT_BOOTSTRAP = "cohort_bootstrap"


class ComparabilityReason(StrEnum):
    """Why cohorts cannot produce a decision (educational mirror)."""

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
class RunValue:
    """One kept per-run statistic and its canonical source identifier."""

    source_run_id: str
    value: float


@dataclass(frozen=True, slots=True)
class MetricExclusion:
    """One run withheld from one metric decision with its exact reason."""

    cohort: Cohort
    source_run_id: str
    reason: MetricReason


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
class EligibleCohort:
    """Usable scalar inputs, provenance, and exclusions for one metric cohort."""

    run_values: tuple[RunValue, ...]
    comparison_inputs: tuple[ComparisonInput, ...]
    exclusions: tuple[MetricExclusion, ...]


@dataclass(frozen=True, slots=True)
class RunRecord:
    """One run's raw metric value, eligibility, and comparison provenance."""

    value: float | None
    content_sha256: str
    policy_sha256: str
    metric_fingerprint: str
    interval_start: datetime
    interval_end: datetime
    collection_failure: str | None = None


@dataclass(frozen=True, slots=True)
class MetricComparisonInput:
    """Comparable run-level inputs for one metric under a selected policy."""

    metric_id: str
    direction: Direction
    requested_alpha: float
    effective_alpha: float
    practical_threshold: float
    current: tuple[RunValue, ...]
    baseline: tuple[RunValue, ...]
    sample_size_warning: bool = False


@dataclass(frozen=True, slots=True)
class CohortBootstrapResult:
    """Reproducible percentile-bootstrap evidence for one metric (mirror)."""

    metric_id: str
    direction: Direction
    method: ComparisonMethod
    requested_alpha: float
    effective_alpha: float
    observed_effect: float
    lower_decision_bound: float
    diagnostic_lower_bound: float
    diagnostic_upper_bound: float
    effective_seed: int
    requested_resamples: int
    effective_resamples: int
    current_sample_count: int
    baseline_sample_count: int
    sample_size_warning: bool


@dataclass(frozen=True, slots=True)
class BaselineReferenceResult:
    """Advisory reference evidence for one metric (mirror)."""

    metric_id: str
    direction: Direction
    method: ComparisonMethod
    requested_alpha: float
    effective_alpha: float
    reference_quantile: float
    reference_effect: float
    reference_anomaly: bool
    current_sample_count: int
    baseline_sample_count: int
    sample_size_warning: bool


@dataclass(frozen=True, slots=True)
class ComparisonSelection:
    """A validated mode choice or one exact inconclusive reason (mirror)."""

    method: ComparisonMethod | None
    reason: ComparabilityReason | None
    alpha_effective: float
    small_cohort_warning: bool


@dataclass(frozen=True, slots=True)
class MetricOutcome:
    """One metric's verdict, selected evidence, and filtered run provenance."""

    metric_id: str
    direction: Direction
    enabled: bool
    status: Status
    method: ComparisonMethod | None
    evidence: BaselineReferenceResult | CohortBootstrapResult | None
    reason: str | None
    exclusions: tuple[MetricExclusion, ...]


@dataclass(frozen=True, slots=True)
class BootstrapOptions:
    """Seeded bootstrap options including the enabled-metric alpha split count."""

    seed: int = _DEFAULT_SEED
    requested_resamples: int = _DEFAULT_REQUESTED_RESAMPLES
    enabled_metric_count: int = 1


@dataclass(frozen=True, slots=True)
class MetricLike:
    """One metric's comparison-relevant fields (educational mirror)."""

    metric_id: str
    query: str
    unit: str
    direction: Direction
    statistic: str
    practical_threshold: float
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class PolicyLike:
    """A policy snapshot the mirror routes and splits alpha over (educational)."""

    policy_sha256: str = _POLICY_SHA256
    suite_id: str = "mirror-suite"
    nominal_alpha: float = 0.05
    comparison_mode: ComparisonMode = ComparisonMode.AUTO
    min_current_runs: int = 5
    min_baseline_runs: int = 10
    min_baseline_reference_runs: int = 10
    metrics: tuple[MetricLike, ...] = ()


def oriented(
    values: tuple[float, ...], *, higher_is_worse: bool
) -> npt.NDArray[np.float64]:
    """Orient values so a positive effect always means a worsening metric.

    This is a faithful educational mirror of
    ``bootstrap_sampling.oriented_float64_values``: higher-is-worse values are
    left unchanged and lower-is-worse values are negated, so current minus
    baseline is positive for a worsening metric.
    """
    if not values:
        message = "oriented requires at least one value"
        raise ValueError(message)
    if not all(np.isfinite(value) for value in values):
        message = "oriented requires finite values"
        raise ValueError(message)
    orientation = 1.0 if higher_is_worse else -1.0
    return orientation * np.asarray(values, dtype=np.float64)


def eligible_cohort(
    records: Mapping[str, RunRecord | None],
    *,
    cohort: Cohort = Cohort.CURRENT,
) -> EligibleCohort:
    """Classify one cohort's runs into kept, missing, unavailable, ineligible.

    This is a faithful educational mirror of
    ``regression_cohorts.eligible_metric_cohort``: a ``None`` record means the
    run has no metric record (``METRIC_MISSING``), a record with a collection
    failure is ``METRIC_UNAVAILABLE``, a record without a value is
    ``METRIC_INELIGIBLE``, and every other run is kept as a ``RunValue`` with its
    comparison provenance.
    """
    run_values: list[RunValue] = []
    comparison_inputs: list[ComparisonInput] = []
    exclusions: list[MetricExclusion] = []
    for run_id, record in records.items():
        if record is None:
            exclusions.append(
                MetricExclusion(cohort, run_id, MetricReason.METRIC_MISSING)
            )
            continue
        if record.collection_failure is not None:
            exclusions.append(
                MetricExclusion(cohort, run_id, MetricReason.METRIC_UNAVAILABLE)
            )
            continue
        if record.value is None:
            exclusions.append(
                MetricExclusion(cohort, run_id, MetricReason.METRIC_INELIGIBLE)
            )
            continue
        run_values.append(RunValue(run_id, record.value))
        comparison_inputs.append(
            ComparisonInput(
                source_run_id=run_id,
                source_content_sha256=record.content_sha256,
                interval_start=record.interval_start,
                interval_end=record.interval_end,
                policy_sha256=record.policy_sha256,
                metric_fingerprints=(record.metric_fingerprint,),
            )
        )
    return EligibleCohort(
        run_values=tuple(run_values),
        comparison_inputs=tuple(comparison_inputs),
        exclusions=tuple(exclusions),
    )


def comparison_fingerprint(policy: PolicyLike, metric: MetricLike) -> str:
    """Hash the metric fields that must stay identical across compared runs.

    This is a faithful educational mirror of ``policy.comparison_fingerprint``:
    the comparison-relevant metric and policy fields are canonicalised and
    hashed so any drift makes two cohorts incomparable.
    """
    payload = {
        "suite_id": policy.suite_id,
        "metric_id": metric.metric_id,
        "query": metric.query,
        "unit": metric.unit,
        "direction": metric.direction,
        "statistic": metric.statistic,
        "threshold": metric.practical_threshold,
        "enabled": metric.enabled,
        "alpha": policy.nominal_alpha,
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def run_record(
    run_id: str,
    value: float | None,
    *,
    day: int,
    metric_fingerprint: str = _FINGERPRINT,
    collection_failure: str | None = None,
) -> RunRecord:
    """Build one run's raw record with a deterministic daily interval (mirror).

    This teaching helper mirrors how production attaches provenance and a
    source interval to each run; ``day`` places the run on a distinct,
    non-overlapping interval so comparable cohorts never overlap, and each run
    gets a unique content hash derived from its run id.
    """
    if not 0 <= day < _YEAR_DAYS:
        message = "run_record day must be within the base year"
        raise ValueError(message)
    if value is not None and not np.isfinite(value):
        message = "run_record value must be finite"
        raise ValueError(message)
    start = _BASE_INSTANT + timedelta(days=day)
    return RunRecord(
        value=value,
        content_sha256=_content_sha256(run_id),
        policy_sha256=_POLICY_SHA256,
        metric_fingerprint=metric_fingerprint,
        interval_start=start,
        interval_end=start + timedelta(minutes=10),
        collection_failure=collection_failure,
    )


def _content_sha256(run_id: str) -> str:
    """Derive a unique, stable content hash for one run id (educational mirror)."""
    return hashlib.sha256(run_id.encode()).hexdigest()


def _enabled_gate_count(policy: PolicyLike) -> int:
    """Count enabled metrics for the alpha split (faithful educational mirror).

    A mirror policy always has at least one enabled metric, so the alpha split
    below always divides by a positive gate count. Teaching material, not
    evidence, not a production API.
    """
    return sum(metric.enabled for metric in policy.metrics)


def select_comparison(
    policy: PolicyLike,
    current: Sequence[ComparisonInput],
    baseline: Sequence[ComparisonInput],
) -> ComparisonSelection:
    """Reject incomparable cohorts before deterministically selecting a method.

    This is a faithful educational mirror of ``policy.select_comparison``: it
    splits ``nominal_alpha`` over the enabled gate count, rejects incomparable
    cohorts, then routes AUTO/BASELINE_REFERENCE/COHORT_BOOTSTRAP with the
    recommended minima.
    """
    effective_alpha = policy.nominal_alpha / _enabled_gate_count(policy)
    mismatch = _comparability_mismatch(policy, current, baseline)
    if mismatch is not None:
        return ComparisonSelection(
            method=None,
            reason=mismatch,
            alpha_effective=effective_alpha,
            small_cohort_warning=False,
        )
    match policy.comparison_mode:
        case ComparisonMode.AUTO:
            return _select_auto(policy, current, baseline, effective_alpha)
        case ComparisonMode.BASELINE_REFERENCE:
            return _select_baseline_reference(
                policy, current, baseline, effective_alpha
            )
        case ComparisonMode.COHORT_BOOTSTRAP:
            return _select_cohort_bootstrap(policy, current, baseline, effective_alpha)
        case _:
            assert_never(policy.comparison_mode)


def _comparability_mismatch(
    policy: PolicyLike,
    current: Sequence[ComparisonInput],
    baseline: Sequence[ComparisonInput],
) -> ComparabilityReason | None:
    """Flag the first comparability failure across both cohorts (mirror).

    Faithful educational mirror of the comparability checks in
    ``policy.select_comparison``; teaching material, not evidence, not a
    production API.
    """
    inputs = (*current, *baseline)
    expected_fingerprints = tuple(
        comparison_fingerprint(policy, metric) for metric in policy.metrics
    )
    if any(ci.policy_sha256 != policy.policy_sha256 for ci in inputs):
        return ComparabilityReason.POLICY_SHA256_MISMATCH
    if any(ci.metric_fingerprints != expected_fingerprints for ci in inputs):
        return ComparabilityReason.METRIC_FINGERPRINT_MISMATCH
    source_run_ids = tuple(ci.source_run_id for ci in inputs)
    if len(source_run_ids) != len(set(source_run_ids)):
        return ComparabilityReason.DUPLICATE_SOURCE_RUN_ID
    source_content_hashes = tuple(ci.source_content_sha256 for ci in inputs)
    if len(source_content_hashes) != len(set(source_content_hashes)):
        return ComparabilityReason.DUPLICATE_SOURCE_CONTENT_SHA256
    if _has_overlapping_intervals(inputs):
        return ComparabilityReason.OVERLAPPING_SOURCE_INTERVAL
    return None


def _has_overlapping_intervals(inputs: Sequence[ComparisonInput]) -> bool:
    """Detect any overlapping source intervals (faithful educational mirror).

    Teaching material, not evidence, not a production API.
    """
    ordered = tuple(sorted(inputs, key=lambda ci: ci.interval_start))
    return any(
        later.interval_start <= earlier.interval_end
        for earlier, later in pairwise(ordered)
    )


def _select_auto(
    policy: PolicyLike,
    current: Sequence[ComparisonInput],
    baseline: Sequence[ComparisonInput],
    effective_alpha: float,
) -> ComparisonSelection:
    """Route AUTO mode to reference (one current run) or cohort bootstrap (mirror).

    Faithful educational mirror of the AUTO routing in
    ``policy.select_comparison``; teaching material, not evidence, not a
    production API.
    """
    if len(current) == 1:
        return _select_baseline_reference(policy, current, baseline, effective_alpha)
    return _select_cohort_bootstrap(policy, current, baseline, effective_alpha)


def _select_baseline_reference(
    policy: PolicyLike,
    current: Sequence[ComparisonInput],
    baseline: Sequence[ComparisonInput],
    effective_alpha: float,
) -> ComparisonSelection:
    """Validate the baseline-reference path and its minima (faithful mirror).

    Faithful educational mirror of the BASELINE_REFERENCE routing in
    ``policy.select_comparison``; teaching material, not evidence, not a
    production API.
    """
    if len(current) != 1:
        return ComparisonSelection(
            method=None,
            reason=ComparabilityReason.BASELINE_REFERENCE_REQUIRES_ONE_CURRENT_RUN,
            alpha_effective=effective_alpha,
            small_cohort_warning=False,
        )
    if len(baseline) < policy.min_baseline_reference_runs:
        return ComparisonSelection(
            method=None,
            reason=ComparabilityReason.INSUFFICIENT_BASELINE_RUNS,
            alpha_effective=effective_alpha,
            small_cohort_warning=False,
        )
    return ComparisonSelection(
        method=ComparisonMethod.BASELINE_REFERENCE,
        reason=None,
        alpha_effective=effective_alpha,
        small_cohort_warning=_small_cohort_warning(current, baseline),
    )


def _select_cohort_bootstrap(
    policy: PolicyLike,
    current: Sequence[ComparisonInput],
    baseline: Sequence[ComparisonInput],
    effective_alpha: float,
) -> ComparisonSelection:
    """Validate the cohort-bootstrap path and its minima (faithful mirror).

    Faithful educational mirror of the COHORT_BOOTSTRAP routing in
    ``policy.select_comparison``; teaching material, not evidence, not a
    production API.
    """
    if len(current) < policy.min_current_runs:
        return ComparisonSelection(
            method=None,
            reason=ComparabilityReason.INSUFFICIENT_CURRENT_RUNS,
            alpha_effective=effective_alpha,
            small_cohort_warning=False,
        )
    if len(baseline) < policy.min_baseline_runs:
        return ComparisonSelection(
            method=None,
            reason=ComparabilityReason.INSUFFICIENT_BASELINE_RUNS,
            alpha_effective=effective_alpha,
            small_cohort_warning=False,
        )
    return ComparisonSelection(
        method=ComparisonMethod.COHORT_BOOTSTRAP,
        reason=None,
        alpha_effective=effective_alpha,
        small_cohort_warning=_small_cohort_warning(current, baseline),
    )


def _small_cohort_warning(
    current: Sequence[ComparisonInput], baseline: Sequence[ComparisonInput]
) -> bool:
    """Warn when either cohort is below the recommended size (faithful mirror).

    Teaching material, not evidence, not a production API.
    """
    return (
        len(current) < _RECOMMENDED_MINIMUM_CURRENT_RUNS
        or len(baseline) < _RECOMMENDED_MINIMUM_BASELINE_RUNS
    )


def bootstrap_cohort(
    metric_input: MetricComparisonInput,
    options: BootstrapOptions,
) -> CohortBootstrapResult:
    """Calculate reproducible percentile-bootstrap evidence for one metric.

    This is a faithful educational mirror of ``bootstrap_sampling.bootstrap_metric``:
    it draws ``max(1000, 2000 * enabled)`` interleaved PCG64 current-then-baseline
    means, selects the linear lower bound at ``effective_alpha``, and reports the
    observed effect and 0.025/0.975 diagnostic bounds.
    """
    if options.enabled_metric_count < 1:
        message = "enabled_metric_count must be positive"
        raise ValueError(message)
    if options.seed < 0:
        message = "bootstrap seed must be nonnegative"
        raise ValueError(message)
    if not 0.0 < metric_input.effective_alpha < 1.0:
        message = "effective_alpha must be in (0, 1)"
        raise ValueError(message)
    effective_resamples = max(
        options.requested_resamples,
        _MINIMUM_RESAMPLES_PER_ENABLED_METRIC * options.enabled_metric_count,
    )
    current = oriented(
        tuple(value.value for value in metric_input.current),
        higher_is_worse=metric_input.direction == Direction.HIGHER_IS_WORSE,
    )
    baseline = oriented(
        tuple(value.value for value in metric_input.baseline),
        higher_is_worse=metric_input.direction == Direction.HIGHER_IS_WORSE,
    )
    generator = np.random.Generator(np.random.PCG64(options.seed))
    draws = tuple(
        float(np.mean(current[generator.integers(0, len(current), size=len(current))]))
        - float(
            np.mean(baseline[generator.integers(0, len(baseline), size=len(baseline))])
        )
        for _ in range(effective_resamples)
    )
    draws_array = np.asarray(draws, dtype=np.float64)
    lower = float(
        np.quantile(draws_array, metric_input.effective_alpha, method="linear")
    )
    observed_effect = float(np.mean(current) - np.mean(baseline))
    return CohortBootstrapResult(
        metric_id=metric_input.metric_id,
        direction=metric_input.direction,
        method=ComparisonMethod.COHORT_BOOTSTRAP,
        requested_alpha=metric_input.requested_alpha,
        effective_alpha=metric_input.effective_alpha,
        observed_effect=observed_effect,
        lower_decision_bound=lower,
        diagnostic_lower_bound=float(
            np.quantile(draws_array, _DIAGNOSTIC_QUANTILES[0], method="linear")
        ),
        diagnostic_upper_bound=float(
            np.quantile(draws_array, _DIAGNOSTIC_QUANTILES[1], method="linear")
        ),
        effective_seed=options.seed,
        requested_resamples=options.requested_resamples,
        effective_resamples=effective_resamples,
        current_sample_count=len(metric_input.current),
        baseline_sample_count=len(metric_input.baseline),
        sample_size_warning=metric_input.sample_size_warning,
    )


def reference_cohort(metric_input: MetricComparisonInput) -> BaselineReferenceResult:
    """Calculate advisory baseline-reference evidence for one metric.

    This is a faithful educational mirror of
    ``bootstrap_reference.reference_metric``: it takes the oriented baseline tail
    at ``1 - effective_alpha``, subtracts it from the current mean, and flags an
    anomaly when the effect exceeds the practical threshold.
    """
    current = oriented(
        tuple(value.value for value in metric_input.current),
        higher_is_worse=metric_input.direction == Direction.HIGHER_IS_WORSE,
    )
    baseline = oriented(
        tuple(value.value for value in metric_input.baseline),
        higher_is_worse=metric_input.direction == Direction.HIGHER_IS_WORSE,
    )
    reference_quantile = float(
        np.quantile(baseline, 1.0 - metric_input.effective_alpha, method="linear")
    )
    reference_effect = float(np.mean(current) - reference_quantile)
    return BaselineReferenceResult(
        metric_id=metric_input.metric_id,
        direction=metric_input.direction,
        method=ComparisonMethod.BASELINE_REFERENCE,
        requested_alpha=metric_input.requested_alpha,
        effective_alpha=metric_input.effective_alpha,
        reference_quantile=reference_quantile,
        reference_effect=reference_effect,
        reference_anomaly=reference_effect > metric_input.practical_threshold,
        current_sample_count=len(metric_input.current),
        baseline_sample_count=len(metric_input.baseline),
        sample_size_warning=metric_input.sample_size_warning,
    )


def evaluate_flow(
    policy: PolicyLike,
    metric: MetricLike,
    current_records: Mapping[str, RunRecord | None],
    baseline_records: Mapping[str, RunRecord | None],
    *,
    seed: int = _DEFAULT_SEED,
) -> MetricOutcome:
    """Evaluate one metric through the full comparison flow (educational mirror).

    This is a faithful educational mirror of ``regression_metrics.evaluate_metric``:
    a disabled metric is inconclusive, incomparable cohorts are inconclusive with
    one reason, the reference tail is advisory, and the cohort bootstrap decides
    PASS/FAIL from the strict lower-bound rule.
    """
    if not metric.enabled:
        return MetricOutcome(
            metric_id=metric.metric_id,
            direction=metric.direction,
            enabled=False,
            status=Status.INCONCLUSIVE,
            method=None,
            evidence=None,
            reason=MetricReason.METRIC_DISABLED,
            exclusions=(),
        )
    current = eligible_cohort(current_records, cohort=Cohort.CURRENT)
    baseline = eligible_cohort(baseline_records, cohort=Cohort.BASELINE)
    selection = select_comparison(
        policy, current.comparison_inputs, baseline.comparison_inputs
    )
    exclusions = current.exclusions + baseline.exclusions
    if selection.method is None:
        return MetricOutcome(
            metric_id=metric.metric_id,
            direction=metric.direction,
            enabled=True,
            status=Status.INCONCLUSIVE,
            method=None,
            evidence=None,
            reason=selection.reason.value if selection.reason is not None else None,
            exclusions=exclusions,
        )
    metric_input = MetricComparisonInput(
        metric_id=metric.metric_id,
        direction=metric.direction,
        requested_alpha=policy.nominal_alpha,
        effective_alpha=selection.alpha_effective,
        practical_threshold=metric.practical_threshold,
        current=current.run_values,
        baseline=baseline.run_values,
        sample_size_warning=selection.small_cohort_warning,
    )
    options = BootstrapOptions(
        seed=seed,
        requested_resamples=_DEFAULT_REQUESTED_RESAMPLES,
        enabled_metric_count=_enabled_gate_count(policy),
    )
    match selection.method:
        case ComparisonMethod.BASELINE_REFERENCE:
            evidence = reference_cohort(metric_input)
            return MetricOutcome(
                metric_id=metric.metric_id,
                direction=metric.direction,
                enabled=True,
                status=Status.INCONCLUSIVE,
                method=evidence.method,
                evidence=evidence,
                reason=None,
                exclusions=exclusions,
            )
        case ComparisonMethod.COHORT_BOOTSTRAP:
            evidence = bootstrap_cohort(metric_input, options)
            status = (
                Status.FAIL
                if evidence.lower_decision_bound > metric.practical_threshold
                else Status.PASS
            )
            return MetricOutcome(
                metric_id=metric.metric_id,
                direction=metric.direction,
                enabled=True,
                status=status,
                method=evidence.method,
                evidence=evidence,
                reason=None,
                exclusions=exclusions,
            )
        case _:
            assert_never(selection.method)


def aggregate_status(outcomes: tuple[MetricOutcome, ...]) -> Status:
    """Reduce enabled outcomes to the contractual suite status (educational).

    This is a faithful educational mirror of
    ``regression_aggregation.aggregate_status``: FAIL wins outright, otherwise an
    inconclusive enabled outcome wins over pass.
    """
    status = Status.PASS
    for outcome in outcomes:
        if outcome.enabled:
            match outcome.status:
                case Status.FAIL:
                    return Status.FAIL
                case Status.INCONCLUSIVE:
                    status = Status.INCONCLUSIVE
                case Status.PASS:
                    pass
                case _:
                    assert_never(outcome.status)
    return status


def _emit(line: str) -> None:
    """Write one trace line for the comparison lesson via sys.stdout.

    Faithful educational mirror helper; teaching material, not evidence, not a
    production API.
    """
    _ = sys.stdout.write(f"{line}\n")


def _print_outcome(label: str, outcome: MetricOutcome) -> None:
    """Emit one metric outcome's inputs and verdict for the trace lesson.

    Faithful educational mirror helper; teaching material, not evidence, not a
    production API.
    """
    _emit(f"[{label}] status={outcome.status.value} enabled={outcome.enabled}")
    _emit(f"    metric_id={outcome.metric_id} direction={outcome.direction.value}")
    _emit(f"    method={outcome.method} reason={outcome.reason}")
    if outcome.evidence is not None:
        _emit(f"    evidence={outcome.evidence}")
    if outcome.exclusions:
        _emit(f"    exclusions={outcome.exclusions}")


def demonstrate() -> None:
    """Run every comparison branch and print each branch's inputs and outputs.

    This teaching driver exercises disabled, missing, ineligible, inconclusive,
    reference, and PASS/FAIL branches so a reader can follow the mirror flow end
    to end. It is educational output only, never production evidence.
    """
    policy = PolicyLike(
        metrics=(
            MetricLike("latency", "q", "ms", Direction.LOWER_IS_WORSE, "mean", 5.0),
        )
    )
    metric = policy.metrics[0]
    fingerprint = comparison_fingerprint(policy, metric)

    _emit("== disabled ==")
    disabled = evaluate_flow(
        policy,
        replace(metric, enabled=False),
        {},
        {},
    )
    _print_outcome("disabled", disabled)

    _emit("== missing ==")
    missing_baseline = {
        "b1": run_record("b1", 10.0, day=11, metric_fingerprint=fingerprint),
        "b-missing": None,
    }
    missing_cohort = eligible_cohort(missing_baseline, cohort=Cohort.BASELINE)
    _emit(f"    baseline run_values: {missing_cohort.run_values}")
    _emit(f"    baseline exclusions: {missing_cohort.exclusions}")

    _emit("== ineligible ==")
    ineligible_baseline = {
        "b1": run_record("b1", 10.0, day=11, metric_fingerprint=fingerprint),
        "b-ineligible": run_record(
            "b-ineligible", None, day=105, metric_fingerprint=fingerprint
        ),
    }
    ineligible_cohort = eligible_cohort(ineligible_baseline, cohort=Cohort.BASELINE)
    _emit(f"    baseline run_values: {ineligible_cohort.run_values}")
    _emit(f"    baseline exclusions: {ineligible_cohort.exclusions}")

    _emit("== inconclusively comparable ==")
    inconclusive = evaluate_flow(
        policy,
        metric,
        {
            "c1": run_record("c1", 5.0, day=1, metric_fingerprint=fingerprint),
            "c2": run_record("c2", 5.0, day=2, metric_fingerprint=fingerprint),
            "c3": run_record("c3", 5.0, day=3, metric_fingerprint=fingerprint),
        },
        _cohort_baseline(fingerprint),
    )
    _print_outcome("inconclusive", inconclusive)

    _emit("== reference ==")
    reference = evaluate_flow(
        policy,
        replace(metric, direction=Direction.HIGHER_IS_WORSE),
        {"c1": run_record("c1", 16.0, day=1, metric_fingerprint=fingerprint)},
        _cohort_baseline(fingerprint),
    )
    _print_outcome("reference", reference)

    _emit("== cohort PASS (higher-is-worse) ==")
    pass_hiw = evaluate_flow(
        policy,
        replace(metric, direction=Direction.HIGHER_IS_WORSE),
        _repeat(15.0, 5, day_start=1, fingerprint=fingerprint),
        _cohort_baseline(fingerprint),
    )
    _print_outcome("PASS-HIW", pass_hiw)

    _emit("== cohort PASS (lower-is-worse) ==")
    pass_low = evaluate_flow(
        policy,
        metric,
        _repeat(5.0, 5, day_start=1, fingerprint=fingerprint),
        _cohort_baseline(fingerprint),
    )
    _print_outcome("PASS-LOW", pass_low)

    _emit("== cohort FAIL (higher-is-worse) ==")
    fail_hiw = evaluate_flow(
        policy,
        replace(metric, direction=Direction.HIGHER_IS_WORSE),
        _repeat(16.0, 5, day_start=1, fingerprint=fingerprint),
        _cohort_baseline(fingerprint),
    )
    _print_outcome("FAIL-HIW", fail_hiw)

    _emit("== cohort FAIL (lower-is-worse) ==")
    fail_low = evaluate_flow(
        policy,
        metric,
        _repeat(4.0, 5, day_start=1, fingerprint=fingerprint),
        _cohort_baseline(fingerprint),
    )
    _print_outcome("FAIL-LOW", fail_low)

    suite = aggregate_status((pass_hiw, fail_hiw))
    _emit(f"== aggregate PASS+FAIL -> {suite.value} ==")


def _repeat(
    value: float, count: int, *, day_start: int, fingerprint: str
) -> dict[str, RunRecord]:
    """Build a constant cohort of ``count`` runs on distinct days (teaching)."""
    return {
        f"run-{index}": run_record(
            f"run-{index}", value, day=day_start + index, metric_fingerprint=fingerprint
        )
        for index in range(count)
    }


def _cohort_baseline(fingerprint: str) -> dict[str, RunRecord]:
    """Build the pinned constant baseline cohort (ten runs at 10.0, mirror).

    Faithful educational mirror helper; teaching material, not evidence, not a
    production API.
    """
    return {
        f"baseline-{index}": run_record(
            f"baseline-{index}", 10.0, day=100 + index, metric_fingerprint=fingerprint
        )
        for index in range(10)
    }


if __name__ == "__main__":
    demonstrate()
