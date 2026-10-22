from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
import pytest

from tests.examples_check import run_standalone_notebook

_ROOT = Path(__file__).parents[1]
_LESSON = _ROOT / "examples/09-plain-python-mechanics.py"


@runtime_checkable
class Mechanics(Protocol):
    def mean(self, values: tuple[float, ...]) -> float: ...
    def linear_quantile(self, values: tuple[float, ...], q: float) -> float: ...
    def sample_variance(self, values: tuple[float, ...]) -> float: ...
    def slope(self, seconds: tuple[float, ...], values: tuple[float, ...]) -> float: ...
    def resample_means(
        self, values: tuple[float, ...], seed: int, count: int
    ) -> tuple[float, ...]: ...
    def orient(
        self, values: tuple[float, ...], *, lower_is_worse: bool
    ) -> tuple[float, ...]: ...


@pytest.fixture
def mechanics() -> Mechanics:
    if importlib.util.find_spec("marimo") is None:
        pytest.skip("mechanics helpers require the optional examples group")
    spec = importlib.util.spec_from_file_location("plain_python_mechanics", _LESSON)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert isinstance(module, Mechanics)
    return module


def test_plain_formulas_match_numpy_when_given_finite_toy_values(
    mechanics: Mechanics,
) -> None:
    # Given: the retained values and elapsed seconds from lesson 07.
    values = (4.0, 6.0, 10.0, 14.0, 20.0)
    seconds = (0.0, 15.0, 30.0, 45.0, 60.0)

    # When: plain-Python descriptive formulas are evaluated.
    actual = (
        mechanics.mean(values),
        mechanics.sample_variance(values),
        math.sqrt(mechanics.sample_variance(values)),
        mechanics.slope(seconds, values),
    )

    # Then: the equivalent NumPy formulas agree numerically, not bitwise in general.
    time_array: np.ndarray[tuple[int], np.dtype[np.float64]] = np.asarray(
        seconds, dtype=np.float64
    )
    value_array: np.ndarray[tuple[int], np.dtype[np.float64]] = np.asarray(
        values, dtype=np.float64
    )
    expected_slope = float(
        np.mean(
            (time_array - np.mean(time_array)) * (value_array - np.mean(value_array))
        )
        / np.mean((time_array - np.mean(time_array)) ** 2)
    )
    assert actual == pytest.approx(
        (
            np.mean(values),
            np.var(values, ddof=1),
            np.std(values, ddof=1),
            expected_slope,
        )
    )
    assert actual == pytest.approx((10.8, 41.2, math.sqrt(41.2), 4.0 / 15.0))


@pytest.mark.parametrize("q", [0.0, 0.025, 0.25, 0.5, 0.9, 0.975, 1.0])
def test_linear_quantile_matches_numpy_when_interpolating(
    mechanics: Mechanics, q: float
) -> None:
    # Given: unordered values including ties and a linear interpolation probability.
    values = (20.0, 4.0, 10.0, 6.0, 10.0)

    # When: the educational order-statistic interpolation runs.
    actual = mechanics.linear_quantile(values, q)

    # Then: endpoints and interpolated values match NumPy's explicit linear method.
    assert actual == pytest.approx(float(np.quantile(values, q, method="linear")))


@pytest.mark.parametrize("values", [(), (math.nan,), (math.inf,), (-math.inf,)])
def test_mean_rejects_invalid_values_when_crossing_formula_boundary(
    mechanics: Mechanics, values: tuple[float, ...]
) -> None:
    # Given: an empty or nonfinite educational input.
    # When: it enters the mean formula.
    # Then: it is rejected rather than rendered as plausible evidence.
    with pytest.raises(ValueError, match="nonempty finite"):
        _ = mechanics.mean(values)


