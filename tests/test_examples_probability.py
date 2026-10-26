import math
from pathlib import Path
from statistics import variance

import pytest
from examples import _probability as probability

from tests.examples_check import run_standalone_notebook


def test_exact_coin_when_eight_heads_are_observed() -> None:
    # Given: ten independent fair flips and the preselected upper-tail event.
    # When: the exact distribution is enumerated.
    masses = probability.coin_distribution(10)
    # Then: mass is not the tail probability.
    assert masses[8] == 45 / 1024
    assert sum(masses[8:]) == 56 / 1024
    assert sum(masses) == 1.0


def test_coin_histogram_when_seed_and_budget_are_fixed() -> None:
    # Given: a bounded fair-coin experiment.
    # When: it is repeated from the same educational seed.
    first = probability.coin_experiment(10, 2000)
    second = probability.coin_experiment(10, 2000)
    # Then: draws repeat and approximate the theoretical mass, not exactly.
    assert first == second
    assert sum(first) == 2000
    assert first[5] / 2000 == pytest.approx(252 / 1024, abs=0.04)


@pytest.mark.parametrize("n", [4, 16, 64])
def test_means_when_iid_normal_model_has_known_standard_deviation(n: int) -> None:
    # Given: independent Normal(100, 8**2) measurements in ms.
    # When: repeated samples are generated from a fixed seed.
    result = probability.mean_experiment(n, 2000)
    # Then: individual spread and mean spread have different units of variation.
    assert result == probability.mean_experiment(n, 2000)
    assert variance(result.individuals) == pytest.approx(64, rel=0.12)
    assert math.sqrt(variance(result.means)) == pytest.approx(
        8 / math.sqrt(n), rel=0.08
    )
    assert result.theoretical_se == 8 / math.sqrt(n)


@pytest.mark.parametrize(
    ("n", "repetitions"), [(0, 100), (41, 100), (10, 0), (10, 2001)]
)
def test_coin_rejects_work_when_outside_budget(n: int, repetitions: int) -> None:
    # Given: an out-of-budget request.
    # When/Then: the pure helper refuses it before allocating draws.
    with pytest.raises(ValueError, match="budget"):
        _ = probability.coin_experiment(n, repetitions)


def test_maximum_work_when_all_controls_are_at_the_limit() -> None:
    # Given: the largest offered workloads.
    # When: each helper evaluates the maximum budget.
    counts = probability.coin_experiment(40, 2000)
    means = probability.mean_experiment(64, 2000)
    # Then: output sizes remain bounded independently of the UI.
    assert len(counts) == 41
    assert len(means.means) == len(means.individuals) == 2000


@pytest.mark.parametrize(("n", "repetitions"), [(3, 100), (65, 100), (4, 2001)])
def test_means_reject_work_when_outside_budget(n: int, repetitions: int) -> None:
    # Given: an unsupported sample size or excessive repetitions.
    # When/Then: no unbounded sample matrix is generated.
    with pytest.raises(ValueError, match="budget"):
        _ = probability.mean_experiment(n, repetitions)


def test_probability_lesson_when_run_as_a_script() -> None:
    # Given: the standalone canonical notebook.
    lesson = Path(__file__).parents[1] / "examples/06-statistical-foundations.py"
    # When: the real Marimo app evaluates default controls.
    result = run_standalone_notebook(lesson)
    # Then: old receipts survive alongside new probability evidence.
    assert result.returncode == 0, result.stderr
    assert "sampling-distribution center 11.500" in result.stdout
    assert "mass=45/1024; upper_tail=56/1024" in result.stdout


def test_density_when_interval_probability_is_requested() -> None:
    # Given: the central two standard-deviation-wide normal interval.
    # When: density, area, and cumulative probability are evaluated separately.
    density, area, cdf = probability.normal_region((-1.0, 1.0))
    # Then: density has different meaning from either probability.
    assert density == pytest.approx(0.24197072451914337)
    assert area == pytest.approx(0.6826894921370859)
    assert cdf == pytest.approx(0.8413447460685429)
    assert probability.normal_region((1.0, 1.0))[1] == 0.0


@pytest.mark.parametrize("bounds", [(1.0, -1.0), (-5.0, 0.0), (0.0, math.nan)])
def test_density_rejects_region_when_bounds_are_invalid(
    bounds: tuple[float, float],
) -> None:
    # Given: reversed, excessive, or nonfinite bounds.
    # When/Then: the region boundary refuses the request.
    with pytest.raises(ValueError, match="ordered bounds"):
        _ = probability.normal_region(bounds)


