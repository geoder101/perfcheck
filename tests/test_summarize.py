from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from perfcheck.collection_models import FloatSample, SourceInterval
from perfcheck.model_types import (
    Direction,
    EligibilityReason,
    MetricId,
    MetricUnit,
    Statistic,
)
from perfcheck.policy_models import EligibilityPolicy, MetricPolicy
from perfcheck.summarize import MetricSummaryInput, summarize

if TYPE_CHECKING:
    from perfcheck.summary_models import MetricSummary

_BASE = datetime(2026, 1, 1, tzinfo=UTC)
_FINGERPRINT = "a" * 64


@dataclass(frozen=True, slots=True)
class SummaryFixture:
    statistic: Statistic
    samples: tuple[FloatSample, ...]
    source_seconds: int
    eligibility: EligibilityPolicy


def _samples(
    sample_seconds: tuple[int, ...], values: tuple[float, ...]
) -> tuple[FloatSample, ...]:
    return tuple(
        FloatSample(timestamp=_BASE + timedelta(seconds=second), value=value)
        for second, value in zip(sample_seconds, values, strict=True)
    )


def _summarize(fixture: SummaryFixture) -> MetricSummary:
    source_interval = SourceInterval(
        start=_BASE,
        end=_BASE + timedelta(seconds=fixture.source_seconds),
    )
    policy = MetricPolicy(
        metric_id=MetricId("cpu-system"),
        query="up",
        unit=MetricUnit.PERCENT,
        direction=Direction.HIGHER_IS_WORSE,
        statistic=fixture.statistic,
        practical_threshold=0.0,
        step_seconds=15,
        rate_window_seconds=60,
        eligibility=fixture.eligibility,
    )
    return summarize(
        MetricSummaryInput(
            source_interval=source_interval,
            policy=policy,
            compatibility_fingerprint=_FINGERPRINT,
            samples=fixture.samples,
        )
    )


@pytest.mark.parametrize(
    ("statistic", "expected"),
    [
        (Statistic.MEAN, 11.0),
        (Statistic.P50, 11.0),
        (Statistic.P90, 19.0),
        (Statistic.P95, 20.0),
        (Statistic.P99, 20.8),
        (Statistic.MIN, 1.0),
        (Statistic.MAX, 21.0),
        (Statistic.STD, 6.2048368229954285),
        (Statistic.FIRST, 1.0),
        (Statistic.LAST, 21.0),
        (Statistic.DELTA, 20.0),
        (Statistic.SLOPE, 1.0 / 15.0),
    ],
)
def test_summarize_calculates_each_selected_statistic(
    statistic: Statistic, expected: float
) -> None:
    # Given: a complete eligible 300-second series with hand-calculated values.
    seconds = tuple(range(0, 301, 15))
    fixture = SummaryFixture(
        statistic=statistic,
        samples=_samples(seconds, tuple(float(index) for index in range(1, 22))),
        source_seconds=300,
        eligibility=EligibilityPolicy(),
    )

    # When: the series is summarized under its selected policy statistic.
    summary = _summarize(fixture)

    # Then: the persisted scalar uses the specified statistic exactly.
    assert summary.value == pytest.approx(expected)
    assert summary.point_count == 21
    assert summary.eligibility.eligible is True


