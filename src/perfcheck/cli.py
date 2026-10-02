"""perfcheck console application."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path  # noqa: TC003 - Typer resolves command annotations at runtime.
from typing import Annotated, NoReturn

import typer
from asyncer import runnify
from rich.console import Console
from rich.table import Table

from perfcheck.cli_services import (
    CliInputError,
    effective_summary,
    load_policy,
    load_raw,
    options,
    preflight_paths,
    summarize_raw,
    write_report,
)
from perfcheck.collection_models import SourceInterval
from perfcheck.collection_service import (
    CollectionInputCode,
    CollectionInputError,
    collect_run,
    has_enabled_failure,
)
from perfcheck.comparison_models import ComparisonCohorts
from perfcheck.errors import PerfcheckError
from perfcheck.model_types import Status
from perfcheck.regression import evaluate_regression
from perfcheck.report import build_report, render_json_report, render_markdown_report
from perfcheck.storage import write_artifact

app = typer.Typer(help="Reproducible performance-regression evidence for CI.")
_console = Console(stderr=True)


@app.callback()
def main() -> None:
    """Configure the perfcheck command group."""


@app.command(name="summarize")
def summarize_command(
    policy_path: Annotated[Path, typer.Option("--policy")],
    run_path: Annotated[Path, typer.Option("--run")],
    output_path: Annotated[Path, typer.Option("--out")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Create one canonical summary artifact from one verified raw run."""
    try:
        preflight_paths((output_path,), force)
        policy = load_policy(policy_path)
        raw = load_raw(run_path)
        summary = summarize_raw(raw, policy)
        write_artifact(output_path, summary, force=force, source_run=raw)
        _console.print(f"wrote summary {summary.summary_id}")
    except (CliInputError, PerfcheckError, OSError) as error:
        _exit_input_error(error)
    except Exception:  # noqa: BLE001, BROAD_EXCEPT_OK - CLI must hide traces.
        _exit_unexpected()


@app.command()
def collect(  # noqa: PLR0913, PLR0917 - Typer exposes the documented flags.
    policy_path: Annotated[Path, typer.Option("--suite")],
    run_id: Annotated[str, typer.Option("--run-id")],
    start: Annotated[str, typer.Option("--start")],
    end: Annotated[str, typer.Option("--end")],
    output_path: Annotated[Path, typer.Option("--out")],
    prometheus_url: Annotated[str | None, typer.Option("--prometheus-url")] = None,
) -> None:
    """Collect all suite metrics into one atomic portable raw run artifact."""
    try:
        preflight_paths((output_path,), force=False)
        policy = load_policy(policy_path)
        try:
            interval = SourceInterval(
                start=datetime.fromisoformat(start), end=datetime.fromisoformat(end)
            )
        except ValueError as error:
            raise CollectionInputError(CollectionInputCode.INVALID_INTERVAL) from error
        run = runnify(collect_run)(
            policy,
            run_id,
            interval,
            prometheus_url,
        )
        write_artifact(output_path, run)
        _console.print(f"wrote run {run.run_id}")
        if has_enabled_failure(policy, run):
            _exit_code(4)
    except typer.Exit:
        raise
    except (CliInputError, PerfcheckError, OSError) as error:
        _exit_input_error(error)
    except Exception:  # noqa: BLE001, BROAD_EXCEPT_OK - CLI must hide traces.
        _exit_unexpected()


@app.command()
def compare(  # noqa: PLR0913, PLR0917 - Typer exposes the documented flags.
    policy_path: Annotated[Path, typer.Option("--policy")],
    current_paths: Annotated[list[Path], typer.Option("--current")],
    baseline_paths: Annotated[list[Path], typer.Option("--baseline")],
    report_json_path: Annotated[Path, typer.Option("--report-json")],
    report_markdown_path: Annotated[Path, typer.Option("--report-md")],
    force: Annotated[bool, typer.Option("--force")] = False,
    write_summary_cache: Annotated[bool, typer.Option("--write-summary-cache")] = False,
    seed: Annotated[int | None, typer.Option("--seed")] = None,
    resamples: Annotated[int | None, typer.Option("--resamples")] = None,
    emit_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Evaluate verified summaries or raw-run convenience inputs under one policy."""
    try:
        preflight_paths((report_json_path, report_markdown_path), force)
        policy = load_policy(policy_path)
        cohorts = ComparisonCohorts(
            current=tuple(
                effective_summary(path, policy, write_summary_cache)
                for path in current_paths
            ),
            baseline=tuple(
                effective_summary(path, policy, write_summary_cache)
                for path in baseline_paths
            ),
        )
        outcome = evaluate_regression(policy, cohorts, options(seed, resamples))
        report = build_report(policy, cohorts, outcome)
        json_report = render_json_report(report)
        write_report(report_json_path, json_report.encode(), force)
        write_report(
            report_markdown_path, render_markdown_report(report).encode(), force
        )
        _render_outcome(outcome.status)
        if emit_json:
            typer.echo(json_report, nl=False)
        _exit_status(outcome.status)
    except typer.Exit:
        raise
    except (CliInputError, PerfcheckError, OSError) as error:
        _exit_input_error(error)
    except Exception:  # noqa: BLE001, BROAD_EXCEPT_OK - CLI must hide traces.
        _exit_unexpected()


def _render_outcome(status: Status) -> None:
    table = Table(show_header=False)
    table.add_row("suite status", status)
    _console.print(table)


def _status_exit_code(status: Status) -> int:
    match status:
        case Status.PASS:
            return 0
        case Status.FAIL:
            return 1
        case Status.INCONCLUSIVE:
            return 2


def _exit_status(status: Status) -> NoReturn:
    _exit_code(_status_exit_code(status))


def _exit_code(code: int) -> NoReturn:
    raise typer.Exit(code)


def _exit_input_error(error: Exception) -> NoReturn:
    _console.print(f"error: {error}")
    raise typer.Exit(3)


def _exit_unexpected() -> NoReturn:
    _console.print("error: unexpected failure")
    raise typer.Exit(70)
