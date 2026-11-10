"""Typed lesson boundary and backwards-compatible runtime helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from examples._evidence import (
    RawEvidence,
    ReportEvidence,
    SummaryEvidence,
    parse_raw_evidence,
    parse_report_evidence,
    parse_summary_evidence,
)
from examples._runtime import (
    FixtureServerCleanupError,
    FixtureServerStartupError,
    FixtureServerStartupReason,
    LocalCommandTimeoutError,
    example_workspace,
    mock_prometheus_endpoint,
    perfcheck_executable,
    run_local_command,
    sanitized_environment,
)

__all__ = (
    "COMPARE_COHORT",
    "FAILURE_COHORT",
    "CollectRequest",
    "CompareRequest",
    "FixtureServerCleanupError",
    "FixtureServerStartupError",
    "FixtureServerStartupReason",
    "LessonContext",
    "LessonRun",
    "LocalCommandTimeoutError",
    "RawEvidence",
    "ReportEvidence",
    "SummaryEvidence",
    "SummaryRequest",
    "collect_arguments",
    "compare_arguments",
    "example_workspace",
    "lesson_context",
    "mock_prometheus_endpoint",
    "parse_raw_evidence",
    "parse_report_evidence",
    "parse_summary_evidence",
    "perfcheck_executable",
    "run_local_command",
    "sanitized_environment",
    "summarize_arguments",
)


@dataclass(frozen=True, slots=True)
class LessonContext:
    """Stable local resources shared by executable lessons."""

    repository_root: Path
    policy_path: Path
    fixture_path: Path
    executable: Path


@dataclass(frozen=True, slots=True)
class LessonRun:
    """One deterministic collection interval used by a lesson cohort."""

    run_id: str
    day: str

    @property
    def start(self) -> str:
        """Return the deterministic UTC start timestamp."""
        return f"{self.day}T10:00:00Z"

    @property
    def end(self) -> str:
        """Return the deterministic UTC end timestamp."""
        return f"{self.day}T10:10:00Z"


@dataclass(frozen=True, slots=True)
class CollectRequest:
    """Inputs for one public collect invocation."""

    endpoint: str
    run: LessonRun
    output_path: Path


@dataclass(frozen=True, slots=True)
class SummaryRequest:
    """Inputs for one public summarize invocation."""

    raw_path: Path
    output_path: Path


@dataclass(frozen=True, slots=True)
class CompareRequest:
    """Inputs for one public compare invocation."""

    current_paths: tuple[Path, ...]
    baseline_paths: tuple[Path, ...]
    report_json_path: Path
    report_markdown_path: Path
    seed: int
    resamples: int


COMPARE_COHORT: Final = (
    LessonRun("lesson-baseline-1", "2026-07-01"),
    LessonRun("lesson-baseline-2", "2026-07-02"),
    LessonRun("lesson-current-1", "2026-07-03"),
    LessonRun("lesson-current-2", "2026-07-04"),
)
FAILURE_COHORT: Final = (
    LessonRun("failure-baseline-1", "2026-07-11"),
    LessonRun("failure-baseline-2", "2026-07-12"),
    LessonRun("failure-current-1", "2026-07-13"),
    LessonRun("failure-current-2", "2026-07-14"),
)


def lesson_context() -> LessonContext:
    """Create the local paths shared by the five lessons."""
    repository_root = Path(__file__).resolve().parents[1]
    return LessonContext(
        repository_root=repository_root,
        policy_path=repository_root / "tests/fixtures/policy-pass.json",
        fixture_path=repository_root / "examples/fixtures/prometheus-matrix.json",
        executable=perfcheck_executable(),
    )


def collect_arguments(
    context: LessonContext, request: CollectRequest
) -> tuple[str, ...]:
    """Build the public collect command for one deterministic lesson run."""
    return (
        str(context.executable),
        "collect",
        "--policy",
        str(context.policy_path),
        "--prometheus-url",
        request.endpoint,
        "--run-id",
        request.run.run_id,
        "--start",
        request.run.start,
        "--end",
        request.run.end,
        "--out",
        str(request.output_path),
    )


def summarize_arguments(
    context: LessonContext, request: SummaryRequest
) -> tuple[str, ...]:
    """Build the public summarize command for one lesson raw run."""
    return (
        str(context.executable),
        "summarize",
        "--policy",
        str(context.policy_path),
        "--run",
        str(request.raw_path),
        "--out",
        str(request.output_path),
    )


def compare_arguments(
    context: LessonContext, request: CompareRequest
) -> tuple[str, ...]:
    """Build the public compare command for fixed deterministic cohorts."""
    current_arguments = tuple(
        argument
        for path in request.current_paths
        for argument in ("--current", str(path))
    )
    baseline_arguments = tuple(
        argument
        for path in request.baseline_paths
        for argument in ("--baseline", str(path))
    )
    return (
        str(context.executable),
        "compare",
        "--policy",
        str(context.policy_path),
        *current_arguments,
        *baseline_arguments,
        "--report-json",
        str(request.report_json_path),
        "--report-md",
        str(request.report_markdown_path),
        "--seed",
        str(request.seed),
        "--resamples",
        str(request.resamples),
    )
