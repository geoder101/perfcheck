"""Per-run metric summary calculation with explicit eligibility evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final

from perfcheck.model_types import CompatibilitySha256, EligibilityReason, Statistic
from perfcheck.summary_models import EligibilityResult, MetricSummary
from perfcheck.summary_statistics import calculate_statistic

if TYPE_CHECKING:
    from perfcheck.collection_models import FloatSample, SourceInterval
    from perfcheck.policy_models import MetricPolicy

_STATISTIC_MINIMUM_POINTS: Final = frozenset((Statistic.STD, Statistic.SLOPE))
_MINIMUM_STATISTIC_OBSERVATIONS: Final = 2


@dataclass(frozen=True, slots=True)
class MetricSummaryInput:
    """Validated samples and policy required to summarize one metric run."""

    source_interval: SourceInterval
    policy: MetricPolicy
    compatibility_fingerprint: CompatibilitySha256
    samples: tuple[FloatSample, ...]


@dataclass(frozen=True, slots=True)
class _EligibilityDiagnostics:
    analysis_start: datetime
    analysis_end: datetime
    duration_seconds: float
    retained_samples: tuple[FloatSample, ...]
    expected_points: int
    coverage: float
    leading_gap_seconds: float
    max_adjacent_gap_seconds: float
    trailing_gap_seconds: float
    max_allowed_gap_seconds: float


def summarize(summary_input: MetricSummaryInput) -> MetricSummary:
    """Calculate one selected statistic or persist its exact ineligibility reason."""
    input_reason = _input_reason(summary_input.samples)
    ordered_samples = tuple(
        sorted(summary_input.samples, key=lambda sample: sample.timestamp)
    )
    diagnostics = _diagnostics(summary_input, ordered_samples)
    reason = _ineligibility_reason(input_reason, summary_input.policy, diagnostics)
    value: float | None = None
    if reason is None:
        try:
            calculated_value = calculate_statistic(
                summary_input.policy.statistic,
                diagnostics.retained_samples,
            )
        except OverflowError:
            reason = EligibilityReason.NONFINITE_VALUE
        else:
            if math.isfinite(calculated_value):
                value = calculated_value
            else:
                reason = EligibilityReason.NONFINITE_VALUE
    eligibility = _eligibility_result(diagnostics, reason)
    return MetricSummary(
        statistic=summary_input.policy.statistic,
        value=value,
        point_count=len(diagnostics.retained_samples),
        compatibility_fingerprint=summary_input.compatibility_fingerprint,
        eligibility=eligibility,
    )


def _diagnostics(
    summary_input: MetricSummaryInput, samples: tuple[FloatSample, ...]
) -> _EligibilityDiagnostics:
    eligibility = summary_input.policy.eligibility
    analysis_start = summary_input.source_interval.start + timedelta(
        seconds=eligibility.warmup_seconds
    )
    requested_analysis_end = summary_input.source_interval.end - timedelta(
        seconds=eligibility.cooldown_seconds
    )
    analysis_end = max(analysis_start, requested_analysis_end)
    duration_seconds = (analysis_end - analysis_start).total_seconds()
    retained_samples = tuple(
        sample
        for sample in samples
        if analysis_start <= sample.timestamp <= analysis_end
    )
    expected_points = (
        math.floor(duration_seconds / summary_input.policy.step_seconds) + 1
    )
    coverage = len(retained_samples) / expected_points
    leading_gap_seconds, max_adjacent_gap_seconds, trailing_gap_seconds = _gaps(
        analysis_start,
        analysis_end,
        retained_samples,
    )
    max_allowed_gap_seconds = (
        summary_input.policy.eligibility.max_gap_steps + 1
    ) * summary_input.policy.step_seconds
    return _EligibilityDiagnostics(
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        duration_seconds=duration_seconds,
        retained_samples=retained_samples,
        expected_points=expected_points,
        coverage=coverage,
        leading_gap_seconds=leading_gap_seconds,
        max_adjacent_gap_seconds=max_adjacent_gap_seconds,
        trailing_gap_seconds=trailing_gap_seconds,
        max_allowed_gap_seconds=max_allowed_gap_seconds,
    )


def _gaps(
    analysis_start: datetime,
    analysis_end: datetime,
    samples: tuple[FloatSample, ...],
) -> tuple[float, float, float]:
    if not samples:
        duration_seconds = (analysis_end - analysis_start).total_seconds()
        return duration_seconds, 0.0, duration_seconds
    adjacent_gaps = tuple(
        (samples[index].timestamp - samples[index - 1].timestamp).total_seconds()
        for index in range(1, len(samples))
    )
    return (
        (samples[0].timestamp - analysis_start).total_seconds(),
        max(adjacent_gaps, default=0.0),
        (analysis_end - samples[-1].timestamp).total_seconds(),
    )


def _ineligibility_reason(
    input_reason: EligibilityReason | None,
    policy: MetricPolicy,
    diagnostics: _EligibilityDiagnostics,
) -> EligibilityReason | None:
    # First matching rule wins, in this precedence: an input-series defect (empty,
    # non-finite, or duplicated timestamps) is reported before any policy-gated
    # rule, then window -> statistic-minimum -> min-points -> coverage -> gap.
    reason = input_reason
    if (
        reason is None
        and diagnostics.duration_seconds
        < policy.eligibility.min_analysis_window_seconds
    ):
        reason = EligibilityReason.ANALYSIS_WINDOW_TOO_SHORT
    elif reason is None and (
        policy.statistic in _STATISTIC_MINIMUM_POINTS
        and len(diagnostics.retained_samples) < _MINIMUM_STATISTIC_OBSERVATIONS
    ):
        reason = EligibilityReason.STATISTIC_REQUIRES_MORE_POINTS
    elif (
        reason is None
        and len(diagnostics.retained_samples) < policy.eligibility.min_points
    ):
        reason = EligibilityReason.INSUFFICIENT_POINTS
    elif reason is None and diagnostics.coverage < policy.eligibility.min_coverage:
        reason = EligibilityReason.COVERAGE_TOO_LOW
    elif reason is None and (
        max(
            diagnostics.leading_gap_seconds,
            diagnostics.max_adjacent_gap_seconds,
            diagnostics.trailing_gap_seconds,
        )
        > diagnostics.max_allowed_gap_seconds
    ):
        reason = EligibilityReason.GAP_TOO_LARGE
    return reason


def _input_reason(samples: tuple[FloatSample, ...]) -> EligibilityReason | None:
    if not samples:
        return EligibilityReason.EMPTY_SERIES
    if not all(math.isfinite(sample.value) for sample in samples):
        return EligibilityReason.NONFINITE_VALUE
    timestamps = tuple(sample.timestamp for sample in samples)
    if len(timestamps) != len(set(timestamps)):
        return EligibilityReason.DUPLICATE_TIMESTAMP
    return None


def _eligibility_result(
    diagnostics: _EligibilityDiagnostics, reason: EligibilityReason | None
) -> EligibilityResult:
    return EligibilityResult(
        eligible=reason is None,
        reason=reason,
        analysis_start=diagnostics.analysis_start,
        analysis_end=diagnostics.analysis_end,
        retained_points=len(diagnostics.retained_samples),
        expected_points=diagnostics.expected_points,
        coverage=diagnostics.coverage,
        analysis_duration_seconds=diagnostics.duration_seconds,
        leading_gap_seconds=diagnostics.leading_gap_seconds,
        max_adjacent_gap_seconds=diagnostics.max_adjacent_gap_seconds,
        trailing_gap_seconds=diagnostics.trailing_gap_seconds,
        max_allowed_gap_seconds=diagnostics.max_allowed_gap_seconds,
    )
