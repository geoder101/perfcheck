"""Bounded independent-run experiments for experimental-design teaching."""

import math
from dataclasses import dataclass
from statistics import fmean, variance
from typing import Final

import numpy as np

from examples._probability import PlotSeries, plot_svg

MAX_READINGS: Final = 64
MAX_RUNS: Final = 40
MIN_RUNS: Final = 2


@dataclass(frozen=True, slots=True)
class ClusterExperiment:
    """Run-level versus pseudo-independent uncertainty in milliseconds."""

    readings: tuple[float, ...]
    run_means: tuple[float, ...]
    naive_se: float
    run_se: float
    model_se: float


def cluster_experiment(readings_per_run: int, runs: int) -> ClusterExperiment:
    """Generate shared Normal(0,64) run effects plus Normal(0,4) reading noise."""
    if not 1 <= readings_per_run <= MAX_READINGS or not MIN_RUNS <= runs <= MAX_RUNS:
        message = "cluster budget requires 1..64 readings/run and 2..40 runs"
        raise ValueError(message)
    generator = np.random.default_rng(701)
    offsets = tuple(generator.normal(0, 8) for _ in range(runs))
    observations = tuple(
        tuple(100 + offset + generator.normal(0, 2) for _ in range(readings_per_run))
        for offset in offsets
    )
    readings = tuple(value for row in observations for value in row)
    run_means = tuple(fmean(row) for row in observations)
    return ClusterExperiment(
        readings,
        run_means,
        math.sqrt(variance(readings) / len(readings)),
        math.sqrt(variance(run_means) / runs),
        math.sqrt((64 + 4 / readings_per_run) / runs),
    )


@dataclass(frozen=True, slots=True)
class ScheduleExperiment:
    """Eight deterministic scheduled runs and their raw treatment contrast."""

    treatment: tuple[int, ...]
    outcomes: tuple[float, ...]
    difference: float


def schedule_experiment(balanced: bool) -> ScheduleExperiment:
    """Balance mean time, or confound treatment with four later time slots."""
    treatment = (0, 1, 1, 0, 1, 0, 0, 1) if balanced else (0, 0, 0, 0, 1, 1, 1, 1)
    outcomes = tuple(100.0 + 2 * time + 3 * arm for time, arm in enumerate(treatment))
    control = tuple(y for y, arm in zip(outcomes, treatment, strict=True) if not arm)
    treated = tuple(y for y, arm in zip(outcomes, treatment, strict=True) if arm)
    return ScheduleExperiment(treatment, outcomes, fmean(treated) - fmean(control))


def cluster_plot(runs: int) -> str:
    """Contrast model standard errors; finite sample estimates need not be monotone."""
    if not MIN_RUNS <= runs <= MAX_RUNS:
        message = "cluster plot budget requires 2..40 independent runs"
        raise ValueError(message)
    return plot_svg(
        (
            "Uncertainty: readings are not runs",
            "Readings per run (count)",
            "Standard error (ms)",
        ),
        (
            PlotSeries(
                "solid: model SE, independent runs",
                tuple((float(m), math.sqrt((64 + 4 / m) / runs)) for m in range(1, 65)),
            ),
            PlotSeries(
                "dashed: false independence, model SE",
                tuple((float(m), math.sqrt(68 / (runs * m))) for m in range(1, 65)),
                dashed=True,
            ),
        ),
    )


def schedule_plot(schedule: ScheduleExperiment) -> str:
    """Distinguish treatment arms by solid/dashed series, not by color alone."""
    return plot_svg(
        ("Y=100+2*time+3*treatment", "Scheduled time slot (index)", "Outcome (ms)"),
        tuple(
            PlotSeries(
                label,
                tuple(
                    (float(t), y)
                    for t, (arm, y) in enumerate(
                        zip(schedule.treatment, schedule.outcomes, strict=True)
                    )
                    if arm == group
                ),
                dashed=bool(group),
            )
            for group, label in enumerate(("solid: control", "dashed: treatment"))
        ),
    )
