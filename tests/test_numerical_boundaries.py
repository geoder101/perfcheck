from dataclasses import replace
from datetime import timedelta
from math import inf, nan
from sys import float_info

import pytest
from pydantic import ValidationError

from perfcheck.bootstrap import (
    BootstrapInputError,
    BootstrapValidationCode,
    CohortBootstrapOptions,
    MetricComparisonInput,
    RunValue,
    bootstrap_cohorts,
)
from perfcheck.collection_models import FloatSample, SourceInterval
from perfcheck.model_types import Direction, EligibilityReason, Statistic
from perfcheck.policy_models import EligibilityPolicy
from perfcheck.summarize import MetricSummaryInput, summarize
from tests.cli_support import cli_policy, cli_run


def _input(
    seconds: tuple[int, ...], statistic: Statistic, eligibility: EligibilityPolicy
) -> MetricSummaryInput:
    policy = cli_policy()
    raw = cli_run(policy, 1, 1.0)
    start = raw.source_interval.start
    metric = policy.metrics[0].model_copy(
        update={"statistic": statistic, "eligibility": eligibility}
    )
    return MetricSummaryInput(
        source_interval=SourceInterval(start=start, end=start + timedelta(seconds=360)),
        policy=metric,
        compatibility_fingerprint="0" * 64,
        samples=tuple(
            FloatSample(
                timestamp=start + timedelta(seconds=second), value=100.0 - 2 * second
            )
            for second in seconds
        ),
    )


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_sample_boundary_rejects_nonfinite_values(value: float) -> None:
    # Given: a valid sample whose only mutation is its numeric value.
    sample = cli_run(cli_policy(), 1, 1.0).metric_records[0].series
    assert sample is not None
    payload = sample.samples[0].model_dump()
    payload["value"] = value

    # When: a nonfinite value enters the normal model boundary.
    with pytest.raises(ValidationError) as caught:
        _ = FloatSample.model_validate(payload)

    # Then: the value fails specifically because it is not finite.
    assert [(error["loc"], error["type"]) for error in caught.value.errors()] == [
        (("value",), "finite_number")
    ]


@pytest.mark.parametrize(
    "value", [float_info.max, -float_info.max, float_info.min, 5e-324, -0.0]
)
def test_sample_boundary_preserves_finite_extremes(value: float) -> None:
    # Given: a valid timestamp and a representable finite boundary value.
    timestamp = cli_run(cli_policy(), 1, 1.0).source_interval.start

    # When: the sample crosses JSON ingress and egress.
    sample = FloatSample(timestamp=timestamp, value=value)
    restored = FloatSample.model_validate_json(sample.model_dump_json())

    # Then: no magnitude clipping or underflow is introduced by the schema.
    assert restored.value.hex() == value.hex()


def test_summary_accepts_exact_coverage_and_allowed_gap_equality() -> None:
    # Given: exactly 20 of 25 expected points, with gaps exactly two steps long.
    seconds = tuple(
        second for second in range(0, 361, 15) if second not in (60, 120, 180, 240, 300)
    )
    summary_input = _input(seconds, Statistic.MEAN, EligibilityPolicy(max_gap_steps=1))

    # When: eligibility evaluates equality at both thresholds.
    result = summarize(summary_input)

    # Then: strict rejection comparisons preserve equality as eligible.
    assert result.eligibility.eligible is True
    assert result.eligibility.reason is None
    assert result.eligibility.coverage == 0.8
    assert result.eligibility.max_adjacent_gap_seconds == 30.0
    assert result.eligibility.max_allowed_gap_seconds == 30.0
    assert result.value == -260.0


@pytest.mark.parametrize("warmup", [360, 361, 720])
def test_trimmed_window_collapses_without_negative_duration(warmup: int) -> None:
    # Given: valid raw points with the complete window trimmed away or to one instant.
    summary_input = _input(
        tuple(range(0, 361, 15)),
        Statistic.MEAN,
        EligibilityPolicy(warmup_seconds=warmup),
    )

    # When: the window is summarized.
    result = summarize(summary_input)

    # Then: it records the short-window reason and nonnegative diagnostics.
    assert result.value is None
    assert result.eligibility.reason is EligibilityReason.ANALYSIS_WINDOW_TOO_SHORT
    assert result.eligibility.analysis_start == result.eligibility.analysis_end
    assert result.eligibility.analysis_duration_seconds == 0.0
    assert result.eligibility.expected_points == 1
    assert result.point_count == (1 if warmup == 360 else 0)


def test_negative_slope_uses_elapsed_seconds_for_irregular_samples() -> None:
    # Given: a descending line sampled irregularly, not by observation index.
    seconds = tuple(
        second + (1 if index % 2 else 0)
        for index, second in enumerate(range(0, 361, 15))
    )
    summary_input = _input(seconds, Statistic.SLOPE, EligibilityPolicy())

    # When: ordinary summary calculation fits the retained line.
    result = summarize(summary_input)

    # Then: the signed slope is per second, even at irregular spacings.
    assert result.eligibility.eligible is True
    assert result.value == -2.0


@pytest.mark.parametrize(
    ("options", "reason"),
    [
        (CohortBootstrapOptions(seed=-1), BootstrapValidationCode.INVALID_SEED),
        (
            CohortBootstrapOptions(requested_resamples=0),
            BootstrapValidationCode.INVALID_RESAMPLES,
        ),
        (
            CohortBootstrapOptions(enabled_metric_count=0),
            BootstrapValidationCode.INVALID_ENABLED_METRIC_COUNT,
        ),
    ],
)
def test_bootstrap_options_reject_exact_invalid_boundary(
    options: CohortBootstrapOptions, reason: BootstrapValidationCode
) -> None:
    # Given: valid finite inputs and an option with exactly one invalid field.
    metric = MetricComparisonInput(
        metric_id="latency",
        direction=Direction.HIGHER_IS_WORSE,
        requested_alpha=0.05,
        effective_alpha=0.05,
        practical_threshold=0.0,
        current=(RunValue("current", 2.0),),
        baseline=(RunValue("baseline", 1.0),),
    )

    # When: the public bootstrap entry point validates its options.
    with pytest.raises(BootstrapInputError) as caught:
        _ = bootstrap_cohorts((metric,), options)

    # Then: the exact typed option failure is retained and printable.
    assert caught.value.code is reason
    assert str(caught.value) == reason.value


@pytest.mark.parametrize("current", [True, False])
def test_bootstrap_rejects_empty_cohort(current: bool) -> None:
    # Given: finite comparable values with just one cohort removed.
    metric = MetricComparisonInput(
        metric_id="latency",
        direction=Direction.HIGHER_IS_WORSE,
        requested_alpha=0.05,
        effective_alpha=0.05,
        practical_threshold=0.0,
        current=(RunValue("current", 2.0),),
        baseline=(RunValue("baseline", 1.0),),
    )
    metric = replace(metric, current=()) if current else replace(metric, baseline=())

    # When: the bootstrap boundary receives an empty cohort.
    with pytest.raises(BootstrapInputError) as caught:
        _ = bootstrap_cohorts((metric,))

    # Then: it names which required cohort is empty.
    assert caught.value.code is (
        BootstrapValidationCode.EMPTY_CURRENT
        if current
        else BootstrapValidationCode.EMPTY_BASELINE
    )
