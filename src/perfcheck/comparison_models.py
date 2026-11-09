"""Strict version-one comparison artifact models."""

from typing import Self

from pydantic import model_validator

from perfcheck.errors import ArtifactSchemaCode, ArtifactSchemaError
from perfcheck.model_types import StrictModel
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
