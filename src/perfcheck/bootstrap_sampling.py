"""Seeded cohort-bootstrap sampling and percentile statistics."""

from __future__ import annotations

from math import isfinite
from typing import Final, assert_never

import numpy as np
import numpy.typing as npt

from perfcheck.bootstrap_models import (
    BootstrapInputError,
    BootstrapValidationCode,
    CohortBootstrapOptions,
    CohortBootstrapResult,
    MetricComparisonInput,
    RunValue,
)
from perfcheck.model_types import V1_ALGORITHM_MANIFEST, ComparisonMethod, Direction

_MINIMUM_RESAMPLES_PER_ENABLED_METRIC: Final = 2_000
_DIAGNOSTIC_QUANTILES: Final = (0.025, 0.975)


def bootstrap_metric(
    metric_input: MetricComparisonInput, options: CohortBootstrapOptions
) -> CohortBootstrapResult:
    """Calculate reproducible percentile-bootstrap evidence for one metric."""
    effective_resamples = max(
        options.requested_resamples,
        _MINIMUM_RESAMPLES_PER_ENABLED_METRIC * options.enabled_metric_count,
    )
    current_values = oriented_float64_values(
        metric_input.current, metric_input.direction
    )
    baseline_values = oriented_float64_values(
        metric_input.baseline, metric_input.direction
    )
    generator = np.random.Generator(np.random.PCG64(options.seed))
    differences = np.asarray(
        tuple(
            difference(
                _draw_mean(current_values, generator),
                _draw_mean(baseline_values, generator),
            )
            for _ in range(effective_resamples)
        ),
        dtype=np.float64,
    )
    diagnostic_lower_bound = quantile(differences, _DIAGNOSTIC_QUANTILES[0])
    diagnostic_upper_bound = quantile(differences, _DIAGNOSTIC_QUANTILES[1])
    return CohortBootstrapResult(
        metric_id=metric_input.metric_id,
        direction=metric_input.direction,
        method=ComparisonMethod.COHORT_BOOTSTRAP,
        algorithm_manifest=V1_ALGORITHM_MANIFEST,
        requested_alpha=metric_input.requested_alpha,
        effective_alpha=metric_input.effective_alpha,
        observed_effect=difference(_mean(current_values), _mean(baseline_values)),
        lower_decision_bound=quantile(differences, metric_input.effective_alpha),
        diagnostic_lower_bound=diagnostic_lower_bound,
        diagnostic_upper_bound=diagnostic_upper_bound,
        effective_seed=options.seed,
        requested_resamples=options.requested_resamples,
        effective_resamples=effective_resamples,
        current_sample_ids=tuple(value.source_run_id for value in metric_input.current),
        baseline_sample_ids=tuple(
            value.source_run_id for value in metric_input.baseline
        ),
        current_sample_count=len(metric_input.current),
        baseline_sample_count=len(metric_input.baseline),
        sample_size_warning=metric_input.sample_size_warning,
    )


def oriented_float64_values(
    run_values: tuple[RunValue, ...], direction: Direction
) -> npt.NDArray[np.float64]:
    """Orient values so positive effects always indicate a worsening metric."""
    match direction:
        case Direction.HIGHER_IS_WORSE:
            values = tuple(run_value.value for run_value in run_values)
        case Direction.LOWER_IS_WORSE:
            values = tuple(-run_value.value for run_value in run_values)
        case _:
            assert_never(direction)
    return np.asarray(values, dtype=np.float64)


def _draw_mean(
    values: npt.NDArray[np.float64], generator: np.random.Generator
) -> float:
    drawn_values = values[generator.integers(0, len(values), size=len(values))]
    return _mean(drawn_values)


def mean(values: npt.NDArray[np.float64]) -> float:
    """Return the float64 arithmetic mean as a Python float."""
    return _mean(values)


def _mean(values: npt.NDArray[np.float64]) -> float:
    try:
        with np.errstate(over="raise", invalid="raise"):
            return float(np.mean(values))
    except FloatingPointError as error:
        raise BootstrapInputError(
            BootstrapValidationCode.NONFINITE_ARITHMETIC
        ) from error


def difference(current: float, baseline: float) -> float:
    """Reject nonfinite contrasts before they enter comparison evidence."""
    value = current - baseline
    if not isfinite(value):
        raise BootstrapInputError(BootstrapValidationCode.NONFINITE_ARITHMETIC)
    return value


def quantile(values: npt.NDArray[np.float64], probability: float) -> float:
    """Calculate the fixed linear quantile with typed arithmetic failures."""
    try:
        with np.errstate(over="raise", invalid="raise"):
            return float(np.quantile(values, probability, method="linear"))
    except FloatingPointError as error:
        raise BootstrapInputError(
            BootstrapValidationCode.NONFINITE_ARITHMETIC
        ) from error
