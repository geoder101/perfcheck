import math
from dataclasses import dataclass

import pytest

from perfcheck.bootstrap import (
    DEFAULT_REFERENCE_OPTIONS,
    BootstrapInputError,
    BootstrapValidationCode,
    CohortBootstrapOptions,
    MetricComparisonInput,
    ReferenceOptions,
    RunValue,
    baseline_references,
    bootstrap_cohorts,
)
from perfcheck.model_types import (
    V1_ALGORITHM_MANIFEST,
    ComparisonMethod,
    Direction,
)


@dataclass(frozen=True, slots=True)
class MetricFixture:
    metric_id: str
    direction: Direction
    current: tuple[RunValue, ...]
    baseline: tuple[RunValue, ...]
    practical_threshold: float = 5.0
    requested_alpha: float = 0.05
    effective_alpha: float = 0.025
    sample_size_warning: bool = False


_COHORT_CURRENT = (
    RunValue(source_run_id="current-1", value=2.5),
    RunValue(source_run_id="current-2", value=4.0),
    RunValue(source_run_id="current-3", value=9.25),
    RunValue(source_run_id="current-4", value=11.5),
    RunValue(source_run_id="current-5", value=15.75),
)
_COHORT_BASELINE = (
    RunValue(source_run_id="baseline-1", value=1.0),
    RunValue(source_run_id="baseline-2", value=3.5),
    RunValue(source_run_id="baseline-3", value=6.5),
    RunValue(source_run_id="baseline-4", value=7.0),
    RunValue(source_run_id="baseline-5", value=8.75),
    RunValue(source_run_id="baseline-6", value=12.0),
    RunValue(source_run_id="baseline-7", value=13.5),
)


def _metric_input(fixture: MetricFixture) -> MetricComparisonInput:
    return MetricComparisonInput(
        metric_id=fixture.metric_id,
        direction=fixture.direction,
        requested_alpha=fixture.requested_alpha,
        effective_alpha=fixture.effective_alpha,
        practical_threshold=fixture.practical_threshold,
        current=fixture.current,
        baseline=fixture.baseline,
        sample_size_warning=fixture.sample_size_warning,
    )


def _cohort_fixture(metric_id: str = "latency") -> MetricFixture:
    return MetricFixture(
        metric_id=metric_id,
        direction=Direction.HIGHER_IS_WORSE,
        current=_COHORT_CURRENT,
        baseline=_COHORT_BASELINE,
    )


def _cohort_options(
    seed: int = 19, requested_resamples: int = 7
) -> CohortBootstrapOptions:
    return CohortBootstrapOptions(
        seed=seed,
        requested_resamples=requested_resamples,
        enabled_metric_count=2,
    )


def test_bootstrap_cohorts_use_pcg64_draw_order_and_linear_quantiles() -> None:
    # Given: comparable per-run values and a Bonferroni-sized bootstrap request.
    metric = _metric_input(_cohort_fixture())

    # When: the cohort calculation uses the fixed PCG64 percentile contract.
    (result,) = bootstrap_cohorts((metric,), _cohort_options())

    # Then: it retains the exact seeded estimator, quantiles, and provenance.
    assert result.method is ComparisonMethod.COHORT_BOOTSTRAP
    assert result.algorithm_manifest is V1_ALGORITHM_MANIFEST
    assert result.observed_effect == 1.1357142857142852
    assert result.lower_decision_bound == -3.9287500000000004
    assert result.diagnostic_lower_bound == -3.9287500000000004
    assert result.diagnostic_upper_bound == 6.428928571428573
    assert result.effective_seed == 19
    assert result.requested_resamples == 7
    assert result.effective_resamples == 4000
    assert result.current_sample_ids == tuple(
        value.source_run_id for value in _COHORT_CURRENT
    )
    assert result.baseline_sample_ids == tuple(
        value.source_run_id for value in _COHORT_BASELINE
    )
    assert result.current_sample_count == 5
    assert result.baseline_sample_count == 7


def test_bootstrap_cohorts_sort_metrics_and_reinitialize_the_generator() -> None:
    # Given: equal cohorts supplied in reverse lexical metric order.
    metrics = (
        _metric_input(_cohort_fixture("zeta")),
        _metric_input(_cohort_fixture("alpha")),
    )

    # When: independent per-metric bootstrap calculations run.
    results = bootstrap_cohorts(metrics, _cohort_options())

    # Then: lexical output ordering and fresh identical seeded streams are retained.
    assert tuple(result.metric_id for result in results) == ("alpha", "zeta")
    assert results[0].lower_decision_bound == results[1].lower_decision_bound
    assert results[0].diagnostic_upper_bound == results[1].diagnostic_upper_bound


def test_bootstrap_cohorts_changes_only_stochastic_results_for_a_changed_seed() -> None:
    # Given: one fixed comparable metric and two permitted cohort seeds.
    metric = _metric_input(_cohort_fixture())

    # When: the seed changes without changing cohorts or policy inputs.
    (first,) = bootstrap_cohorts((metric,), _cohort_options(seed=19))
    (second,) = bootstrap_cohorts((metric,), _cohort_options(seed=29))

    # Then: provenance stays fixed while the sampled percentile result may differ.
    assert first.metric_id == second.metric_id
    assert first.current_sample_ids == second.current_sample_ids
    assert first.baseline_sample_ids == second.baseline_sample_ids
    assert first.observed_effect == second.observed_effect
    assert first.lower_decision_bound != second.lower_decision_bound


