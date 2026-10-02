"""Deterministic run-level bootstrap and advisory reference calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

import numpy as np
import numpy.typing as npt

from perfcheck.errors import PerfcheckError
from perfcheck.model_types import (
    V1_ALGORITHM_MANIFEST,
    AlgorithmManifest,
    ComparisonMethod,
    Direction,
)

_DEFAULT_SEED: Final = 42
_DEFAULT_REQUESTED_RESAMPLES: Final = 10_000
_MINIMUM_RESAMPLES_PER_ENABLED_METRIC: Final = 2_000
_DIAGNOSTIC_QUANTILES: Final = (0.025, 0.975)


class BootstrapValidationCode(StrEnum):
    """Stable validation failures emitted by bootstrap input boundaries."""

    EMPTY_BASELINE = "baseline cohort must contain one or more run values"
    EMPTY_CURRENT = "current cohort must contain one or more run values"
    INVALID_ALPHA = "requested and effective alpha values are invalid"
    INVALID_ENABLED_METRIC_COUNT = "enabled metric count must be positive"
    INVALID_PRACTICAL_THRESHOLD = "practical threshold must be finite and nonnegative"
    INVALID_RESAMPLES = "requested resamples must be positive"
    INVALID_SEED = "bootstrap seed must be nonnegative"
    NONFINITE_INPUT = "run-level values must be finite"
    REFERENCE_OVERRIDE = "seed and resamples are invalid for baseline reference"
    REFERENCE_REQUIRES_ONE_CURRENT = "baseline reference requires one current run"


@dataclass(frozen=True, slots=True)
class BootstrapInputError(PerfcheckError):
    """A caller supplied values outside the fixed numerical contract."""

    code: BootstrapValidationCode
    exit_code: ClassVar[int] = 3

    def __str__(self) -> str:
        """Render the stable validation message for caller diagnostics."""
        return self.code


@dataclass(frozen=True, slots=True)
class RunValue:
    """One validated per-run statistic and its canonical source identifier."""

    source_run_id: str
    value: float


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
class CohortBootstrapOptions:
    """Explicit cohort-bootstrap options including the fixed default seed."""

    seed: int = _DEFAULT_SEED
    requested_resamples: int = _DEFAULT_REQUESTED_RESAMPLES
    enabled_metric_count: int = 1


@dataclass(frozen=True, slots=True)
class ReferenceOptions:
    """Optional overrides rejected by the advisory baseline-reference method."""

    seed: int | None = None
    requested_resamples: int | None = None


DEFAULT_COHORT_OPTIONS: Final = CohortBootstrapOptions()
DEFAULT_REFERENCE_OPTIONS: Final = ReferenceOptions()


@dataclass(frozen=True, slots=True)
class ComparisonEvidence:
    """Shared immutable provenance retained by each comparison evidence variant."""

    metric_id: str
    direction: Direction
    method: ComparisonMethod
    algorithm_manifest: AlgorithmManifest
    requested_alpha: float
    effective_alpha: float
    current_sample_ids: tuple[str, ...]
    baseline_sample_ids: tuple[str, ...]
    current_sample_count: int
    baseline_sample_count: int
    sample_size_warning: bool


@dataclass(frozen=True, slots=True)
class CohortBootstrapResult(ComparisonEvidence):
    """Reproducible approximate percentile-bootstrap evidence for one metric."""

    observed_effect: float
    lower_decision_bound: float
    diagnostic_lower_bound: float
    diagnostic_upper_bound: float
    effective_seed: int
    requested_resamples: int
    effective_resamples: int


@dataclass(frozen=True, slots=True)
class BaselineReferenceResult(ComparisonEvidence):
    """Advisory reference evidence without a confidence interval."""

    reference_quantile: float
    reference_effect: float
    reference_anomaly: bool
    effective_seed: None
    requested_resamples: None
    effective_resamples: None


def bootstrap_cohorts(
    metric_inputs: tuple[MetricComparisonInput, ...],
    options: CohortBootstrapOptions = DEFAULT_COHORT_OPTIONS,
) -> tuple[CohortBootstrapResult, ...]:
    """Calculate seeded percentile-bootstrap evidence in lexical metric order."""
    _validate_cohort_options(options)
    return tuple(
        _bootstrap_metric(metric_input, options)
        for metric_input in _ordered_metric_inputs(metric_inputs, reference=False)
    )


def baseline_references(
    metric_inputs: tuple[MetricComparisonInput, ...],
    options: ReferenceOptions = DEFAULT_REFERENCE_OPTIONS,
) -> tuple[BaselineReferenceResult, ...]:
    """Calculate advisory reference evidence without any bootstrap randomness."""
    if options.seed is not None or options.requested_resamples is not None:
        raise BootstrapInputError(BootstrapValidationCode.REFERENCE_OVERRIDE)
    return tuple(
        _reference_metric(metric_input)
        for metric_input in _ordered_metric_inputs(metric_inputs, reference=True)
    )


def _validate_cohort_options(options: CohortBootstrapOptions) -> None:
    if options.seed < 0:
        raise BootstrapInputError(BootstrapValidationCode.INVALID_SEED)
    if options.requested_resamples < 1:
        raise BootstrapInputError(BootstrapValidationCode.INVALID_RESAMPLES)
    if options.enabled_metric_count < 1:
        raise BootstrapInputError(BootstrapValidationCode.INVALID_ENABLED_METRIC_COUNT)


def _ordered_metric_inputs(
    metric_inputs: tuple[MetricComparisonInput, ...], *, reference: bool
) -> tuple[MetricComparisonInput, ...]:
    for metric_input in metric_inputs:
        _validate_metric_input(metric_input, reference=reference)
    return tuple(sorted(metric_inputs, key=lambda metric_input: metric_input.metric_id))


def _validate_metric_input(
    metric_input: MetricComparisonInput, *, reference: bool
) -> None:
    if not metric_input.current:
        raise BootstrapInputError(BootstrapValidationCode.EMPTY_CURRENT)
    if not metric_input.baseline:
        raise BootstrapInputError(BootstrapValidationCode.EMPTY_BASELINE)
    alpha_is_valid = (
        math.isfinite(metric_input.requested_alpha)
        and math.isfinite(metric_input.effective_alpha)
        and 0.0 < metric_input.effective_alpha <= metric_input.requested_alpha < 1.0
    )
    if not alpha_is_valid:
        raise BootstrapInputError(BootstrapValidationCode.INVALID_ALPHA)
    threshold_is_valid = (
        math.isfinite(metric_input.practical_threshold)
        and metric_input.practical_threshold >= 0.0
    )
    if not threshold_is_valid:
        raise BootstrapInputError(BootstrapValidationCode.INVALID_PRACTICAL_THRESHOLD)
    if any(
        not math.isfinite(run_value.value)
        for run_value in metric_input.current + metric_input.baseline
    ):
        raise BootstrapInputError(BootstrapValidationCode.NONFINITE_INPUT)
    if reference and len(metric_input.current) != 1:
        raise BootstrapInputError(
            BootstrapValidationCode.REFERENCE_REQUIRES_ONE_CURRENT
        )


def _bootstrap_metric(
    metric_input: MetricComparisonInput, options: CohortBootstrapOptions
) -> CohortBootstrapResult:
    effective_resamples = max(
        options.requested_resamples,
        _MINIMUM_RESAMPLES_PER_ENABLED_METRIC * options.enabled_metric_count,
    )
    current_values = _oriented_float64_values(
        metric_input.current, metric_input.direction
    )
    baseline_values = _oriented_float64_values(
        metric_input.baseline, metric_input.direction
    )
    generator = np.random.Generator(np.random.PCG64(options.seed))
    differences = np.asarray(
        tuple(
            _draw_mean(current_values, generator)
            - _draw_mean(baseline_values, generator)
            for _ in range(effective_resamples)
        ),
        dtype=np.float64,
    )
    diagnostic_bounds = np.quantile(differences, _DIAGNOSTIC_QUANTILES, method="linear")
    return CohortBootstrapResult(
        metric_id=metric_input.metric_id,
        direction=metric_input.direction,
        method=ComparisonMethod.COHORT_BOOTSTRAP,
        algorithm_manifest=V1_ALGORITHM_MANIFEST,
        requested_alpha=metric_input.requested_alpha,
        effective_alpha=metric_input.effective_alpha,
        observed_effect=_mean(current_values) - _mean(baseline_values),
        lower_decision_bound=float(
            np.quantile(differences, metric_input.effective_alpha, method="linear")
        ),
        diagnostic_lower_bound=float(diagnostic_bounds[0]),
        diagnostic_upper_bound=float(diagnostic_bounds[1]),
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


def _reference_metric(metric_input: MetricComparisonInput) -> BaselineReferenceResult:
    current_values = _oriented_float64_values(
        metric_input.current, metric_input.direction
    )
    baseline_values = _oriented_float64_values(
        metric_input.baseline, metric_input.direction
    )
    reference_quantile = float(
        np.quantile(
            baseline_values,
            1.0 - metric_input.effective_alpha,
            method="linear",
        )
    )
    reference_effect = _mean(current_values) - reference_quantile
    return BaselineReferenceResult(
        metric_id=metric_input.metric_id,
        direction=metric_input.direction,
        method=ComparisonMethod.BASELINE_REFERENCE,
        algorithm_manifest=V1_ALGORITHM_MANIFEST,
        requested_alpha=metric_input.requested_alpha,
        effective_alpha=metric_input.effective_alpha,
        reference_quantile=reference_quantile,
        reference_effect=reference_effect,
        reference_anomaly=reference_effect > metric_input.practical_threshold,
        effective_seed=None,
        requested_resamples=None,
        effective_resamples=None,
        current_sample_ids=tuple(value.source_run_id for value in metric_input.current),
        baseline_sample_ids=tuple(
            value.source_run_id for value in metric_input.baseline
        ),
        current_sample_count=len(metric_input.current),
        baseline_sample_count=len(metric_input.baseline),
        sample_size_warning=metric_input.sample_size_warning,
    )


def _oriented_float64_values(
    run_values: tuple[RunValue, ...], direction: Direction
) -> npt.NDArray[np.float64]:
    match direction:
        case Direction.HIGHER_IS_WORSE:
            values = tuple(run_value.value for run_value in run_values)
        case Direction.LOWER_IS_WORSE:
            values = tuple(-run_value.value for run_value in run_values)
    return np.asarray(values, dtype=np.float64)


def _draw_mean(
    values: npt.NDArray[np.float64], generator: np.random.Generator
) -> float:
    drawn_values = values[generator.integers(0, len(values), size=len(values))]
    return _mean(drawn_values)


def _mean(values: npt.NDArray[np.float64]) -> float:
    return math.fsum(float(value) for value in values) / len(values)
