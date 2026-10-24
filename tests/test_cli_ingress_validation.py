from __future__ import annotations

from sys import float_info
from typing import TYPE_CHECKING, Literal, assert_never

import pytest
from typer.testing import CliRunner

from perfcheck.cli import app
from perfcheck.model_types import Statistic
from perfcheck.storage import policy_content_sha256, write_artifact
from tests.cli_support import cli_policy, cli_run, compare_inputs, write_cli_policy
from tests.schema_boundary_support import mutated_json

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("kind", ["missing", "malformed", "stale"])
def test_collect_rejects_invalid_policy_before_client_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: Literal["missing", "malformed", "stale"],
) -> None:
    # Given: an absent, malformed, or hash-stale policy and no permission to collect.
    policy_path = tmp_path / "policy.json"
    match kind:
        case "missing":
            pass
        case "malformed":
            _ = policy_path.write_text("{", encoding="utf-8")
        case "stale":
            _ = policy_path.write_text(
                mutated_json(cli_policy(), ("policy_id",), "changed"), encoding="utf-8"
            )
        case unreachable:
            assert_never(unreachable)
    output = tmp_path / "run.json"

    def unexpected_client() -> None:
        pytest.fail("client created before policy validation")

    monkeypatch.setattr("httpx2.AsyncClient", unexpected_client)

    # When: collect receives the invalid policy through the real command boundary.
    result = CliRunner().invoke(
        app,
        [
            "collect",
            "--suite",
            str(policy_path),
            "--run-id",
            "run-1",
            "--start",
            "2026-01-01T00:00:00Z",
            "--end",
            "2026-01-01T00:10:00Z",
            "--out",
            str(output),
        ],
    )

    # Then: it safely rejects input without stdout, network clients, or artifacts.
    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr == "error: invalid command input\n"
    assert not output.exists()


@pytest.mark.parametrize(
    "interval",
    [
        ("not-a-date", "2026-01-01T00:10:00Z"),
        ("2026-01-01T00:00:00Z", "not-a-date"),
        ("2026-01-01T00:10:00Z", "2026-01-01T00:00:00Z"),
        ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        ("2026-01-01T00:00:00+01:00", "2026-01-01T00:10:00Z"),
        ("2026-01-01T00:00:00Z", "2026-01-01T01:10:00+01:00"),
        ("2026-01-01T00:00:00", "2026-01-01T00:10:00Z"),
    ],
)
def test_collect_rejects_invalid_interval_before_client_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interval: tuple[str, str],
) -> None:
    # Given: a valid policy and an interval supplied by the parameter matrix.
    start, end = interval
    policy_path = tmp_path / "policy.json"
    write_cli_policy(policy_path, cli_policy())
    output = tmp_path / "run.json"

    def unexpected_client() -> None:
        pytest.fail("client created before interval validation")

    monkeypatch.setattr("httpx2.AsyncClient", unexpected_client)

    # When: collect parses the supplied timestamps and interval.
    result = CliRunner().invoke(
        app,
        [
            "collect",
            "--suite",
            str(policy_path),
            "--run-id",
            "run-1",
            "--start",
            start,
            "--end",
            end,
            "--out",
            str(output),
        ],
    )

    # Then: interval rejection is safe and cannot leave partial artifacts.
    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr == "error: invalid command input\n"
    assert not output.exists()


@pytest.mark.parametrize("override", [("--seed", "-1"), ("--resamples", "0")])
def test_compare_rejects_invalid_bootstrap_options_on_eligible_cohorts(
    tmp_path: Path, override: tuple[str, str]
) -> None:
    # Given: eligible cohorts that reach bootstrap option validation.
    arguments = compare_inputs(tmp_path, multi_run=True)
    report_json, report_md = tmp_path / "report.json", tmp_path / "report.md"
    arguments.extend(
        [
            "--report-json",
            str(report_json),
            "--report-md",
            str(report_md),
            "--json",
            *override,
        ]
    )

    # When: compare receives an invalid numerical bootstrap option.
    result = CliRunner().invoke(app, arguments)

    # Then: it exits safely before writing either report or machine stdout.
    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr.endswith("error: invalid command input\n")
    assert not report_json.exists()
    assert not report_md.exists()


@pytest.mark.parametrize("multi_run", [False, True])
def test_compare_arithmetic_overflow_exits_safely_without_reports(
    tmp_path: Path, multi_run: bool
) -> None:
    # Given: eligible finite raw evidence using FIRST to preserve extreme samples.
    policy = cli_policy()
    metric = policy.metrics[0].model_copy(update={"statistic": Statistic.FIRST})
    policy = policy.model_copy(update={"metrics": (metric,)})
    policy = policy.model_copy(update={"policy_sha256": policy_content_sha256(policy)})
    policy_path = tmp_path / "policy.json"
    write_cli_policy(policy_path, policy)
    arguments = ["compare", "--policy", str(policy_path)]
    counts = (
        (policy.min_current_runs, policy.min_baseline_runs) if multi_run else (1, 1)
    )
    index = 0
    for cohort, count, value in zip(
        ("current", "baseline"), counts, (float_info.max, -float_info.max), strict=True
    ):
        for member in range(count):
            index += 1
            path = tmp_path / f"{cohort}-{member}.json"
            write_artifact(path, cli_run(policy, index, value))
            arguments.extend([f"--{cohort}", str(path)])
    report_json, report_md = tmp_path / "report.json", tmp_path / "report.md"
    arguments.extend(
        [
            "--report-json",
            str(report_json),
            "--report-md",
            str(report_md),
            "--json",
        ]
    )

    # When: a real comparison reaches overflowing cohort or reference arithmetic.
    result = CliRunner().invoke(app, arguments)

    # Then: the typed numerical failure reaches the safe CLI input-error boundary.
    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr.endswith("error: invalid command input\n")
    assert "RuntimeWarning" not in result.stderr
    assert "Traceback" not in result.stderr
    assert not report_json.exists()
    assert not report_md.exists()
