import marimo  # noqa: D100, N999

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():  # noqa: ANN202
    import marimo as mo  # noqa: PLC0415

    return (mo,)


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    # Handle a CLI failure safely in CI

    ## Goal

    Construct local raw-run comparison inputs, then safely demonstrate the documented
    preflight failure caused by attempting to overwrite report outputs.
    """
    )
    return  # noqa: PLR1711


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Inputs

    This lesson independently makes four fixed UTC runs from the bundled policy
    and loopback fixtures. `compare` accepts those raw-run convenience inputs;
    a fixed seed and resample count make the first call reproducible before the
    second intentionally omits `--force`.
    """
    )
    return  # noqa: PLR1711


@app.cell
def _():  # noqa: ANN202
    import sys  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))
    from examples._support import (  # noqa: PLC0415
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


@app.cell  # pyright: ignore[reportUnknownArgumentType]
def _(  # noqa: ANN202  # pyright: ignore[reportUnknownParameterType]
    example_workspace,  # noqa: ANN001  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mock_prometheus_endpoint,  # noqa: ANN001  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    perfcheck_executable,  # noqa: ANN001  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    repository_root,  # noqa: ANN001  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    run_local_command,  # noqa: ANN001  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
):
    policy_path = repository_root / "tests/fixtures/policy-pass.json"  # pyright: ignore[reportUnknownVariableType]
    fixture_path = repository_root / "examples/fixtures/prometheus-matrix.json"  # pyright: ignore[reportUnknownVariableType]
    runs = (
        ("failure-baseline-1", "2026-07-11"),
        ("failure-baseline-2", "2026-07-12"),
        ("failure-current-1", "2026-07-13"),
        ("failure-current-2", "2026-07-14"),
    )
    with (
        example_workspace() as workspace,  # pyright: ignore[reportUnknownVariableType]
        mock_prometheus_endpoint(fixture_path) as endpoint,  # pyright: ignore[reportUnknownVariableType]
    ):
        raw_runs = {}
        for run_id, day in runs:
            raw_path = workspace / f"{run_id}.json"  # pyright: ignore[reportUnknownVariableType]
            _ = run_local_command(  # pyright: ignore[reportUnknownVariableType]
                (
                    str(perfcheck_executable()),  # pyright: ignore[reportUnknownArgumentType]
                    "collect",
                    "--suite",
                    str(policy_path),  # pyright: ignore[reportUnknownArgumentType]
                    "--prometheus-url",
                    endpoint,
                    "--run-id",
                    run_id,
                    "--start",
                    f"{day}T10:00:00Z",
                    "--end",
                    f"{day}T10:10:00Z",
                    "--out",
                    str(raw_path),  # pyright: ignore[reportUnknownArgumentType]
                ),
                cwd=workspace,
            )
            raw_runs[run_id] = raw_path
        compare_arguments = (
            str(perfcheck_executable()),  # pyright: ignore[reportUnknownArgumentType]
            "compare",
            "--policy",
            str(policy_path),  # pyright: ignore[reportUnknownArgumentType]
            "--current",
            str(raw_runs["failure-current-1"]),  # pyright: ignore[reportUnknownArgumentType]
            "--current",
            str(raw_runs["failure-current-2"]),  # pyright: ignore[reportUnknownArgumentType]
            "--baseline",
            str(raw_runs["failure-baseline-1"]),  # pyright: ignore[reportUnknownArgumentType]
            "--baseline",
            str(raw_runs["failure-baseline-2"]),  # pyright: ignore[reportUnknownArgumentType]
            "--report-json",
            str(workspace / "existing-report.json"),  # pyright: ignore[reportUnknownArgumentType]
            "--report-md",
            str(workspace / "existing-report.md"),  # pyright: ignore[reportUnknownArgumentType]
            "--seed",
            "20260705",
            "--resamples",
            "1000",
        )
        initial_compare = run_local_command(compare_arguments, cwd=workspace)  # pyright: ignore[reportUnknownVariableType]
        handled_failure = run_local_command(compare_arguments, cwd=workspace)  # pyright: ignore[reportUnknownVariableType]
    failure_context = handled_failure.stderr.strip()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return failure_context, handled_failure, initial_compare  # pyright: ignore[reportUnknownVariableType]


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Run

    The first comparison writes its reports. The second uses the same paths
    without `--force`; the CLI preflight rejects stale output before it reads or
    overwrites evidence. The nonzero child status is captured, not propagated.
    """
    )
    return  # noqa: PLR1711


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Evidence

    Expected handled failure: exit status 3 with `error: invalid command input`.
    Only sanitized stderr is displayed, and this lesson itself exits 0 so CI can
    test its failure-handling branch rather than accidentally failing the job.
    """
    )
    return  # noqa: PLR1711


@app.cell  # pyright: ignore[reportUnknownArgumentType]
def _(failure_context, handled_failure, initial_compare):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    print("Goal: handle a documented CLI failure without failing the lesson")  # noqa: T201
    print("Inputs: fixture reports intentionally left at temporary output paths")  # noqa: T201
    print(f"Run: initial compare exit status {initial_compare.returncode}")  # noqa: T201  # pyright: ignore[reportUnknownMemberType]
    print(  # noqa: T201
        f"Handled failure: exit status {handled_failure.returncode} — {failure_context}"  # pyright: ignore[reportUnknownMemberType]
    )
    return  # noqa: PLR1711


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Takeaway

    In CI, preserve the child process status and sanitized context as evidence.
    Decide whether that status should fail the job at the workflow boundary; a
    teaching probe must catch it so the notebook remains a successful process.
    """
    )
    return  # noqa: PLR1711


@app.cell
def _():  # noqa: ANN202
    print("Takeaway: CI owns policy for a captured nonzero child status.")  # noqa: T201
    return  # noqa: PLR1711


if __name__ == "__main__":
    app.run()  # pyright: ignore[reportUnusedCallResult]
