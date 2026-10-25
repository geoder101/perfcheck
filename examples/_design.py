"""Bounded independent-run experiments for experimental-design teaching."""

import math
from dataclasses import dataclass
from statistics import fmean, variance

import numpy as np


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
    if not 1 <= readings_per_run <= 64 or not 2 <= runs <= 40:
        message = "cluster budget requires 1..64 readings/run and 2..40 runs"
        raise ValueError(message)
    generator = np.random.default_rng(701)
    offsets = generator.normal(0, 8, (runs, 1))
    noise = generator.normal(0, 2, (runs, readings_per_run))
    observations = 100 + offsets + noise
    readings = tuple(float(value) for value in observations.flat)
    run_means = tuple(float(value) for value in np.mean(observations, axis=1))
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
