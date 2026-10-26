import importlib.util
import re
import sys
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pytest
from examples import _inference as inference
from examples import _inference_plots as plots
from examples._support import run_local_command


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
    assert all(
        row.contains == (row.lower <= 100 <= row.upper) for row in result.intervals
    )
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


def test_inference_lesson_when_executed_retains_receipts(tmp_path: Path) -> None:
    # Given: the actual notebook, executed from an unrelated empty workspace.
    if importlib.util.find_spec("marimo") is None:
        pytest.skip("inference lesson requires the optional examples group")
    lesson = (
        Path(__file__).resolve().parents[1] / "examples/08-bootstrap-and-decisions.py"
    )
    # When: the notebook runs as a bounded offline Python script.
    result = run_local_command(
        (sys.executable, str(lesson)), cwd=tmp_path, timeout_seconds=15.0
    )
    # Then: default numerical receipts and the separate coverage experiment survive.
    assert result.returncode == 0, result.stderr
    assert "effective_resamples=4000" in result.stdout
    assert "oriented_effect=10.000; lower_bound=9.000" in result.stdout
    assert "reference_effect=9.075; anomaly=True; verdict=INCONCLUSIVE" in result.stdout
    assert "Welch t=-17.321" in result.stdout
    assert "Known-sigma CI: achieved coverage=" in result.stdout
    assert tuple(tmp_path.iterdir()) == ()


@pytest.mark.parametrize("method", ["none", "Bonferroni", "Holm", "BH"])
def test_singleton_family_when_rendered_has_three_visible_series(method: str) -> None:
    # Given: the actual multiplicity panel, whose raw and adjusted p coincide at m=1.
    if importlib.util.find_spec("marimo") is None:
        pytest.skip("multiplicity panel requires the optional examples group")
    script = (
        "from examples._multiplicity_panel import multiplicity_panel; "
        "from examples._multiple_testing import FamilyExperiment; "
        f"print(multiplicity_panel(FamilyExperiment(size=1,true_nulls=1,method='{method}')).text)"
    )
    # When: all three real panel series are rendered, including the coincident cutoff.
    result = run_local_command(
        (sys.executable, "-c", script),
        cwd=Path(__file__).resolve().parents[1],
        timeout_seconds=15.0,
    )
    assert result.returncode == 0, result.stderr
    match = re.search(r"<svg\b.*?</svg>", result.stdout, flags=re.DOTALL)
    assert match is not None
    svg = ET.fromstring(match[0])  # noqa: S314 - trusted local renderer output
    groups = svg.findall(".//{*}g[@data-series]")
    # Then: distinct coincident glyphs and a nonzero cutoff segment remain visible.
    assert len(groups) == 3
    raw = groups[0].find("{*}circle")
    adjusted = groups[1].find("{*}rect")
    cutoff = groups[2].find("{*}line")
    assert raw is not None
    assert adjusted is not None
    assert cutoff is not None
    assert float(raw.attrib["r"]) > 0
    assert float(adjusted.attrib["width"]) > 2 * float(raw.attrib["r"])
    assert float(adjusted.attrib["x"]) + float(adjusted.attrib["width"]) / 2 == float(
        raw.attrib["cx"]
    )
    assert float(adjusted.attrib["y"]) + float(adjusted.attrib["height"]) / 2 == float(
        raw.attrib["cy"]
    )
    assert (
        float(cutoff.attrib["x1"])
        < float(raw.attrib["cx"])
        < float(cutoff.attrib["x2"])
    )
    assert cutoff.attrib["y1"] == cutoff.attrib["y2"]


def test_chart_when_narrow_keeps_axis_labels_and_legends_outside_scaled_svg() -> None:
    # Given: an annotated chart whose figure must work without magnification.
    spec = plots.PlotSpec("Readable experiment", "Shift (ms)", "Density (1/ms)")
    series = (plots.Series("Measured curve", ((0.0, 0.0), (1.0, 1.0))),)
    # When: the responsive figure is generated.
    markup = plots.line_plot(spec, series)
    figure = ET.fromstring(markup)  # noqa: S314 - trusted local renderer output
    # Then: axis labels and legend text use HTML sizing, not SVG viewport scaling.
    assert figure.tag == "figure"
    assert figure.find("figcaption") is not None
    assert figure.find(".//*[@data-axis='x']") is not None
    assert figure.find(".//*[@data-axis='y']") is not None
    legend = figure.find(".//ul")
    assert legend is not None
    assert "Measured curve" in "".join(legend.itertext())


def test_chart_when_regions_overlap_uses_distinct_noncolor_fills() -> None:
    # Given: alpha and beta regions like the power panel, with equal gray outlines.
    spec = plots.PlotSpec("Power regions", "Shift (ms)", "Density (1/ms)")
    points = ((0.0, 0.0), (1.0, 1.0), (2.0, 0.0))
    series = tuple(
        plots.Series(label, points, shade=True) for label in ("alpha", "beta")
    )
    # When: the probability regions are rendered.
    markup = plots.line_plot(spec, series)
    figure = ET.fromstring(markup)  # noqa: S314 - trusted local renderer output
    polygons = figure.findall(".//{*}polygon")
    # Then: separate pattern definitions and legend swatches encode both regions.
    assert len(polygons) == 2
    assert polygons[0].attrib["fill"] != polygons[1].attrib["fill"]
    assert all(row.attrib["fill"].startswith("url(#") for row in polygons)
    assert len(figure.findall(".//{*}pattern")) == 2
