import math
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

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
from perfcheck.summary_statistics import calculate_statistic

if TYPE_CHECKING:
    from perfcheck.summary_models import MetricSummary

_BASE = datetime(2026, 1, 1, tzinfo=UTC)
_FINGERPRINT = "b" * 64


def _samples(values: tuple[float, ...]) -> tuple[FloatSample, ...]:
    return tuple(
        FloatSample(timestamp=_BASE + timedelta(seconds=index * 15), value=value)
        for index, value in enumerate(values)
    )


def _summarize(
    statistic: Statistic, sample_vector: tuple[FloatSample, ...]
) -> MetricSummary:
    policy = MetricPolicy(
        metric_id=MetricId("cpu-system"),
        query="up",
        unit=MetricUnit.PERCENT,
        direction=Direction.HIGHER_IS_WORSE,
        statistic=statistic,
        practical_threshold=0.0,
        step_seconds=15,
        rate_window_seconds=60,
        eligibility=EligibilityPolicy(),
    )
    return summarize(
        MetricSummaryInput(
            source_interval=SourceInterval(
                start=_BASE, end=_BASE + timedelta(seconds=300)
            ),
            policy=policy,
            compatibility_fingerprint=_FINGERPRINT,
            samples=sample_vector,
        )
    )


def test_calculate_statistic_uses_fsum_sample_standard_deviation() -> None:
    # Given: values whose Bessel sample deviation exposes reduction rounding.
    values = (1e16, 1.0, -1e16, 3.0, 5.0, -7.0, 11.0)
    sample_vector = _samples(values)
    mean = math.fsum(values) / len(values)
    expected = math.sqrt(math.fsum((value - mean) ** 2 for value in values) / 6)

    # When: the selected statistic is the sample standard deviation.
    actual = calculate_statistic(Statistic.STD, sample_vector)

    # Then: the deterministic fsum/Bessel formula is retained exactly.
    assert actual == expected


def test_summarize_orders_bypassed_raw_samples_by_timestamp() -> None:
    # Given: a reverse-ordered vector bypassed collection order checks.
    ordered_samples = _samples(tuple(float(index) for index in range(1, 22)))

    # When: the summary boundary receives the bypassed vector.
    summary = _summarize(Statistic.FIRST, tuple(reversed(ordered_samples)))

    # Then: first is based on the earliest timestamp without invalid diagnostics.
    assert summary.value == 1.0
    assert summary.eligibility.eligible is True


def test_summarize_withholds_a_scalar_when_finite_values_overflow_fsum() -> None:
    # Given: enough individually finite samples whose sum exceeds binary64 range.
    samples = _samples((1e308,) * 21)

    # When: the summary calculator performs its exact mean reduction.
    summary = _summarize(Statistic.MEAN, samples)

    # Then: no invalid scalar is persisted and the metric is ineligible.
    assert summary.value is None
    assert summary.eligibility.reason is EligibilityReason.NONFINITE_VALUE
