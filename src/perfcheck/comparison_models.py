"""Strict version-one comparison and report artifact models."""

from typing import Literal, Self

from pydantic import Field, model_validator

from perfcheck.errors import ArtifactSchemaCode, ArtifactSchemaError
from perfcheck.model_types import (
    V1_ALGORITHM_MANIFEST,
    AlgorithmManifest,
    ComparisonMethod,
    Direction,
    FiniteFloat,
    MetricIdentifier,
    NonBlankText,
    NonNegativeInteger,
    PolicySha256,
    PositiveInteger,
    Status,
    StrictModel,
)
from perfcheck.summary_models import SummaryArtifact


class ComparisonCohorts(StrictModel):
    """Validated summary cohorts with globally unique source identities."""

    current: tuple[SummaryArtifact, ...]
    baseline: tuple[SummaryArtifact, ...]

    @model_validator(mode="after")
    def validate_unique_sources(self) -> Self:
        """Reject duplicated source IDs or source content across cohorts."""
        summaries = self.current + self.baseline
        source_ids = tuple(summary.source_run_id for summary in summaries)
        source_hashes = tuple(summary.source_content_sha256 for summary in summaries)
        if len(source_ids) != len(set(source_ids)):
            raise ArtifactSchemaError(ArtifactSchemaCode.DUPLICATE_SOURCE_RUN)
        if len(source_hashes) != len(set(source_hashes)):
            raise ArtifactSchemaError(ArtifactSchemaCode.DUPLICATE_SOURCE_CONTENT)
        return self


class ComparisonResult(StrictModel):
    """One metric's persisted comparison outcome and method diagnostics."""

    metric_id: MetricIdentifier
    direction: Direction
    status: Status
    method: ComparisonMethod
    reference_anomaly: bool | None = None
    effective_seed: NonNegativeInteger | None = None
    requested_resamples: PositiveInteger | None = None
    effective_resamples: PositiveInteger | None = None
    observed_effect: FiniteFloat | None = None
    lower_decision_bound: FiniteFloat | None = None
    reason: NonBlankText | None = None

    @model_validator(mode="after")
    def validate_method_options(self) -> Self:
        """Keep cohort-bootstrap options out of baseline-reference results."""
        baseline_is_valid = (
            self.method is ComparisonMethod.BASELINE_REFERENCE
            and self.effective_seed is None
            and self.requested_resamples is None
            and self.effective_resamples is None
            and self.lower_decision_bound is None
            and self.reference_anomaly is not None
        )
        bootstrap_is_valid = (
            self.method is ComparisonMethod.COHORT_BOOTSTRAP
            and self.effective_seed is not None
            and self.requested_resamples is not None
            and self.effective_resamples is not None
            and self.reference_anomaly is None
        )
        if not (baseline_is_valid or bootstrap_is_valid):
            raise ArtifactSchemaError(ArtifactSchemaCode.INVALID_COMPARISON_OPTIONS)
        return self


class ComparisonReport(StrictModel):
    """Deterministic report data with no wall-clock or local-path fields."""

    schema_version: Literal[1] = 1
    policy_sha256: PolicySha256
    algorithm_manifest: AlgorithmManifest = V1_ALGORITHM_MANIFEST
    suite_status: Status
    cohorts: ComparisonCohorts
    metric_results: tuple[ComparisonResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        """Require reports to retain one policy and one result per metric."""
        summaries = self.cohorts.current + self.cohorts.baseline
        if any(summary.policy_sha256 != self.policy_sha256 for summary in summaries):
            raise ArtifactSchemaError(ArtifactSchemaCode.POLICY_HASH_MISMATCH)
        metric_ids = tuple(result.metric_id for result in self.metric_results)
        if len(metric_ids) != len(set(metric_ids)):
            raise ArtifactSchemaError(ArtifactSchemaCode.DUPLICATE_REPORT_METRIC)
        return self
