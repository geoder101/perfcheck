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
    # Collect a raw run

    ## Goal

    Create one portable raw-run artifact with `perfcheck collect`, using a
    deterministic loopback Prometheus fixture instead of an external service.
    """
    )
    return  # noqa: PLR1711


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Inputs

    The lesson copies nothing into the repository: a policy fixture and matrix
    fixture are read from the project, while the raw artifact lives only in a
    helper-managed temporary workspace.
    """
    )
    return  # noqa: PLR1711


@app.cell
def _():  # noqa: ANN202
    from pathlib import Path  # noqa: I001, PLC0415
    import json  # noqa: PLC0415
    import sys  # noqa: PLC0415

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
        json,
        mock_prometheus_endpoint,
        perfcheck_executable,
        repository_root,
        run_local_command,
    )


@app.cell  # pyright: ignore[reportUnknownArgumentType]
def _(  # noqa: ANN202, PLR0913, PLR0917  # pyright: ignore[reportUnknownParameterType]
    example_workspace,  # noqa: ANN001  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    json,  # noqa: ANN001  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mock_prometheus_endpoint,  # noqa: ANN001  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    perfcheck_executable,  # noqa: ANN001  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    repository_root,  # noqa: ANN001  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    run_local_command,  # noqa: ANN001  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
):
    policy_path = repository_root / "tests/fixtures/policy-pass.json"  # pyright: ignore[reportUnknownVariableType]
    fixture_path = repository_root / "examples/fixtures/prometheus-matrix.json"  # pyright: ignore[reportUnknownVariableType]
    with (
        example_workspace() as workspace,  # pyright: ignore[reportUnknownVariableType]
        mock_prometheus_endpoint(fixture_path) as endpoint,  # pyright: ignore[reportUnknownVariableType]
    ):
        raw_path = workspace / "raw-run.json"  # pyright: ignore[reportUnknownVariableType]
        collect_result = run_local_command(  # pyright: ignore[reportUnknownVariableType]
            (
                str(perfcheck_executable()),  # pyright: ignore[reportUnknownArgumentType]
                "collect",
                "--suite",
                str(policy_path),  # pyright: ignore[reportUnknownArgumentType]
                "--prometheus-url",
                endpoint,
                "--run-id",
                "lesson-collect",
                "--start",
                "2026-07-01T10:00:00Z",
                "--end",
                "2026-07-01T10:10:00Z",
                "--out",
                str(raw_path),  # pyright: ignore[reportUnknownArgumentType]
            ),
            cwd=workspace,
        )
        raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    safe_excerpt = {  # pyright: ignore[reportUnknownVariableType]
        "run_id": raw_payload["run_id"],
        "schema_version": raw_payload["schema_version"],
        "metric_record_count": len(raw_payload["metric_records"]),  # pyright: ignore[reportUnknownArgumentType]
    }
    return collect_result, safe_excerpt  # pyright: ignore[reportUnknownVariableType]


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Run

    `collect` runs against a local fixture on an ephemeral loopback port. Its
    server and temporary workspace are both cleaned up when the cell finishes.
    """
    )
    return  # noqa: PLR1711


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Evidence

    The next cell shows a narrowed, safe excerpt before displaying it: a stable
    run identifier, schema version, and metric-record count, not request URLs
    or full artifact internals.
    """
    )
    return  # noqa: PLR1711


@app.cell  # pyright: ignore[reportUnknownArgumentType]
def _(collect_result, safe_excerpt):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    print("Goal: collect deterministic raw evidence")  # noqa: T201
    print("Inputs: policy fixture and loopback Prometheus fixture")  # noqa: T201
    print(f"Run: exit status {collect_result.returncode}")  # noqa: T201  # pyright: ignore[reportUnknownMemberType]
    print(f"Evidence: {safe_excerpt}")  # noqa: T201
    return  # noqa: PLR1711


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Takeaway

    `collect` writes a raw run that can move between environments. Use temporary
    output paths for exploration; production automation should choose its own
    managed output location.
    """
    )
    return  # noqa: PLR1711


@app.cell
def _():  # noqa: ANN202
    print("Takeaway: collect raw evidence before any policy summary.")  # noqa: T201
    return  # noqa: PLR1711


if __name__ == "__main__":
    app.run()  # pyright: ignore[reportUnusedCallResult]
