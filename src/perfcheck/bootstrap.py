"""Stable public API for deterministic bootstrap comparison evidence."""

from __future__ import annotations

from perfcheck.bootstrap_models import (
    DEFAULT_COHORT_OPTIONS,
    DEFAULT_REFERENCE_OPTIONS,
    BaselineReferenceResult,
    BootstrapInputError,
    BootstrapValidationCode,
    CohortBootstrapOptions,
    CohortBootstrapResult,
    ComparisonEvidence,
    MetricComparisonInput,
    ReferenceOptions,
    RunValue,
)
from perfcheck.bootstrap_reference import reference_metric
from perfcheck.bootstrap_sampling import bootstrap_metric
from perfcheck.bootstrap_validation import (
    ordered_metric_inputs,
    validate_cohort_options,
)

__all__ = (
    "DEFAULT_COHORT_OPTIONS",
    "DEFAULT_REFERENCE_OPTIONS",
    "BaselineReferenceResult",
    "BootstrapInputError",
    "BootstrapValidationCode",
    "CohortBootstrapOptions",
    "CohortBootstrapResult",
    "ComparisonEvidence",
    "MetricComparisonInput",
    "ReferenceOptions",
    "RunValue",
    "baseline_references",
    "bootstrap_cohorts",
)


def bootstrap_cohorts(
    metric_inputs: tuple[MetricComparisonInput, ...],
    options: CohortBootstrapOptions = DEFAULT_COHORT_OPTIONS,
) -> tuple[CohortBootstrapResult, ...]:
    """Calculate seeded percentile-bootstrap evidence in lexical metric order."""
    validate_cohort_options(options)
    return tuple(
        bootstrap_metric(metric_input, options)
        for metric_input in ordered_metric_inputs(metric_inputs, reference=False)
    )


def baseline_references(
    metric_inputs: tuple[MetricComparisonInput, ...],
    options: ReferenceOptions = DEFAULT_REFERENCE_OPTIONS,
) -> tuple[BaselineReferenceResult, ...]:
    """Calculate advisory reference evidence without any bootstrap randomness."""
    if options.seed is not None or options.requested_resamples is not None:
        raise BootstrapInputError(BootstrapValidationCode.REFERENCE_OVERRIDE)
    return tuple(
        reference_metric(metric_input)
        for metric_input in ordered_metric_inputs(metric_inputs, reference=True)
    )
