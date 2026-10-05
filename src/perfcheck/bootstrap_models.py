"""Public bootstrap value types and fixed defaults."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Final, override

from perfcheck.errors import PerfcheckError

if TYPE_CHECKING:
    from perfcheck.model_types import AlgorithmManifest, ComparisonMethod, Direction

_DEFAULT_SEED: Final = 42
_DEFAULT_REQUESTED_RESAMPLES: Final = 10_000


class BootstrapValidationCode(StrEnum):
    """Stable validation failures emitted by bootstrap input boundaries."""

    EMPTY_BASELINE = "baseline cohort must contain one or more run values"
    EMPTY_CURRENT = "current cohort must contain one or more run values"
    INVALID_ALPHA = "requested and effective alpha values are invalid"
    INVALID_ENABLED_METRIC_COUNT = "enabled metric count must be positive"
    INVALID_PRACTICAL_THRESHOLD = "practical threshold must be finite and nonnegative"
    INVALID_RESAMPLES = "requested resamples must be positive"
    INVALID_SEED = "bootstrap seed must be nonnegative"
    NONFINITE_INPUT = "run-level values must be finite"
    REFERENCE_OVERRIDE = "seed and resamples are invalid for baseline reference"
    REFERENCE_REQUIRES_ONE_CURRENT = "baseline reference requires one current run"


@dataclass(frozen=True, slots=True)
class BootstrapInputError(PerfcheckError):
    """A caller supplied values outside the fixed numerical contract."""

    code: BootstrapValidationCode
    exit_code: ClassVar[int] = 3

    @override
    def __str__(self) -> str:
        """Render the stable validation message for caller diagnostics."""
        return self.code


@dataclass(frozen=True, slots=True)
class RunValue:
    """One validated per-run statistic and its canonical source identifier."""

    source_run_id: str
    value: float


@dataclass(frozen=True, slots=True)
class MetricComparisonInput:
    """Comparable run-level inputs for one metric under a selected policy."""

    metric_id: str
    direction: Direction
    requested_alpha: float
    effective_alpha: float
    practical_threshold: float
    current: tuple[RunValue, ...]
    baseline: tuple[RunValue, ...]
    sample_size_warning: bool = False


@dataclass(frozen=True, slots=True)
class CohortBootstrapOptions:
    """Explicit cohort-bootstrap options including the fixed default seed."""

    seed: int = _DEFAULT_SEED
    requested_resamples: int = _DEFAULT_REQUESTED_RESAMPLES
    enabled_metric_count: int = 1


@dataclass(frozen=True, slots=True)
class ReferenceOptions:
    """Optional overrides rejected by the advisory baseline-reference method."""

    seed: int | None = None
    requested_resamples: int | None = None


DEFAULT_COHORT_OPTIONS: Final = CohortBootstrapOptions()
DEFAULT_REFERENCE_OPTIONS: Final = ReferenceOptions()


@dataclass(frozen=True, slots=True)
class ComparisonEvidence:
    """Shared immutable provenance retained by each comparison evidence variant."""

    metric_id: str
    direction: Direction
    method: ComparisonMethod
    algorithm_manifest: AlgorithmManifest
    requested_alpha: float
    effective_alpha: float
    current_sample_ids: tuple[str, ...]
    baseline_sample_ids: tuple[str, ...]
    current_sample_count: int
    baseline_sample_count: int
    sample_size_warning: bool


@dataclass(frozen=True, slots=True)
class CohortBootstrapResult(ComparisonEvidence):
    """Reproducible approximate percentile-bootstrap evidence for one metric."""

    observed_effect: float
    lower_decision_bound: float
    diagnostic_lower_bound: float
    diagnostic_upper_bound: float
    effective_seed: int
    requested_resamples: int
    effective_resamples: int


@dataclass(frozen=True, slots=True)
class BaselineReferenceResult(ComparisonEvidence):
    """Advisory reference evidence without a confidence interval."""

    reference_quantile: float
    reference_effect: float
    reference_anomaly: bool
    effective_seed: None
    requested_resamples: None
    effective_resamples: None
