"""Collect a portable perfcheck raw-run artifact."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


with app.setup:
    import sys
    from pathlib import Path

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))

    from examples._markdown import md
    from examples._support import (
        CollectRequest,
        LessonContext,
        LessonRun,
        RawEvidence,
        collect_arguments,
        example_workspace,
        lesson_context,
        mock_prometheus_endpoint,
        parse_raw_evidence,
        run_local_command,
    )


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
# Collect a raw run

## Goal

Create one portable raw-run artifact with `perfcheck collect`, using a
deterministic loopback Prometheus fixture instead of an external service.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Inputs

The lesson copies nothing into the repository: a policy fixture and matrix
fixture are read from the project, while the raw artifact lives only in a
helper-managed temporary workspace.
        """)


@app.cell
def _() -> tuple[LessonContext, LessonRun]:
    context = lesson_context()
    run = LessonRun("lesson-collect", "2026-07-01")
    return context, run


@app.cell
def _(context: LessonContext, run: LessonRun) -> tuple[int, RawEvidence]:
    with (
        example_workspace() as workspace,
        mock_prometheus_endpoint(context.fixture_path) as endpoint,
    ):
        raw_path = workspace / "raw-run.json"
        request = CollectRequest(
            endpoint=endpoint,
            run=run,
            output_path=raw_path,
        )
        collect_result = run_local_command(
            collect_arguments(context, request),
            cwd=workspace,
        )
        safe_excerpt = parse_raw_evidence(raw_path.read_bytes())
    collect_status = collect_result.returncode
    return collect_status, safe_excerpt


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Run

`collect` runs against a local fixture on an ephemeral loopback port. Its
server and temporary workspace are both cleaned up when the cell finishes.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Evidence

The next cell shows a narrowed, safe excerpt before displaying it: a stable
run identifier, schema version, and metric-record count, not request URLs
or full artifact internals.
        """)


@app.cell
def _(collect_status: int, safe_excerpt: RawEvidence) -> None:
    message = "\n".join(
        (
            "Goal: collect deterministic raw evidence",
            "Inputs: policy fixture and loopback Prometheus fixture",
            f"Run: exit status {collect_status}",
            f"Evidence: {safe_excerpt}",
        )
    )
    _ = sys.stdout.write(f"{message}\n")


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Takeaway

`collect` writes a raw run that can move between environments. Use temporary
output paths for exploration; production automation should choose its own
managed output location.
        """)


@app.cell
def _() -> None:
    _ = sys.stdout.write("Takeaway: collect raw evidence before any policy summary.\n")


if __name__ == "__main__":
    _app_run_result = app.run()