def test_summarize_trims_an_inclusive_warmup_and_cooldown_window() -> None:
    # Given: raw points extend beyond both inclusive analysis boundaries.
    seconds = tuple(range(0, 361, 15))
    fixture = SummaryFixture(
        statistic=Statistic.FIRST,
        samples=_samples(seconds, tuple(float(second // 15) for second in seconds)),
        source_seconds=360,
        eligibility=EligibilityPolicy(warmup_seconds=30, cooldown_seconds=30),
    )

    # When: warmup and cooldown are applied before summary eligibility.
    summary = _summarize(fixture)

    # Then: only the inclusive 30-to-330-second window contributes.
    assert summary.value == 2.0
    assert summary.point_count == 21
    assert summary.eligibility.analysis_start == _BASE + timedelta(seconds=30)
    assert summary.eligibility.analysis_end == _BASE + timedelta(seconds=330)
    assert summary.eligibility.expected_points == 21
    assert summary.eligibility.coverage == 1.0
    assert summary.eligibility.leading_gap_seconds == 0.0
    assert summary.eligibility.max_adjacent_gap_seconds == 15.0
    assert summary.eligibility.trailing_gap_seconds == 0.0
    assert summary.eligibility.max_allowed_gap_seconds == 60.0


@pytest.mark.parametrize(
    "samples",
    [
        _samples(tuple(range(75, 601, 15)), tuple(float(value) for value in range(36))),
        _samples(
            (0, *range(75, 601, 15)),
            tuple(float(value) for value in range(37)),
        ),
        _samples(tuple(range(0, 526, 15)), tuple(float(value) for value in range(36))),
    ],
)
def test_summarize_rejects_excessive_leading_adjacent_or_trailing_gaps(
    samples: tuple[FloatSample, ...],
) -> None:
    # Given: enough points and coverage, but one 75-second gap in the window.
    fixture = SummaryFixture(
        statistic=Statistic.MEAN,
        samples=samples,
        source_seconds=600,
        eligibility=EligibilityPolicy(),
    )

    # When: eligibility evaluates each boundary and interior gap.
    summary = _summarize(fixture)

    # Then: any gap greater than four policy steps is ineligible.
    assert summary.value is None
    assert summary.eligibility.reason is EligibilityReason.GAP_TOO_LARGE


@pytest.mark.parametrize(
    ("samples", "reason"),
    [
        ((), EligibilityReason.EMPTY_SERIES),
        (
            (FloatSample.model_construct(timestamp=_BASE, value=float("nan")),),
            EligibilityReason.NONFINITE_VALUE,
        ),
        (
            (
                FloatSample.model_construct(timestamp=_BASE, value=1.0),
                FloatSample.model_construct(timestamp=_BASE, value=2.0),
            ),
            EligibilityReason.DUPLICATE_TIMESTAMP,
        ),
    ],
)
def test_summarize_rejects_invalid_raw_vectors(
    samples: tuple[FloatSample, ...], reason: EligibilityReason
) -> None:
    # Given: a raw vector that bypassed the collection-model boundary.
    fixture = SummaryFixture(
        statistic=Statistic.MEAN,
        samples=samples,
        source_seconds=300,
        eligibility=EligibilityPolicy(),
    )

    # When: summary validation receives the raw vector.
    summary = _summarize(fixture)

    # Then: it persists no scalar and records its exact invalidity reason.
    assert summary.value is None
    assert summary.eligibility.reason is reason


@pytest.mark.parametrize("statistic", [Statistic.STD, Statistic.SLOPE])
def test_summarize_requires_two_usable_points_for_std_and_slope(
    statistic: Statistic,
) -> None:
    # Given: an otherwise valid window containing only one retained observation.
    fixture = SummaryFixture(
        statistic=statistic,
        samples=_samples((0,), (1.0,)),
        source_seconds=300,
        eligibility=EligibilityPolicy(),
    )

    # When: a two-point statistic is selected.
    summary = _summarize(fixture)

    # Then: the metric is inconclusive for the statistic-specific reason.
    assert summary.value is None
    assert (
        summary.eligibility.reason is EligibilityReason.STATISTIC_REQUIRES_MORE_POINTS
    )


@pytest.mark.parametrize(
    ("source_seconds", "samples", "reason"),
    [
        (
            299,
            _samples(
                tuple(range(0, 300, 15)), tuple(float(value) for value in range(20))
            ),
            EligibilityReason.ANALYSIS_WINDOW_TOO_SHORT,
        ),
        (
            300,
            _samples(
                tuple(range(0, 271, 15)), tuple(float(value) for value in range(19))
            ),
            EligibilityReason.INSUFFICIENT_POINTS,
        ),
        (
            600,
            _samples(
                tuple(range(0, 286, 15)), tuple(float(value) for value in range(20))
            ),
            EligibilityReason.COVERAGE_TOO_LOW,
        ),
    ],
)
def test_summarize_records_exact_duration_count_and_coverage_failures(
    source_seconds: int,
    samples: tuple[FloatSample, ...],
    reason: EligibilityReason,
) -> None:
    # Given: a vector that misses exactly one eligibility threshold.
    fixture = SummaryFixture(
        statistic=Statistic.MEAN,
        samples=samples,
        source_seconds=source_seconds,
        eligibility=EligibilityPolicy(),
    )

    # When: summary eligibility is evaluated.
    summary = _summarize(fixture)

    # Then: its scalar is withheld with the threshold's stable reason key.
    assert summary.value is None
    assert summary.eligibility.reason is reason
