# pyright: basic
# ruff: noqa: ANN001, ANN202, D100, I001, N999, PLC0415, PLR0913, PLR0917, PLR1711, T201

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Collect a raw run

    ## Goal

    Create one portable raw-run artifact with `perfcheck collect`, using a
    deterministic loopback Prometheus fixture instead of an external service.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Inputs

    The lesson copies nothing into the repository: a policy fixture and matrix
    fixture are read from the project, while the raw artifact lives only in a
    helper-managed temporary workspace.
    """)
    return


@app.cell
def _():
    from pathlib import Path
    import json
    import sys

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))
    from examples._support import (
        example_workspace,
        mock_prometheus_endpoint,
        perfcheck_executable,
        run_local_command,
    )

    return (
        example_workspace,
        json,
        mock_prometheus_endpoint,
        perfcheck_executable,
        repository_root,
        run_local_command,
    )


@app.cell
def _(
    example_workspace,
    json,
    mock_prometheus_endpoint,
    perfcheck_executable,
    repository_root,
    run_local_command,
):
    policy_path = repository_root / "tests/fixtures/policy-pass.json"
    fixture_path = repository_root / "examples/fixtures/prometheus-matrix.json"
    with (
        example_workspace() as workspace,
        mock_prometheus_endpoint(fixture_path) as endpoint,
    ):
        raw_path = workspace / "raw-run.json"
        collect_result = run_local_command(
            (
                str(perfcheck_executable()),
                "collect",
                "--suite",
                str(policy_path),
                "--prometheus-url",
                endpoint,
                "--run-id",
                "lesson-collect",
                "--start",
                "2026-07-01T10:00:00Z",
                "--end",
                "2026-07-01T10:10:00Z",
                "--out",
                str(raw_path),
            ),
            cwd=workspace,
        )
        raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
    safe_excerpt = {
        "run_id": raw_payload["run_id"],
        "schema_version": raw_payload["schema_version"],
        "metric_record_count": len(raw_payload["metric_records"]),
    }
    return collect_result, safe_excerpt


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Run

    `collect` runs against a local fixture on an ephemeral loopback port. Its
    server and temporary workspace are both cleaned up when the cell finishes.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Evidence

    The next cell shows a narrowed, safe excerpt before displaying it: a stable
    run identifier, schema version, and metric-record count, not request URLs
    or full artifact internals.
    """)
    return


@app.cell
def _(collect_result, safe_excerpt):
    print("Goal: collect deterministic raw evidence")
    print("Inputs: policy fixture and loopback Prometheus fixture")
    print(f"Run: exit status {collect_result.returncode}")
    print(f"Evidence: {safe_excerpt}")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Takeaway

    `collect` writes a raw run that can move between environments. Use temporary
    output paths for exploration; production automation should choose its own
    managed output location.
    """)
    return


@app.cell
def _():
    print("Takeaway: collect raw evidence before any policy summary.")
    return


if __name__ == "__main__":
    app.run()