def test_svg_when_negative_or_singleton_values_are_displayed() -> None:
    # Given: a single negative oriented observation and unsafe label characters.
    series = (
        probability.PlotSeries("dashed: observed <tail>", ((1.0, -25.0),), dashed=True),
    )
    # When: the offline plot is rendered.
    svg = probability.plot_svg(
        ("<Title>", "Index (count)", "Throughput (requests/s)"), series
    )
    # Then: accessible units, negative ticks, markers, and escaped labels survive.
    assert 'role="img"' in svg
    assert "&lt;Title&gt;" in svg
    assert "&lt;tail&gt;" in svg
    assert "-25" in svg
    assert "requests/s" in svg
    assert "stroke-dasharray" in svg
    assert "<circle" in svg
    assert "http://" not in svg.replace('xmlns="http://www.w3.org/2000/svg"', "")


@pytest.mark.parametrize("point", [(math.nan, 1.0), (1.0, math.inf), (-math.inf, 1.0)])
def test_svg_rejects_geometry_when_coordinates_are_nonfinite(
    point: tuple[float, float],
) -> None:
    # Given: a coordinate that cannot produce finite SVG geometry.
    series = (probability.PlotSeries("invalid", (point,)),)
    # When/Then: rendering rejects it instead of emitting NaN/Inf attributes.
    with pytest.raises(ValueError, match="finite"):
        _ = probability.plot_svg(("Title", "x", "y"), series)


@pytest.mark.parametrize("empty_series", [False, True])
def test_svg_rejects_empty_data_when_series_or_points_are_missing(
    empty_series: bool,
) -> None:
    # Given: no series or a series with no drawable points.
    series = (probability.PlotSeries("empty", ()),) if empty_series else ()
    # When/Then: the missing evidence has an explicit boundary error.
    with pytest.raises(ValueError, match="nonempty"):
        _ = probability.plot_svg(("Title", "x", "y"), series)


def test_svg_rejects_geometry_when_finite_endpoints_overflow_the_axis_span() -> None:
    # Given: finite endpoints whose subtraction exceeds floating-point range.
    series = (probability.PlotSeries("overflow", ((-1e308, 0.0), (1e308, 1.0))),)
    # When/Then: the chart refuses an unrepresentable scale.
    with pytest.raises(ValueError, match="finite"):
        _ = probability.plot_svg(("Title", "x", "y"), series)


@pytest.mark.parametrize("heads", [-1, 11])
def test_coin_plot_rejects_cutoff_when_outside_support(heads: int) -> None:
    # Given: an impossible observed head count for ten flips.
    # When/Then: plotting uses the same support as the probability experiment.
    with pytest.raises(ValueError, match="heads"):
        _ = probability.coin_plot(10, heads, 100)


def test_normal_plot_rejects_region_when_bounds_are_reversed() -> None:
    # Given: a reversed interval passed directly to the plotting wrapper.
    # When/Then: plotting cannot bypass the numerical boundary.
    with pytest.raises(ValueError, match="ordered bounds"):
        _ = probability.normal_plots((1.0, -1.0))


def test_chart_when_viewport_is_narrow_preserves_readable_scrollable_geometry() -> None:
    # Given: an ordinary chart in a notebook that can have a 375px viewport.
    series = (probability.PlotSeries("solid: mass", ((0.0, 0.25), (1.0, 0.75))),)
    # When: its shared offline renderer produces the chart container.
    html = probability.plot_svg(("Coin", "Heads (count)", "Probability"), series)
    # Then: a bounded keyboard-scrollable region preserves unscaled 16px labels.
    assert 'role="region"' in html
    assert 'tabindex="0"' in html
    assert "overflow-x:auto" in html
    assert "max-width:100%" in html
    assert 'width="640"' in html
    assert 'height="300"' in html
    assert "max-width:none" in html
    assert 'font-size="16"' in html
    assert 'font-size="12"' not in html


@pytest.mark.parametrize(
    ("lesson", "document"),
    [
        ("06-statistical-foundations.py", "probability-and-distributions.rst"),
        ("07-summary-and-eligibility.py", "experimental-design.rst"),
    ],
)
def test_companion_source_when_lesson_is_served_standalone_has_no_docs_url(
    lesson: str, document: str
) -> None:
    # Given: Marimo does not serve repository-relative Sphinx sources.
    root = Path(__file__).parents[1]
    # When: the offline lesson's source reference is inspected.
    source = (root / "examples" / lesson).read_text(encoding="utf-8")
    # Then: the accurate checkout path remains, without a guaranteed-broken URL.
    assert f"docs/explanation/{document}" in source.replace("<wbr>", "")
    assert "../docs/explanation/" not in source
    assert (root / "docs/explanation" / document).is_file()
