from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

from tests.e2e.support import mock_prometheus_endpoint, perfcheck_executable

_ROOT: Final = Path(__file__).parents[2]
_PROMETHEUS_FIXTURE: Final = _ROOT / "tests/fixtures/prometheus/matrix.json"


@dataclass(frozen=True, slots=True)
class RunDay:
    run_id: str
    day: str


@dataclass(frozen=True, slots=True)
class WorkflowScenario:
    name: str
    policy_fixture: str
    runs: tuple[RunDay, ...]
    current_run_ids: tuple[str, ...]
    baseline_run_ids: tuple[str, ...]
    expected_exit: int


_SCENARIOS: Final = (
    WorkflowScenario(
        name="pass",
        policy_fixture="policy-pass.json",
        runs=(
            RunDay("baseline-1", "01"),
            RunDay("baseline-2", "02"),
            RunDay("current-1", "03"),
            RunDay("current-2", "04"),
        ),
        current_run_ids=("current-1", "current-2"),
        baseline_run_ids=("baseline-1", "baseline-2"),
        expected_exit=0,
    ),
    WorkflowScenario(
        name="fail",
        policy_fixture="policy-fail.json",
        runs=(
            RunDay("fail-baseline-1", "01"),
            RunDay("fail-baseline-2", "02"),
            RunDay("fail-current-1", "03"),
            RunDay("fail-current-2", "04"),
        ),
        current_run_ids=("fail-current-1", "fail-current-2"),
        baseline_run_ids=("fail-baseline-1", "fail-baseline-2"),
        expected_exit=1,
    ),
    WorkflowScenario(
        name="inconclusive",
        policy_fixture="policy-inconclusive.json",
        runs=(
            RunDay("inconclusive-baseline-1", "01"),
            RunDay("inconclusive-baseline-2", "02"),
            RunDay("inconclusive-current-1", "03"),
        ),
        current_run_ids=("inconclusive-current-1",),
        baseline_run_ids=("inconclusive-baseline-1", "inconclusive-baseline-2"),
        expected_exit=2,
    ),
)


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=("pass", "fail", "inconclusive"))
def test_installed_command_workflow_writes_both_report_formats_for_each_verdict(
    scenario: WorkflowScenario, tmp_path: Path
) -> None:
    # Given: an isolated Prometheus fixture and the generated console command.
    command = perfcheck_executable(Path(sys.executable).parent.parent)
    policy_path = _ROOT / "tests/fixtures" / scenario.policy_fixture
    report_path = tmp_path / f"{scenario.name}.json"
    markdown_path = tmp_path / f"{scenario.name}.md"

    with mock_prometheus_endpoint(_PROMETHEUS_FIXTURE) as endpoint:
        # When: each public CLI stage receives its arguments without a shell.
        for run in scenario.runs:
            run_path = tmp_path / f"{run.run_id}.json"
            collect = subprocess.run(  # noqa: S603 - generated local console command.
                [
                    str(command),
                    "collect",
                    "--policy",
                    str(policy_path),
                    "--prometheus-url",
                    endpoint,
                    "--run-id",
                    run.run_id,
                    "--start",
                    f"2026-07-{run.day}T10:00:00Z",
                    "--end",
                    f"2026-07-{run.day}T10:10:00Z",
                    "--out",
                    str(run_path),
                ],
                check=False,
            )
            summary = subprocess.run(  # noqa: S603 - generated local console command.
                [
                    str(command),
                    "summarize",
                    "--policy",
                    str(policy_path),
                    "--run",
                    str(run_path),
                    "--out",
                    str(tmp_path / f"{run.run_id}.summary.json"),
                ],
                check=False,
            )
            assert collect.returncode == 0
            assert summary.returncode == 0

        compare = subprocess.run(  # noqa: S603 - generated local console command.
            [
                str(command),
                "compare",
                "--policy",
                str(policy_path),
                *(
                    argument
                    for run_id in scenario.current_run_ids
                    for argument in (
                        "--current",
                        str(tmp_path / f"{run_id}.summary.json"),
                    )
                ),
                *(
                    argument
                    for run_id in scenario.baseline_run_ids
                    for argument in (
                        "--baseline",
                        str(tmp_path / f"{run_id}.summary.json"),
                    )
                ),
                "--report-json",
                str(report_path),
                "--report-md",
                str(markdown_path),
            ],
            check=False,
        )

    # Then: the verdict and portable JSON and Markdown report contracts hold.
    assert compare.returncode == scenario.expected_exit
    assert report_path.is_file()
    assert markdown_path.is_file()
    golden_path = _ROOT / f"tests/fixtures/golden/{scenario.name}.json"
    assert (
        json.loads(report_path.read_text(encoding="utf-8"))["suite_status"]
        == json.loads(golden_path.read_text(encoding="utf-8"))["suite_status"]
    )
