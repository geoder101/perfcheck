"""Known-sigma normal tests, analytic power and explicit null-model simulations."""

import math
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np

from examples._inference import MAX_REPETITIONS, MAX_SAMPLE_SIZE, MAX_SIGMA, FloatVector


def normal_cdf(value: float) -> float:
    """Evaluate the lower standard-normal tail without cancellation in that tail."""
    return 0.5 * math.erfc(-value / math.sqrt(2))


@dataclass(frozen=True, slots=True)
class ZResult:
    """A lower-tailed known-sigma contrast, not a perfcheck verdict."""

    standard_error: float
    z: float
    p: float


def known_sigma_z(observed_mean: float) -> ZResult:
    """Use the lesson's prespecified N(100, 10 squared), n=25 model."""
    se = 10 / math.sqrt(25)
    z = (observed_mean - 100) / se
    return ZResult(se, z, normal_cdf(z))


@dataclass(frozen=True, slots=True)
class PowerExperiment:
    """Right-tailed IID normal mean design, known sigma, prespecified alpha."""

    effect: float = 4.0
    n: int = 25
    sigma: float = 10.0
    alpha: float = 0.05

    def __post_init__(self) -> None:
        if not 1 <= self.n <= MAX_SAMPLE_SIZE or not 0 < self.sigma <= MAX_SIGMA:
            message = "n must be 1..500; sigma must be positive and at most 100"
            raise ValueError(message)
        if not 0 < self.alpha < 1 or not math.isfinite(self.effect):
            message = "alpha must be in (0,1); effect must be finite"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class PowerResult:
    """Rejection boundary in mean-shift units and alternative error probabilities."""

    standard_error: float
    critical_shift: float
    beta: float
    power: float


def analytic_power(inputs: PowerExperiment) -> PowerResult:
    """Integrate the alternative distribution above the fixed null critical mean."""
    se = inputs.sigma / math.sqrt(inputs.n)
    critical = NormalDist().inv_cdf(1 - inputs.alpha) * se
    beta = normal_cdf((critical - inputs.effect) / se)
    power = normal_cdf((inputs.effect - critical) / se)
    return PowerResult(se, critical, beta, power)


@dataclass(frozen=True, slots=True)
class NullExperiment:
    """A bounded comparison of valid, discrete, and misspecified null p-values."""

    repetitions: int = 128
    seed: int = 42

    def __post_init__(self) -> None:
        if not 1 <= self.repetitions <= MAX_REPETITIONS or self.seed < 0:
            message = "repetitions must be 1..512; seed must be nonnegative"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class NullPvalues:
    """Matched normal draws expose a coarse valid p-value and wrong sigma model."""

    continuous: tuple[float, ...]
    discrete: tuple[float, ...]
    violated: tuple[float, ...]


def null_pvalues(inputs: NullExperiment) -> NullPvalues:
    """Use right tails of Z~N(0,1); discrete rounds up, violated uses 2Z."""
    rng = np.random.Generator(np.random.PCG64(inputs.seed))
    draws: FloatVector = rng.normal(size=inputs.repetitions)
    continuous = tuple(normal_cdf(-float(z)) for z in draws)
    return NullPvalues(
        continuous=continuous,
        discrete=tuple(math.ceil(p * 20) / 20 for p in continuous),
        violated=tuple(normal_cdf(-2 * float(z)) for z in draws),
    )
