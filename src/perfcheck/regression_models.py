"""Immutable values shared across regression evaluation responsibilities."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from perfcheck.bootstrap import (
        BaselineReferenceResult,
        CohortBootstrapOptions,
        CohortBootstrapResult,
        RunValue,
    )
    from perfcheck.model_types import ComparisonMethod, Direction, Status
    from perfcheck.policy import ComparisonInput
    from perfcheck.policy_models import MetricPolicy, SuitePolicy


class Cohort(StrEnum):
    """The source cohort of a metric exclusion."""

    CURRENT = "current"
    BASELINE = "baseline"


@dataclass(frozen=True, slots=True)
class MetricExclusion:
    """One run withheld from one metric decision with its exact reason."""

    cohort: Cohort
    source_run_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class MetricOutcome:
    """One metric's verdict, selected evidence, and filtered run provenance."""

    metric_id: str
    direction: Direction
    enabled: bool
    status: Status
    method: ComparisonMethod | None
    evidence: BaselineReferenceResult | CohortBootstrapResult | None
    reason: str | None
    exclusions: tuple[MetricExclusion, ...]


@dataclass(frozen=True, slots=True)
class RegressionOutcome:
    """Deterministic suite verdict assembled from its policy metric outcomes."""

    status: Status
    metrics: tuple[MetricOutcome, ...]


@dataclass(frozen=True, slots=True)
class MetricEvaluationInput:
    """All policy inputs needed to evaluate one metric."""

    policy: SuitePolicy
    metric: MetricPolicy
    cohort_options: CohortBootstrapOptions | None


@dataclass(frozen=True, slots=True)
class EligibleMetricCohort:
    """Usable scalar inputs and exclusions for one metric in one cohort."""

    run_values: tuple[RunValue, ...]
    comparison_inputs: tuple[ComparisonInput, ...]
    exclusions: tuple[MetricExclusion, ...]
