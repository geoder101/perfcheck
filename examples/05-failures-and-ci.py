# pyright: basic
# ruff: noqa: ANN001, ANN202, D100, N999, PLC0415, PLR1711, T201

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
    # Handle a CLI failure safely in CI

    ## Goal

    Construct local raw-run comparison inputs, then safely demonstrate the documented
    preflight failure caused by attempting to overwrite report outputs.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Inputs

    This lesson independently makes four fixed UTC runs from the bundled policy
    and loopback fixtures. `compare` accepts those raw-run convenience inputs;
    a fixed seed and resample count make the first call reproducible before the
    second intentionally omits `--force`.
    """)
    return


@app.cell
def _():
    import sys
    from pathlib import Path

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
        mock_prometheus_endpoint,
        perfcheck_executable,
        repository_root,
        run_local_command,
    )


@app.cell
def _(
    example_workspace,
    mock_prometheus_endpoint,
    perfcheck_executable,
    repository_root,
    run_local_command,
):
    policy_path = repository_root / "tests/fixtures/policy-pass.json"
    fixture_path = repository_root / "examples/fixtures/prometheus-matrix.json"
    runs = (
        ("failure-baseline-1", "2026-07-11"),
        ("failure-baseline-2", "2026-07-12"),
        ("failure-current-1", "2026-07-13"),
        ("failure-current-2", "2026-07-14"),
    )
    with (
        example_workspace() as workspace,
        mock_prometheus_endpoint(fixture_path) as endpoint,
    ):
        raw_runs = {}
        for run_id, day in runs:
            raw_path = workspace / f"{run_id}.json"
            _ = run_local_command(
                (
                    str(perfcheck_executable()),
                    "collect",
                    "--suite",
                    str(policy_path),
                    "--prometheus-url",
                    endpoint,
                    "--run-id",
                    run_id,
                    "--start",
                    f"{day}T10:00:00Z",
                    "--end",
                    f"{day}T10:10:00Z",
                    "--out",
                    str(raw_path),
                ),
                cwd=workspace,
            )
            raw_runs[run_id] = raw_path
        compare_arguments = (
            str(perfcheck_executable()),
            "compare",
            "--policy",
            str(policy_path),
            "--current",
            str(raw_runs["failure-current-1"]),
            "--current",
            str(raw_runs["failure-current-2"]),
            "--baseline",
            str(raw_runs["failure-baseline-1"]),
            "--baseline",
            str(raw_runs["failure-baseline-2"]),
            "--report-json",
            str(workspace / "existing-report.json"),
            "--report-md",
            str(workspace / "existing-report.md"),
            "--seed",
            "20260705",
            "--resamples",
            "1000",
        )
        initial_compare = run_local_command(compare_arguments, cwd=workspace)
        handled_failure = run_local_command(compare_arguments, cwd=workspace)
    failure_context = handled_failure.stderr.strip()
    return failure_context, handled_failure, initial_compare


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Run

    The first comparison writes its reports. The second uses the same paths
    without `--force`; the CLI preflight rejects stale output before it reads or
    overwrites evidence. The nonzero child status is captured, not propagated.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Evidence

    Expected handled failure: exit status 3 with `error: invalid command input`.
    Only sanitized stderr is displayed, and this lesson itself exits 0 so CI can
    test its failure-handling branch rather than accidentally failing the job.
    """)
    return


@app.cell
def _(failure_context, handled_failure, initial_compare):
    print("Goal: handle a documented CLI failure without failing the lesson")
    print("Inputs: fixture reports intentionally left at temporary output paths")
    print(f"Run: initial compare exit status {initial_compare.returncode}")
    print(
        f"Handled failure: exit status {handled_failure.returncode} — {failure_context}"
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Takeaway

    In CI, preserve the child process status and sanitized context as evidence.
    Decide whether that status should fail the job at the workflow boundary; a
    teaching probe must catch it so the notebook remains a successful process.
    """)
    return


@app.cell
def _():
    print("Takeaway: CI owns policy for a captured nonzero child status.")
    return


if __name__ == "__main__":
    app.run()
