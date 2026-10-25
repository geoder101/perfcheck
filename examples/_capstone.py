"""Run one isolated teaching scenario through the public console executable."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Final, assert_never

from examples._support import (
    FAILURE_COHORT,
    CollectRequest,
    CompareRequest,
    SummaryRequest,
    collect_arguments,
    compare_arguments,
    example_workspace,
    lesson_context,
    mock_prometheus_endpoint,
    run_local_command,
    summarize_arguments,
)
from examples.fixtures.mock_prometheus import PrometheusFixture

if TYPE_CHECKING:
    from pathlib import Path
    from subprocess import CompletedProcess

_PASS_LABEL: Final = "pass"


class Scenario(StrEnum):
    """Exactly one workflow selected by the learner."""

    PASS = _PASS_LABEL
    REGRESSION = "regression"
    ADVISORY_REFERENCE = "advisory-reference"


@dataclass(frozen=True, slots=True)
class CapstoneReceipt:
    """Actual child outcomes and artifact bytes retained after workspace cleanup."""

    scenario: Scenario
    workspace: Path
    commands: tuple[tuple[str, ...], ...]
    stage_statuses: tuple[int, ...]
    comparison_status: int
    overwrite_status: int
    overwrite_context: str
    raw_artifacts: tuple[bytes, ...]
    summary_artifacts: tuple[bytes, ...]
    report_json: bytes
    report_markdown: str


def run_capstone(scenario: Scenario = Scenario.PASS) -> CapstoneReceipt:
    """Collect, summarize, compare, and probe overwrite for only the chosen scenario."""
    context = lesson_context()
    match scenario:
        case Scenario.PASS:
            policy_name, run_count = "policy-pass.json", 4
        case Scenario.REGRESSION:
            policy_name, run_count = "policy-fail.json", 4
        case Scenario.ADVISORY_REFERENCE:
            policy_name, run_count = "policy-inconclusive.json", 3
        case unreachable:
            assert_never(unreachable)
    context = replace(
        context, policy_path=context.repository_root / "tests/fixtures" / policy_name
    )
    with example_workspace() as workspace:
        fixture_path = context.fixture_path
        if run_count == 3:
            fixture = PrometheusFixture.model_validate_json(fixture_path.read_bytes())
            reference_fixture = PrometheusFixture(
                sample_count=fixture.sample_count,
                queries={**fixture.queries, "inconclusive_metric": (10.0, 10.0, 20.0)},
            )
            fixture_path = workspace / "reference-matrix.json"
            _ = fixture_path.write_text(reference_fixture.model_dump_json())
        commands: list[tuple[str, ...]] = []
        stage_statuses: list[int] = []
        raw_artifacts: list[bytes] = []
        summary_artifacts: list[bytes] = []
        summary_paths: list[Path] = []
        with mock_prometheus_endpoint(fixture_path) as endpoint:
            for run in FAILURE_COHORT[:run_count]:
                raw_path = workspace / f"{run.run_id}.json"
                summary_path = workspace / f"{run.run_id}.summary.json"
                for command in (
                    collect_arguments(context, CollectRequest(endpoint, run, raw_path)),
                    summarize_arguments(
                        context, SummaryRequest(raw_path, summary_path)
                    ),
                ):
                    result = run_local_command(command, cwd=workspace)
                    result.check_returncode()
                    commands.append(command)
                    stage_statuses.append(result.returncode)
                raw_artifacts.append(raw_path.read_bytes())
                summary_artifacts.append(summary_path.read_bytes())
                summary_paths.append(summary_path)
        compare_command = compare_arguments(
            context,
            CompareRequest(
                current_paths=tuple(summary_paths[2:]),
                baseline_paths=tuple(summary_paths[:2]),
                report_json_path=workspace / "comparison.json",
                report_markdown_path=workspace / "comparison.md",
                seed=20260705,
                resamples=1000,
            ),
        )
        if run_count == 3:
            # The shared builder is unchanged; reference forbids these two overrides.
            compare_command = compare_command[:-4]
        comparison: CompletedProcess[str] = run_local_command(
            compare_command, cwd=workspace
        )
        commands.append(compare_command)
        report_json = (workspace / "comparison.json").read_bytes()
        report_markdown = (workspace / "comparison.md").read_text(encoding="utf-8")
        overwrite = run_local_command(compare_command, cwd=workspace)
        commands.append(compare_command)
        return CapstoneReceipt(
            scenario=scenario,
            workspace=workspace,
            commands=tuple(commands),
            stage_statuses=tuple(stage_statuses),
            comparison_status=comparison.returncode,
            overwrite_status=overwrite.returncode,
            overwrite_context=overwrite.stderr.strip(),
            raw_artifacts=tuple(raw_artifacts),
            summary_artifacts=tuple(summary_artifacts),
            report_json=report_json,
            report_markdown=report_markdown,
        )
