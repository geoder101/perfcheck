from sys import float_info

import pytest

from perfcheck.bootstrap import (
    BootstrapInputError,
    CohortBootstrapOptions,
    MetricComparisonInput,
    RunValue,
    baseline_references,
    bootstrap_cohorts,
)
from perfcheck.model_types import Direction


@pytest.mark.parametrize("count", [1, 2])
def test_bootstrap_extreme_finite_arithmetic_has_typed_failure(count: int) -> None:
    # Given: accepted finite samples whose float64 mean or contrast overflows.
    metric = MetricComparisonInput(
        metric_id="latency",
        direction=Direction.HIGHER_IS_WORSE,
        requested_alpha=0.05,
        effective_alpha=0.05,
        practical_threshold=0.0,
        current=tuple(RunValue(f"current-{i}", float_info.max) for i in range(count)),
        baseline=tuple(
            RunValue(f"baseline-{i}", -float_info.max) for i in range(count)
        ),
    )

    # When: resampling encounters arithmetic outside finite float64 range.
    with pytest.raises(
        BootstrapInputError, match="bootstrap arithmetic must remain finite"
    ) as caught:
        _ = bootstrap_cohorts((metric,), CohortBootstrapOptions(requested_resamples=1))

    # Then: it returns a typed failure, never warnings or NaN evidence.
    assert caught.value.exit_code == 3


def test_bootstrap_large_representable_values_retain_exact_effect() -> None:
    # Given: large constant cohorts well within finite float64 arithmetic range.
    metric = MetricComparisonInput(
        metric_id="latency",
        direction=Direction.HIGHER_IS_WORSE,
        requested_alpha=0.05,
        effective_alpha=0.05,
        practical_threshold=0.0,
        current=(RunValue("current-1", 2e150), RunValue("current-2", 2e150)),
        baseline=(RunValue("baseline-1", 1e150), RunValue("baseline-2", 1e150)),
    )

    # When: ordinary cohort bootstrap computes the signed difference.
    (result,) = bootstrap_cohorts(
        (metric,), CohortBootstrapOptions(requested_resamples=1)
    )

    # Then: the effect and all quantiles are finite and exactly the constant contrast.
    assert (
        result.observed_effect,
        result.lower_decision_bound,
        result.diagnostic_lower_bound,
        result.diagnostic_upper_bound,
    ) == (1e150,) * 4


@pytest.mark.parametrize("quantile_overflow", [False, True])
def test_reference_extreme_finite_arithmetic_has_typed_failure(
    quantile_overflow: bool,
) -> None:
    # Given: finite values causing either quantile interpolation or effect overflow.
    baseline = (
        (-float_info.max, float_info.max) if quantile_overflow else (-float_info.max,)
    )
    metric = MetricComparisonInput(
        metric_id="latency",
        direction=Direction.HIGHER_IS_WORSE,
        requested_alpha=0.05,
        effective_alpha=0.05,
        practical_threshold=0.0,
        current=(RunValue("current", float_info.max),),
        baseline=tuple(
            RunValue(f"baseline-{i}", value) for i, value in enumerate(baseline)
        ),
    )

    # When: reference calculations exceed finite float64 arithmetic range.
    with pytest.raises(
        BootstrapInputError, match="bootstrap arithmetic must remain finite"
    ) as caught:
        _ = baseline_references((metric,))

    # Then: reference and cohort arithmetic use the same safe typed failure contract.
    assert caught.value.exit_code == 3
