"""Artifact discriminators over strict run and summary models."""

from typing import Annotated, Final

from pydantic import Field, TypeAdapter

from perfcheck.run_models import RunArtifact
from perfcheck.summary_models import SummaryArtifact

type Artifact = Annotated[
    RunArtifact | SummaryArtifact, Field(discriminator="artifact_type")
]
ARTIFACT_ADAPTER: Final[TypeAdapter[RunArtifact | SummaryArtifact]] = TypeAdapter[
    RunArtifact | SummaryArtifact
](Artifact)
