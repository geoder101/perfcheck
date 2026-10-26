"""Independent normal-family teaching experiments; no production policy engine."""

import math
from dataclasses import dataclass
from typing import Final, Literal, assert_never

import numpy as np

from examples._inference import MAX_REPETITIONS, FloatVector
from examples._power import normal_cdf

type Method = Literal["none", "Bonferroni", "Holm", "BH"]
MAX_FAMILY_SIZE: Final = 40


def independent_fwer(size: int, alpha: float) -> float:
    """Probability of at least one rejection for independent continuous true nulls."""
    return 1 - (1 - alpha) ** size


def adjust_pvalues(values: tuple[float, ...], method: Method) -> tuple[float, ...]:
    """Adjust one full family, retaining original indices and step monotonicity."""
    size = len(values)
    order = sorted(range(size), key=values.__getitem__)
    adjusted = [0.0] * size
    match method:
        case "none":
            return values
        case "Bonferroni":
            return tuple(min(1.0, size * p) for p in values)
        case "Holm":
            previous = 0.0
            for rank, index in enumerate(order):
                previous = min(1.0, max(previous, (size - rank) * values[index]))
                adjusted[index] = previous
        case "BH":
            previous = 1.0
            for rank in range(size - 1, -1, -1):
                index = order[rank]
                previous = min(previous, size * values[index] / (rank + 1))
                adjusted[index] = previous
        case _:
            assert_never(method)
    return tuple(adjusted)


@dataclass(frozen=True, slots=True)
class FamilyExperiment:
    """IID unit-variance z statistics: true mean zero or false mean three."""

    size: int = 20
    true_nulls: int = 15
    alpha: float = 0.05
    method: Method = "none"
    repetitions: int = 128
    seed: int = 42

    def __post_init__(self) -> None:
        if (
            not 1 <= self.size <= MAX_FAMILY_SIZE
            or not 0 <= self.true_nulls <= self.size
        ):
            message = "size must be 1..40; true_nulls must be 0..size"
            raise ValueError(message)
        if not 1 <= self.repetitions <= MAX_REPETITIONS or self.seed < 0:
            message = "repetitions must be 1..512; seed must be nonnegative"
            raise ValueError(message)
        if not 0 < self.alpha < 1:
            message = "alpha must be in (0,1)"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class FamilyResult:
    """Truth is known only because this is a synthetic experiment."""

    pvalues: tuple[float, ...]
    adjusted: tuple[float, ...]
    rejected: tuple[bool, ...]
    false_rejections: int
    fdp: float


@dataclass(frozen=True, slots=True)
class FamilySimulation:
    """Empirical FWER and mean FDP (an FDR estimate), not universal guarantees."""

    families: tuple[FamilyResult, ...]
    fwer: float
    mean_fdp: float
    fwer_mc_se: float
    fdr_mc_se: float


def simulate_families(inputs: FamilyExperiment) -> FamilySimulation:
    """Generate independent z tests once, then adjust each entire family."""
    rng = np.random.Generator(np.random.PCG64(inputs.seed))
    means = np.asarray(
        (0.0,) * inputs.true_nulls + (3.0,) * (inputs.size - inputs.true_nulls),
        dtype=np.float64,
    )
    rows: list[FamilyResult] = []
    for _ in range(inputs.repetitions):
        zvalues: FloatVector = rng.normal(means, 1.0)
        pvalues = tuple(normal_cdf(-float(z)) for z in zvalues)
        adjusted = adjust_pvalues(pvalues, inputs.method)
        rejected = tuple(p <= inputs.alpha for p in adjusted)
        false_rejections = sum(rejected[: inputs.true_nulls])
        rows.append(
            FamilyResult(
                pvalues,
                adjusted,
                rejected,
                false_rejections,
                false_rejections / max(1, sum(rejected)),
            )
        )
    fwer = sum(row.false_rejections > 0 for row in rows) / inputs.repetitions
    fdr = math.fsum(row.fdp for row in rows) / inputs.repetitions
    fdr_se = (
        math.sqrt(
            math.fsum((row.fdp - fdr) ** 2 for row in rows)
            / (inputs.repetitions - 1)
            / inputs.repetitions
        )
        if inputs.repetitions > 1
        else 0.0
    )
    return FamilySimulation(
        tuple(rows),
        fwer,
        fdr,
        math.sqrt(fwer * (1 - fwer) / inputs.repetitions),
        fdr_se,
    )