def test_seeded_draws_and_orientation_when_repeating_the_toy_experiment(
    mechanics: Mechanics,
) -> None:
    # Given: finite lower-is-worse baseline throughput and a fixed educational seed.
    baseline = mechanics.orient((30.0, 25.0, 35.0), lower_is_worse=True)

    # When: the same seeded with-replacement experiment is repeated.
    first = mechanics.resample_means(baseline, 42, 8)
    second = mechanics.resample_means(baseline, 42, 8)

    # Then: draws repeat locally and the advisory upper oriented tail is -25.25.
    assert first == second
    assert first == pytest.approx(
        (-95 / 3, -30.0, -95 / 3, -100 / 3, -100 / 3, -85 / 3, -30.0, -100 / 3)
    )
    assert len(first) == 8
    assert all(-35.0 <= value <= -25.0 for value in first)
    assert mechanics.linear_quantile(baseline, 0.975) == pytest.approx(-25.25)
    assert -20.0 - mechanics.linear_quantile(baseline, 0.975) == pytest.approx(5.25)
    assert mechanics.orient((30.0,), lower_is_worse=False) == (30.0,)


def test_lesson_output_when_executed_in_isolation() -> None:
    # Given: the absolute canonical lesson path.
    # When: two clean temporary workspaces execute the lesson.
    first = run_standalone_notebook(_LESSON)
    second = run_standalone_notebook(_LESSON)

    # Then: all five sections and the numerical/non-equivalence receipts repeat.
    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    assert first.stdout == second.stdout
    sections = ("Goal:", "Inputs:", "Run:", "Evidence:", "Takeaway:")
    positions = tuple(first.stdout.index(section) for section in sections)
    assert positions == tuple(sorted(positions))
    for receipt in (
        "mean=10.800; q90=17.600; variance=41.200; sd=6.418723; slope=0.266667",
        "reference_quantile=-25.250; reference_effect=5.250; anomaly=True",
        "INCONCLUSIVE",
        "not bitwise or evidence-compatible",
        "NumPy PCG64",
        "decision_q=0.025; diagnostic_q=(0.025, 0.975)",
        "lower_bound=3.625000; diagnostic_bounds=(3.625000, 13.191667)",
        "oriented_effect=8.000",
    ):
        assert receipt in first.stdout


@pytest.mark.parametrize("q", [-0.1, 1.1, math.nan, math.inf])
def test_quantile_rejects_invalid_probability_when_called(
    mechanics: Mechanics, q: float
) -> None:
    # Given: finite observations and an invalid probability.
    # When: the probability enters the quantile formula.
    # Then: interpolation is rejected at its boundary.
    with pytest.raises(ValueError, match="probability"):
        _ = mechanics.linear_quantile((4.0, 6.0), q)


def test_quantile_selects_singleton_when_only_one_value_exists(
    mechanics: Mechanics,
) -> None:
    # Given: one finite observation.
    # When: an interior quantile is selected.
    actual = mechanics.linear_quantile((4.0,), 0.9)
    # Then: there is no neighboring value to interpolate toward.
    assert actual == 4.0


def test_variance_rejects_singleton_when_sample_spread_is_undefined(
    mechanics: Mechanics,
) -> None:
    # Given: one observation, with no sample degrees of freedom.
    # When: sample variance is requested.
    # Then: the undefined denominator is rejected.
    with pytest.raises(ValueError, match="at least two"):
        _ = mechanics.sample_variance((4.0,))


@pytest.mark.parametrize("seconds", [(0.0,), (0.0, 0.0)])
def test_slope_rejects_undefined_fit_when_times_are_invalid(
    mechanics: Mechanics, seconds: tuple[float, ...]
) -> None:
    # Given: mismatched or identical elapsed times for two observations.
    # When: a centered least-squares fit is requested.
    # Then: the undefined fit is rejected.
    with pytest.raises(ValueError, match=r"equal-length|distinct times"):
        _ = mechanics.slope(seconds, (4.0, 6.0))


@pytest.mark.parametrize(("seed", "count"), [(-1, 8), (42, 0), (42, -1)])
def test_resampling_rejects_invalid_request_when_seed_or_count_is_invalid(
    mechanics: Mechanics, seed: int, count: int
) -> None:
    # Given: an invalid seed or replicate count.
    # When: the educational draw request enters the sampler.
    # Then: it is rejected rather than producing an empty or misleading receipt.
    with pytest.raises(ValueError, match="positive count and nonnegative seed"):
        _ = mechanics.resample_means((4.0, 6.0), seed, count)
