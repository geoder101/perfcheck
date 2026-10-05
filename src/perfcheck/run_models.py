"""Strict version-one raw run artifact model."""

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from perfcheck.artifact_validation import contains_secret
from perfcheck.collection_models import MetricCollectionRecord, SourceInterval
from perfcheck.errors import ArtifactSchemaCode, ArtifactSchemaError
from perfcheck.model_types import (
    ArtifactKind,
    ArtifactSha256,
    NonBlankText,
    PolicySha256,
    RunIdentifier,
    StrictModel,
    SuiteIdentifier,
)
from perfcheck.policy_models import SuitePolicy


class RunMetadata(StrictModel):
    """Portable run context without local paths or invocation state."""

    test_name: NonBlankText
    git_sha: NonBlankText
    environment: NonBlankText
    scenario: NonBlankText
    target_topology: NonBlankText

    @field_validator(
        "test_name", "git_sha", "environment", "scenario", "target_topology"
    )
    @classmethod
    def reject_secret_text(cls, value: str) -> str:
        """Prevent request credentials entering persisted run metadata."""
        if contains_secret(value):
            raise ArtifactSchemaError(ArtifactSchemaCode.CREDENTIAL_METADATA)
        return value


class RunArtifact(StrictModel):
    """A complete validated raw collection artifact for one source interval."""

    artifact_type: Literal[ArtifactKind.RUN] = ArtifactKind.RUN
    schema_version: Literal[1] = 1
    content_sha256: ArtifactSha256
    run_id: RunIdentifier
    suite_id: SuiteIdentifier
    source_interval: SourceInterval
    policy_sha256: PolicySha256
    policy_snapshot: SuitePolicy
    metadata: RunMetadata
    metric_records: tuple[MetricCollectionRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        """Retain every exact policy metric under its immutable snapshot."""
        self._validate_identity()
        self._validate_metric_records()
        return self

    def _validate_identity(self) -> None:
        if self.policy_sha256 != self.policy_snapshot.policy_sha256:
            raise ArtifactSchemaError(ArtifactSchemaCode.POLICY_HASH_MISMATCH)
        if self.suite_id != self.policy_snapshot.suite_id:
            raise ArtifactSchemaError(ArtifactSchemaCode.SUITE_MISMATCH)

    def _validate_metric_records(self) -> None:
        expected = {metric.metric_id: metric for metric in self.policy_snapshot.metrics}
        record_ids = tuple(record.metric_id for record in self.metric_records)
        if len(record_ids) != len(set(record_ids)):
            raise ArtifactSchemaError(ArtifactSchemaCode.DUPLICATE_METRIC_RECORD)
        if set(record_ids) != set(expected):
            raise ArtifactSchemaError(ArtifactSchemaCode.METRIC_SET_MISMATCH)
        for record in self.metric_records:
            if (
                record.provenance.start != self.source_interval.start
                or record.provenance.end != self.source_interval.end
            ):
                raise ArtifactSchemaError(
                    ArtifactSchemaCode.PROVENANCE_INTERVAL_MISMATCH
                )
            if record.series is not None:
                if record.series.metric_id != record.metric_id:
                    raise ArtifactSchemaError(ArtifactSchemaCode.SERIES_METRIC_MISMATCH)
                labels = tuple(label.name for label in record.series.labels)
                metric_policy = expected[record.metric_id]
                if labels != metric_policy.expected_label_names:
                    raise ArtifactSchemaError(ArtifactSchemaCode.LABEL_SET_MISMATCH)
                if (
                    record.provenance.query != metric_policy.query
                    or record.provenance.step_seconds != metric_policy.step_seconds
                ):
                    raise ArtifactSchemaError(
                        ArtifactSchemaCode.QUERY_PROVENANCE_MISMATCH
                    )
