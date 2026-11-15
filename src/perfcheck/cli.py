"""perfcheck console application."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path  # noqa: TC003 - Typer resolves command annotations at runtime.
from typing import TYPE_CHECKING, Annotated, NoReturn, assert_never

import typer
from asyncer import runnify
from rich.console import Console
from rich.table import Table

from perfcheck.bootstrap_models import BootstrapInputError
from perfcheck.cli_services import (
    CliInputCode,
    CliInputError,
    effective_summary,
    load_policy,
    load_raw,
    options,
    preflight_paths,
    schema_pointer,
    stamp_policy,
    summarize_raw,
    warn_schema_pointer,
    write_report,
)
from perfcheck.collection_auth import (
    AuthResolutionError,
    AuthScheme,
    resolve_auth,
)
from perfcheck.collection_models import SourceInterval
from perfcheck.collection_service import (
    CollectionInputCode,
    CollectionInputError,
    collect_run,
    has_enabled_failure,
)
from perfcheck.comparison_models import ComparisonCohorts
from perfcheck.errors import ArtifactSchemaError, PerfcheckError
from perfcheck.model_types import RunId, Status
from perfcheck.regression import evaluate_regression
from perfcheck.report import build_report, render_json_report, render_markdown_report
from perfcheck.storage import write_artifact, write_bytes

if TYPE_CHECKING:
    from collections.abc import Callable

app = typer.Typer(help="Reproducible performance-regression evidence for CI.")

policy_app = typer.Typer(
    no_args_is_help=True,
    help="Policy authoring and verification helpers.",
)
app.add_typer(policy_app, name="policy")

_console = Console(stderr=True)


@app.callback()
def main() -> None:
    """Configure the perfcheck command group."""


@app.command(name="collect")
def collect_command(  # noqa: PLR0913, PLR0917 - Typer exposes the documented flags.
    policy_path: Annotated[Path, typer.Option("--policy")],
    run_id: Annotated[str, typer.Option("--run-id")],
    start: Annotated[str, typer.Option("--start")],
    end: Annotated[str, typer.Option("--end")],
    output_path: Annotated[Path, typer.Option("--out")],
    force: Annotated[bool, typer.Option("--force")] = False,
    prometheus_url: Annotated[str | None, typer.Option("--prometheus-url")] = None,
    prometheus_auth_scheme: Annotated[
        AuthScheme | None,
        typer.Option(
            "--prometheus-auth-scheme",
            help=(
                "Prometheus HTTP auth scheme: none, bearer, or basic. "
                "A flag wins over the matching env var."
            ),
        ),
    ] = None,
    prometheus_bearer_token: Annotated[
        str | None, typer.Option("--prometheus-bearer-token")
    ] = None,
    prometheus_auth_basic_user: Annotated[
        str | None, typer.Option("--prometheus-auth-basic-user")
    ] = None,
    prometheus_auth_basic_password: Annotated[
        str | None, typer.Option("--prometheus-auth-basic-password")
    ] = None,
) -> None:
    """Collect all suite metrics into one atomic portable raw run artifact.

    HTTP auth is resolved from these flags with the matching env var as fallback;
    a flag wins over its env var. The resolved configuration is forwarded to the
    transport only and is never written to the artifact or CLI output.
    """

    def action() -> None:
        preflight_paths((output_path,), force=force)
        policy = load_policy(policy_path)
        try:
            interval = SourceInterval(
                start=datetime.fromisoformat(start), end=datetime.fromisoformat(end)
            )
        except ValueError as error:
            raise CollectionInputError(CollectionInputCode.INVALID_INTERVAL) from error
        auth_config = resolve_auth(
            prometheus_auth_scheme,
            prometheus_bearer_token,
            prometheus_auth_basic_user,
            prometheus_auth_basic_password,
        )
        run = runnify(collect_run)(
            policy,
            RunId(run_id),
            interval,
            prometheus_url,
            auth_config=auth_config,
        )
        write_artifact(output_path, run, force=force)
        _console.print(f"wrote run {run.run_id}")
        if has_enabled_failure(policy, run):
            _exit_code(4)

    _run_command(action)


@app.command(name="summarize")
def summarize_command(
    policy_path: Annotated[Path, typer.Option("--policy")],
    run_path: Annotated[Path, typer.Option("--run")],
    output_path: Annotated[Path, typer.Option("--out")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Create one canonical summary artifact from one verified raw run."""
    _run_command(
        lambda: _summarize(policy_path, run_path, output_path, force),
    )


