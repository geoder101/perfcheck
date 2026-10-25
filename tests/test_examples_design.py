import math
from pathlib import Path
from statistics import variance

import pytest

from examples import _design as design
from tests.examples_check import run_standalone_notebook


def test_schedule_contrast_when_time_is_confounded_or_balanced() -> None:
    # Given: Y = 100 + 2*time + 3*treatment with eight scheduled runs.
    # When: the same model is evaluated under two assignment schedules.
    confounded = design.schedule_experiment(False)
    balanced = design.schedule_experiment(True)
    # Then: balanced time removes the eight-unit drift contribution.
    assert confounded.difference == 11.0
    assert balanced.difference == 3.0
    assert sum(balanced.treatment) == sum(confounded.treatment) == 4


def test_cluster_uncertainty_when_readings_share_a_run_effect() -> None:
    # Given: shared run SD=8ms, independent reading noise SD=2ms.
    # When: a fixed bounded experiment is evaluated.
    result = design.cluster_experiment(16, 20)
    # Then: treating all readings as independent understates model uncertainty.
    assert result == design.cluster_experiment(16, 20)
    assert result.model_se == math.sqrt((64 + 4 / 16) / 20)
    assert result.naive_se < result.run_se
    assert result.run_se == pytest.approx(math.sqrt(variance(result.run_means) / 20))
    assert len(result.readings) == 320


def test_independent_runs_when_readings_per_run_is_one() -> None:
    # Given: one reading in each independent run.
    # When: uncertainty is summarized.
    result = design.cluster_experiment(1, 20)
    # Then: the naive and run-level formulas coincide.
    assert result.naive_se == result.run_se


@pytest.mark.parametrize(("readings", "runs"), [(0, 2), (65, 2), (1, 1), (1, 41)])
def test_cluster_budget_when_request_is_invalid(readings: int, runs: int) -> None:
    # Given: an invalid workload.
    # When/Then: bounded helpers reject it without simulation.
    with pytest.raises(ValueError, match="budget"):
        _ = design.cluster_experiment(readings, runs)


def test_cluster_maximum_when_controls_reach_their_limits() -> None:
    # Given: 40 runs with 64 readings each.
    # When: the largest offered experiment runs.
    result = design.cluster_experiment(64, 40)
    # Then: no more than 2560 readings are retained.
    assert len(result.readings) == 2560


def test_design_lesson_when_run_as_a_script() -> None:
    # Given: the real eligibility lesson.
    lesson = Path(__file__).parents[1] / "examples/07-summary-and-eligibility.py"
    # When: the notebook evaluates its default controls.
    result = run_standalone_notebook(lesson)
    # Then: design evidence supplements, rather than replaces, eligibility.
    assert result.returncode == 0, result.stderr
    assert "Rejected evidence: eligible=false, reason=gap_too_large" in result.stdout
    assert "confounded_difference=11; balanced_difference=3" in result.stdout
