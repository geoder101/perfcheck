"""Input validation and deterministic ordering for bootstrap calculations."""

from __future__ import annotations

import math

from perfcheck.bootstrap_models import (
    BootstrapInputError,
    BootstrapValidationCode,
    CohortBootstrapOptions,
    MetricComparisonInput,
)


def validate_cohort_options(options: CohortBootstrapOptions) -> None:
    """Reject cohort-bootstrap options outside the numerical contract."""
    if options.seed < 0:
        raise BootstrapInputError(BootstrapValidationCode.INVALID_SEED)
    if options.requested_resamples < 1:
        raise BootstrapInputError(BootstrapValidationCode.INVALID_RESAMPLES)
    if options.enabled_metric_count < 1:
        raise BootstrapInputError(BootstrapValidationCode.INVALID_ENABLED_METRIC_COUNT)


def ordered_metric_inputs(
    metric_inputs: tuple[MetricComparisonInput, ...], *, reference: bool
) -> tuple[MetricComparisonInput, ...]:
    """Validate inputs then return them in stable lexical metric order."""
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