@app.command(name="compare")
def compare_command(  # noqa: PLR0913, PLR0917 - Typer exposes the documented flags.
    policy_path: Annotated[Path, typer.Option("--policy")],
    current_paths: Annotated[list[Path], typer.Option("--current")],
    baseline_paths: Annotated[list[Path], typer.Option("--baseline")],
    report_json_path: Annotated[Path | None, typer.Option("--report-json")] = None,
    report_markdown_path: Annotated[Path | None, typer.Option("--report-md")] = None,
    force: Annotated[bool, typer.Option("--force")] = False,
    write_summary_cache: Annotated[bool, typer.Option("--write-summary-cache")] = False,
    seed: Annotated[int | None, typer.Option("--seed")] = None,
    resamples: Annotated[int | None, typer.Option("--resamples")] = None,
    emit_json: Annotated[
        bool,
        typer.Option(
            "--json",
            help=(
                "Additionally emit the JSON report to stdout; "
                "--report-json or --report-md is still required."
            ),
        ),
    ] = False,
) -> None:
    """Evaluate verified summaries or raw-run convenience inputs under one policy.

    Supply --report-json, --report-md, or both. --json also emits JSON to stdout.
    """

    def action() -> None:
        report_paths = tuple(
            path
            for path in (report_json_path, report_markdown_path)
            if path is not None
        )
        if not report_paths:
            raise CliInputError(CliInputCode.REPORT_REQUIRED)
        preflight_paths(report_paths, force)
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
        if report_json_path is not None:
            write_report(report_json_path, json_report.encode(), force)
        if report_markdown_path is not None:
            write_report(
                report_markdown_path, render_markdown_report(report).encode(), force
            )
        _render_outcome(outcome.status)
        if emit_json:
            typer.echo(json_report, nl=False)
        _exit_status(outcome.status)

    _run_command(action)


@policy_app.command(name="check")
def check_command(
    input_path: Annotated[Path, typer.Option("--input")],
) -> None:
    """Verify a policy is well-formed and its content hash matches its content.

    Requires ``--input``. Exits ``0`` when the policy validates and ``3`` for
    invalid JSON, a schema failure, or a content-hash mismatch. A ``$schema``
    pointer referencing an unknown or older perfcheck schema version prints a
    warning on stderr but still exits ``0``.
    """

    def action() -> None:
        policy = load_policy(input_path)
        warn_schema_pointer(schema_pointer(input_path))
        short = policy.policy_sha256[:12]
        _console.print(f"policy {policy.policy_id} is valid ({short})")

    _run_command(action)


@policy_app.command(name="stamp")
def stamp_command(
    input_path: Annotated[Path, typer.Option("--input")],
    output_path: Annotated[Path | None, typer.Option("--output")] = None,
    to_stdout: Annotated[bool, typer.Option("--stdout")] = False,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Stamp a policy with its content hash and write canonical JSON.

    Requires ``--input``. By default the stamped policy replaces the
    ``--input`` file in place; pass ``--force`` to allow the overwrite.
    ``--output`` writes a different path, and ``--stdout`` prints the stamped
    policy without writing a file. ``--stdout`` takes precedence over
    ``--output``.
    """

    def action() -> None:
        stamped_bytes = stamp_policy(input_path)
        if to_stdout:
            typer.echo(stamped_bytes.decode("utf-8"), nl=False)
            return
        destination = output_path if output_path is not None else input_path
        preflight_paths((destination,), force=force)
        write_bytes(destination, stamped_bytes, force=force)
        _console.print(f"wrote policy {destination}")

    _run_command(action)


def _summarize(
    policy_path: Path, run_path: Path, output_path: Path, force: bool
) -> None:
    preflight_paths((output_path,), force)
    policy = load_policy(policy_path)
    raw = load_raw(run_path)
    summary = summarize_raw(raw, policy)
    write_artifact(output_path, summary, force=force, source_run=raw)
    _console.print(f"wrote summary {summary.summary_id}")


def _run_command(action: Callable[[], None]) -> None:
    try:
        action()
    except typer.Exit:
        raise
    except (CliInputError, PerfcheckError, OSError) as error:
        _exit_input_error(error)
    except Exception:  # noqa: BLE001
        # Defense in depth: an unexpected failure (a bug, or a third-party error
        # carrying internal state or credential-shaped values in its message)
        # must never reach standalone_mode with a traceback on command output.
        # Fail closed on a dedicated exit status, keeping internal failures
        # distinct from a genuine suite FAIL and reported without their message.
        _console.print("error: internal failure")
        raise typer.Exit(5) from None


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
        case _:
            assert_never(status)


def _exit_status(status: Status) -> NoReturn:
    _exit_code(_status_exit_code(status))


def _exit_code(code: int) -> NoReturn:
    raise typer.Exit(code)


# Pure typed input diagnostics carry a stable, secret-free label and are safe
# to surface; ArtifactIntegrityError carries the artifact id and OSError carries
# untrusted file state, so both keep a generic message. AuthResolutionError
# carries a secret-free reason, so its message is surfaced rather than the
# generic "invalid command input".
_INPUT_DIAGNOSTICS: tuple[type[PerfcheckError], ...] = (
    CliInputError,
    CollectionInputError,
    BootstrapInputError,
    ArtifactSchemaError,
    AuthResolutionError,
)


def _exit_input_error(error: Exception) -> NoReturn:
    if isinstance(error, _INPUT_DIAGNOSTICS):
        _console.print(f"error: {error}")
    else:
        _console.print("error: invalid command input")
    raise typer.Exit(3)