def test_baseline_reference_uses_the_oriented_tail_quantile_as_an_advisory() -> None:
    # Given: one lower-is-worse current value and a baseline reference cohort.
    metric = _metric_input(
        MetricFixture(
            metric_id="throughput",
            direction=Direction.LOWER_IS_WORSE,
            current=(RunValue(source_run_id="current-1", value=20.0),),
            baseline=(
                RunValue(source_run_id="baseline-1", value=30.0),
                RunValue(source_run_id="baseline-2", value=25.0),
                RunValue(source_run_id="baseline-3", value=35.0),
            ),
        )
    )

    # When: the one-current advisory reference calculation runs.
    (result,) = baseline_references((metric,), DEFAULT_REFERENCE_OPTIONS)

    # Then: it has no bootstrap CI/options and records the strict anomaly signal.
    assert result.method is ComparisonMethod.BASELINE_REFERENCE
    assert result.reference_quantile == -25.25
    assert result.reference_effect == 5.25
    assert result.reference_anomaly is True
    assert result.effective_seed is None
    assert result.requested_resamples is None
    assert result.effective_resamples is None


def test_bootstrap_cohorts_allow_tied_constant_values() -> None:
    # Given: constant per-run cohorts that contain only tied scalar values.
    metric = _metric_input(
        MetricFixture(
            metric_id="memory",
            direction=Direction.HIGHER_IS_WORSE,
            current=(
                RunValue(source_run_id="current-1", value=10.0),
                RunValue(source_run_id="current-2", value=10.0),
            ),
            baseline=(
                RunValue(source_run_id="baseline-1", value=7.0),
                RunValue(source_run_id="baseline-2", value=7.0),
            ),
        )
    )

    # When: the percentile bootstrap samples the degenerate cohorts.
    (result,) = bootstrap_cohorts((metric,), _cohort_options())

    # Then: tied constants remain valid and yield their exact constant effect.
    assert result.observed_effect == 3.0
    assert result.lower_decision_bound == 3.0
    assert result.diagnostic_lower_bound == 3.0
    assert result.diagnostic_upper_bound == 3.0


def test_bootstrap_cohorts_reject_invalid_confidence() -> None:
    # Given: a cohort whose requested alpha is outside the open unit interval.
    metric = _metric_input(
        MetricFixture(
            metric_id="latency",
            direction=Direction.HIGHER_IS_WORSE,
            current=_COHORT_CURRENT,
            baseline=_COHORT_BASELINE,
            requested_alpha=1.0,
        )
    )

    # When: the bootstrap boundary validates the metric contract.
    with pytest.raises(BootstrapInputError) as error:
        bootstrap_cohorts((metric,), _cohort_options())

    # Then: it identifies the invalid confidence input.
    assert error.value.code is BootstrapValidationCode.INVALID_ALPHA


def test_bootstrap_cohorts_reject_invalid_resamples() -> None:
    # Given: a valid cohort with a non-positive requested resample count.
    metric = _metric_input(_cohort_fixture())

    # When: the bootstrap options cross the numerical boundary.
    with pytest.raises(BootstrapInputError) as error:
        bootstrap_cohorts((metric,), _cohort_options(requested_resamples=0))

    # Then: it reports the stable resample validation error.
    assert error.value.code is BootstrapValidationCode.INVALID_RESAMPLES


def test_bootstrap_cohorts_reject_nonfinite_run_values() -> None:
    # Given: a run-level input containing a non-finite scalar.
    metric = _metric_input(
        MetricFixture(
            metric_id="latency",
            direction=Direction.HIGHER_IS_WORSE,
            current=(RunValue(source_run_id="current-1", value=math.nan),),
            baseline=_COHORT_BASELINE,
        )
    )

    # When: numerical input validation precedes random sampling.
    with pytest.raises(BootstrapInputError) as error:
        bootstrap_cohorts((metric,), _cohort_options())

    # Then: no invalid value can reach the percentile calculation.
    assert error.value.code is BootstrapValidationCode.NONFINITE_INPUT


def test_baseline_reference_rejects_bootstrap_overrides_with_code_three_error() -> None:
    # Given: a valid single-current reference metric and a forbidden seed override.
    metric = _metric_input(
        MetricFixture(
            metric_id="throughput",
            direction=Direction.LOWER_IS_WORSE,
            current=(RunValue(source_run_id="current-1", value=20.0),),
            baseline=(RunValue(source_run_id="baseline-1", value=30.0),),
        )
    )

    # When: reference mode receives a bootstrap-only option.
    with pytest.raises(BootstrapInputError) as error:
        baseline_references((metric,), ReferenceOptions(seed=42))

    # Then: callers receive the documented user-input exit classification.
    assert error.value.code is BootstrapValidationCode.REFERENCE_OVERRIDE
    assert error.value.exit_code == 3
