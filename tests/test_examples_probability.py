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
    assert math.sqrt(variance(result.means)) == pytest.approx(8 / math.sqrt(n), rel=0.08)
    assert result.theoretical_se == 8 / math.sqrt(n)


@pytest.mark.parametrize(("n", "repetitions"), [(0, 100), (41, 100), (10, 0), (10, 2001)])
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
