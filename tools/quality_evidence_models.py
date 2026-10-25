"""Validated boundaries for CI coverage provenance and coverage.py reports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, ClassVar, Literal, override

from pydantic import BaseModel, ConfigDict, Field

type Sha = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
type Count = Annotated[int, Field(ge=0)]
type Label = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[^\r\n`]+$")]


@dataclass(frozen=True, slots=True)
class EvidenceError(Exception):
    """A fixed diagnostic that never exposes paths or environment data."""

    @override
    def __str__(self) -> str:
        """Describe evidence rejection without including boundary inputs."""
        return "coverage evidence validation failed"


def require(condition: bool) -> None:
    """Reject an invalid evidence contract with a secret-free typed error."""
    if not condition:
        raise EvidenceError


class Outcome(StrEnum):
    """The original GitHub step outcome, not its subsequent job conclusion."""

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class Boundary(BaseModel):
    """Immutable strict evidence boundary, independent of product schemas."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        strict=True, frozen=True, extra="forbid", allow_inf_nan=False
    )


class RunStart(Boundary):
    """Current invocation identity captured before the coverage gate."""

    started_ns: Annotated[int, Field(gt=0)]
    tested_sha: Sha
    expected_sha: Sha | None
    pr_head_sha: Sha | None
    event: Label
    ref: Label
    run_id: Annotated[str, Field(pattern=r"^[0-9]+$")]
    run_attempt: Annotated[str, Field(pattern=r"^[0-9]+$")]
    dirty: bool


class Totals(BaseModel):
    """Known coverage.py totals; unrelated upstream fields are deliberately ignored."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        strict=True, frozen=True, extra="ignore", allow_inf_nan=False
    )
    covered_lines: Count
    num_statements: Count
    missing_lines: Count
    excluded_lines: Count
    num_branches: Count
    covered_branches: Count
    missing_branches: Count
    percent_covered: Annotated[float, Field(ge=0, le=100)]

    @property
    def counts(self) -> tuple[int, ...]:
        """Expose only integer counts for exact per-file reconciliation."""
        return (
            self.covered_lines,
            self.num_statements,
            self.missing_lines,
            self.excluded_lines,
            self.num_branches,
            self.covered_branches,
            self.missing_branches,
        )

    @property
    def combined_percent(self) -> float:
        """Use exact combined counts, not rounded text or averaged percentages."""
        return (
            100
            * (self.covered_lines + self.covered_branches)
            / (self.num_statements + self.num_branches)
        )


class ReportMeta(BaseModel):
    """Required measurement mode and timestamp from coverage.py JSON."""

    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True, extra="ignore")
    branch_coverage: Literal[True]
    timestamp: str
    version: str


class FileReport(BaseModel):
    """Per-file counts used to reconcile aggregate totals."""

    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True, extra="ignore")
    summary: Totals


class CoverageReport(BaseModel):
    """Parse coverage.py JSON at its file boundary, without untyped values."""

    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True, extra="ignore")
    meta: ReportMeta
    totals: Totals
    files: dict[str, FileReport]


class Provenance(Boundary):
    """Exported internal CI evidence, never an application artifact schema."""

    tested_sha: Sha
    observed_export_sha: Sha
    pr_head_sha: Sha | None
    expected_sha: Sha | None
    event: Label
    ref: Label
    run_id: str
    run_attempt: str
    dirty: bool
    started_ns: int
    finished_ns: int
    gate_outcome: Outcome
    availability: Literal["complete", "partial", "unavailable"]
    reason: str | None
    totals: Totals | None
    versions: dict[str, str]
    command: Literal["just coverage-check"] = "just coverage-check"
    selection: str = "standard suite; excludes tests/test_examples{,_check}.py"
    scope: str = "src/perfcheck; statements and branches; subprocess patch enabled"
    threshold: Literal[99] = 99
    threshold_semantics: str = (
        "coverage.py fail-under precision; gate outcome authoritative"
    )
    exclusions: str = "coverage.py defaults plus audited case _ / assert_never guards"
