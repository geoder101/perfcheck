"""Pure inference experiments; educational calculations, never product decisions."""

import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Final

import numpy as np

type FloatVector = np.ndarray[tuple[int], np.dtype[np.float64]]
MAX_REPETITIONS: Final = 512
MAX_ENABLED: Final = 20
MAX_SAMPLE_SIZE: Final = 500
MAX_SIGMA: Final = 100


@dataclass(frozen=True, slots=True)
class BootstrapExperiment:
    """Cohorts and policy settings for the transparent percentile demonstration."""

    baseline: tuple[float, ...] = (100.0, 99.0, 101.0, 100.0)
    current: tuple[float, ...] = (90.0, 89.0, 91.0, 90.0)
    higher_is_worse: bool = False
    enabled: int = 2
    seed: int = 20260808
    threshold: float = 3.0

    def __post_init__(self) -> None:
        if not 1 <= self.enabled <= MAX_ENABLED or self.seed < 0:
            message = "enabled must be 1..20; seed must be nonnegative"
            raise ValueError(message)
        if not self.current or not self.baseline:
            message = "both cohorts must be nonempty"
            raise ValueError(message)
        if not all(math.isfinite(x) for x in (*self.current, *self.baseline)):
            message = "cohorts must be finite"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class BootstrapDistribution:
    """Retain the actual distribution behind the one-sided bound."""

    draws: tuple[float, ...]
    effect: float
    lower: float
    verdict: str
    reference_effect: float
    reference_anomaly: bool


def bootstrap_experiment(inputs: BootstrapExperiment) -> BootstrapDistribution:
    """Use float64 PCG64 interleaved current-then-baseline draws and linear tails."""
    orientation = 1.0 if inputs.higher_is_worse else -1.0
    current: FloatVector = orientation * np.asarray(inputs.current, dtype=np.float64)
    baseline: FloatVector = orientation * np.asarray(inputs.baseline, dtype=np.float64)
    rng = np.random.Generator(np.random.PCG64(inputs.seed))
    draws = tuple(
        float(np.mean(current[rng.integers(0, len(current), size=len(current))]))
        - float(np.mean(baseline[rng.integers(0, len(baseline), size=len(baseline))]))
        for _ in range(max(1000, 2000 * inputs.enabled))
    )
    alpha = 0.05 / inputs.enabled
    lower = float(
        np.quantile(np.asarray(draws, dtype=np.float64), alpha, method="linear")
    )
    reference = orientation * inputs.current[0] - float(
        np.quantile(baseline, 1 - alpha, method="linear")
    )
    return BootstrapDistribution(
        draws=draws,
        effect=float(np.mean(current) - np.mean(baseline)),
        lower=lower,
        verdict="FAIL" if lower > inputs.threshold else "PASS",
        reference_effect=reference,
        reference_anomaly=reference > inputs.threshold,
    )


@dataclass(frozen=True, slots=True)
class CoverageExperiment:
    """Repeated IID N(100, sigma squared) sampling with known population sigma."""

    n: int = 25
    sigma: float = 10.0
    confidence: float = 0.95
    repetitions: int = 128
    seed: int = 42

    def __post_init__(self) -> None:
        if not 1 <= self.repetitions <= MAX_REPETITIONS:
            message = "repetitions must be 1..512"
            raise ValueError(message)
        if not 1 <= self.n <= MAX_SAMPLE_SIZE or not 0 < self.sigma <= MAX_SIGMA:
            message = "n must be 1..500; sigma must be positive and at most 100"
            raise ValueError(message)
        if not 0 < self.confidence < 1 or self.seed < 0:
            message = "confidence must be in (0,1); seed must be nonnegative"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    """One realized interval and its fixed-mean containment indicator."""

    lower: float
    upper: float
    contains: bool


@dataclass(frozen=True, slots=True)
class CoverageResult:
    """Empirical containment frequency with binomial Monte Carlo standard error."""

    intervals: tuple[ConfidenceInterval, ...]
    coverage: float
    mc_se: float


def coverage_experiment(inputs: CoverageExperiment) -> CoverageResult:
    """Simulate sample means directly from their exact normal sampling model."""
    se = inputs.sigma / math.sqrt(inputs.n)
    radius = NormalDist().inv_cdf((1 + inputs.confidence) / 2) * se
    rng = np.random.Generator(np.random.PCG64(inputs.seed))
    means: FloatVector = rng.normal(100.0, se, size=inputs.repetitions)
    intervals = tuple(
        ConfidenceInterval(
            float(m - radius), float(m + radius), bool(abs(m - 100) <= radius)
        )
        for m in means
    )
    coverage = sum(row.contains for row in intervals) / inputs.repetitions
    return CoverageResult(
        intervals, coverage, math.sqrt(coverage * (1 - coverage) / inputs.repetitions)
    )
