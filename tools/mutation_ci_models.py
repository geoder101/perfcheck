"""Strict file boundaries for manual mutation CI provenance."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

type Sha = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
type Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Boundary(BaseModel):
    """Strict immutable file boundary for CI-only metadata."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        allow_inf_nan=False,
    )


class Start(Boundary):
    """Actual checkout identity captured before the mutation command."""

    tested_sha: Sha
    expected_sha: Sha
    event: Literal["workflow_dispatch"]
    run_id: Annotated[str, Field(pattern=r"^[0-9]+$")]
    run_attempt: Annotated[str, Field(pattern=r"^[0-9]+$")]
    started_ns: Annotated[int, Field(gt=0)]
    source_sha256: Digest
    lock_sha256: Digest


class Status(Boundary):
    """The trusted runner's complete, invalid or interrupted result."""

    status: Literal["complete", "invalid", "incomplete"]
    detail: str
    elapsed_seconds: Annotated[float, Field(ge=0)]
    source_unchanged: bool


class Manifest(BaseModel):
    """Required policy fields; retain the full original manifest separately."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True)
    target: Literal["src/perfcheck/regression_aggregation.py"]
    tests: Literal["tests/test_suite_aggregation.py"]
    workers: Literal[1]
    child_budget_seconds: Literal[600]
    source_sha256: Digest
    lock_sha256: Digest
