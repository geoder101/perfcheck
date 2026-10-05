"""Advisory baseline-reference evidence calculations."""

from __future__ import annotations

import numpy as np

from perfcheck.bootstrap_models import BaselineReferenceResult, MetricComparisonInput
from perfcheck.bootstrap_sampling import mean, oriented_float64_values
from perfcheck.model_types import V1_ALGORITHM_MANIFEST, ComparisonMethod


def reference_metric(metric_input: MetricComparisonInput) -> BaselineReferenceResult:
    """Calculate non-stochastic baseline-reference evidence for one metric."""
    current_values = oriented_float64_values(
        metric_input.current, metric_input.direction
    )
    baseline_values = oriented_float64_values(
        metric_input.baseline, metric_input.direction
    )
    reference_quantile = float(
        np.quantile(
            baseline_values,
            1.0 - metric_input.effective_alpha,
            method="linear",
        )
    )
    reference_effect = mean(current_values) - reference_quantile
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
