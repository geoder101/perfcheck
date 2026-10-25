from dataclasses import replace

import numpy as np
import pytest
from examples import _inference as inference
from examples import _inference_plots as plots


def test_bootstrap_when_default_inputs_preserves_draw_receipt() -> None:
    # Given: the original lower-is-worse throughput fixture.
    experiment = inference.BootstrapExperiment()
    # When: the actual seeded bootstrap distribution is calculated.
    result = inference.bootstrap_experiment(experiment)
    # Then: the original floor, observed effect and percentile are preserved.
    assert len(result.draws) == 4000
    assert result.effect == 10.0
    assert result.lower == 9.0
    assert result.verdict == "FAIL"
    assert result.reference_effect == pytest.approx(9.075)


def test_bootstrap_when_threshold_equals_bound_passes() -> None:
    # Given: constant cohorts separated by exactly the practical threshold.
    experiment = inference.BootstrapExperiment(
        baseline=(100.0, 100.0), current=(97.0, 97.0), threshold=3.0
    )
    # When: the strict lower-bound comparison is evaluated.
    result = inference.bootstrap_experiment(experiment)
    # Then: equality never fails or raises the reference anomaly.
    assert result.lower == 3.0
    assert result.verdict == "PASS"
    assert not result.reference_anomaly


def test_bootstrap_when_orientation_changes_reverses_effect() -> None:
    # Given: otherwise identical higher-is-worse cohorts.
    experiment = inference.BootstrapExperiment(higher_is_worse=True)
    # When: worsening is oriented positively.
    result = inference.bootstrap_experiment(experiment)
    # Then: an improvement has a negative effect.
    assert result.effect == -10.0
    assert result.verdict == "PASS"


def test_bootstrap_when_seeded_matches_independent_interleaved_oracle() -> None:
    # Given: asymmetric cohorts and three enabled tests.
    experiment = inference.BootstrapExperiment(
        baseline=(1.0, 4.0, 8.0), current=(2.0, 9.0), enabled=3, seed=19
    )
    rng = np.random.Generator(np.random.PCG64(19))
    expected = tuple(
        -np.mean(rng.choice(experiment.current, 2))
        + np.mean(rng.choice(experiment.baseline, 3))
        for _ in range(6000)
    )
    # When: the helper computes its draw distribution.
    result = inference.bootstrap_experiment(experiment)
    # Then: float64 draws and the linear adjusted percentile agree exactly.
    assert result.draws == expected
    assert result.lower == float(np.quantile(expected, 0.05 / 3, method="linear"))


def test_intervals_when_seeded_report_actual_containment() -> None:
    # Given: a repeated IID normal experiment with known sigma, not bootstrap.
    experiment = inference.CoverageExperiment(repetitions=512, seed=4)
    # When: intervals are built around simulated sample means.
    result = inference.coverage_experiment(experiment)
    # Then: containment is computed per interval, with reproducible MC uncertainty.
    assert result == inference.coverage_experiment(experiment)
    assert result.coverage == sum(row.contains for row in result.intervals) / 512
    assert 0.90 < result.coverage < 0.99
    assert all(row.contains == (row.lower <= 100 <= row.upper) for row in result.intervals)
    assert result.mc_se > 0


@pytest.mark.parametrize("repetitions", [0, 513])
def test_intervals_when_budget_invalid_rejects(repetitions: int) -> None:
    # Given: a simulation outside the interactive budget.
    # When: its typed inputs are constructed.
    with pytest.raises(ValueError, match="repetitions"):
        _ = replace(inference.CoverageExperiment(), repetitions=repetitions)
    # Then: no unbounded experiment can run.


def test_chart_when_series_differ_has_labels_and_noncolor_encoding() -> None:
    # Given: two curves and a threshold in a shared numeric coordinate system.
    spec = plots.PlotSpec("Power model", "Mean shift (ms)", "Density (1/ms)")
    series = (plots.Series("Null solid", ((0.0, 1.0), (1.0, 0.0))),)
    # When: the offline chart is rendered.
    svg = plots.line_plot(spec, series, (0.5, "Critical mean"))
    # Then: axes, legend and threshold remain readable without color or a network.
    assert "Mean shift (ms)" in svg
    assert "Density (1/ms)" in svg
    assert "Critical mean" in svg
    assert "Null solid" in svg
    assert 'role="img"' in svg
    assert "stroke-dasharray" in svg
    assert "http" not in svg.replace("http://www.w3.org/2000/svg", "")
