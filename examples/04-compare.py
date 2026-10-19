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
    # Compare verified evidence

    ## Goal

    Independently create baseline and current summaries, compare them under one
    policy, and inspect the portable JSON and Markdown decision reports.
    """
    )
    return  # noqa: PLR1711


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Inputs

    Fixed run IDs, UTC intervals, a policy fixture, explicit bootstrap seed and
    resamples, and a bundled loopback matrix fixture make this lesson repeatable.
    Every raw run, summary, and report stays in a temporary workspace.
    """
    )
    return  # noqa: PLR1711


@app.cell
def _():  # noqa: ANN202
    import json  # noqa: PLC0415
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
    runs = (
        ("lesson-baseline-1", "2026-07-01"),
        ("lesson-baseline-2", "2026-07-02"),
        ("lesson-current-1", "2026-07-03"),
        ("lesson-current-2", "2026-07-04"),
    )
    with (
        example_workspace() as workspace,  # pyright: ignore[reportUnknownVariableType]
        mock_prometheus_endpoint(fixture_path) as endpoint,  # pyright: ignore[reportUnknownVariableType]
    ):
        summaries = {}
        stage_statuses: list[int] = []
        for run_id, day in runs:
            raw_path = workspace / f"{run_id}.json"  # pyright: ignore[reportUnknownVariableType]
            summary_path = workspace / f"{run_id}.summary.json"  # pyright: ignore[reportUnknownVariableType]
            collect_result = run_local_command(  # pyright: ignore[reportUnknownVariableType]
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
            summarize_result = run_local_command(  # pyright: ignore[reportUnknownVariableType]
                (
                    str(perfcheck_executable()),  # pyright: ignore[reportUnknownArgumentType]
                    "summarize",
                    "--policy",
                    str(policy_path),  # pyright: ignore[reportUnknownArgumentType]
                    "--run",
                    str(raw_path),  # pyright: ignore[reportUnknownArgumentType]
                    "--out",
                    str(summary_path),  # pyright: ignore[reportUnknownArgumentType]
                ),
                cwd=workspace,
            )
            summaries[run_id] = summary_path
            stage_statuses.extend(
                (collect_result.returncode, summarize_result.returncode)  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            )
        json_report_path = workspace / "comparison.json"  # pyright: ignore[reportUnknownVariableType]
        markdown_report_path = workspace / "comparison.md"  # pyright: ignore[reportUnknownVariableType]
        compare_result = run_local_command(  # pyright: ignore[reportUnknownVariableType]
            (
                str(perfcheck_executable()),  # pyright: ignore[reportUnknownArgumentType]
                "compare",
                "--policy",
                str(policy_path),  # pyright: ignore[reportUnknownArgumentType]
                "--current",
                str(summaries["lesson-current-1"]),  # pyright: ignore[reportUnknownArgumentType]
                "--current",
                str(summaries["lesson-current-2"]),  # pyright: ignore[reportUnknownArgumentType]
                "--baseline",
                str(summaries["lesson-baseline-1"]),  # pyright: ignore[reportUnknownArgumentType]
                "--baseline",
                str(summaries["lesson-baseline-2"]),  # pyright: ignore[reportUnknownArgumentType]
                "--report-json",
                str(json_report_path),  # pyright: ignore[reportUnknownArgumentType]
                "--report-md",
                str(markdown_report_path),  # pyright: ignore[reportUnknownArgumentType]
                "--seed",
                "20260704",
                "--resamples",
                "1000",
            ),
            cwd=workspace,
        )
        report_payload = json.loads(json_report_path.read_text(encoding="utf-8"))  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        markdown_excerpt = " / ".join(
            markdown_report_path.read_text(encoding="utf-8").splitlines()[:4]  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
        )
    evidence = {  # pyright: ignore[reportUnknownVariableType]
        "suite_status": report_payload["suite_status"],
        "metric_status": report_payload["metrics"][0]["status"],
        "run_count": len(runs),
        "stage_statuses": tuple(stage_statuses),
        "comparison_status": compare_result.returncode,  # pyright: ignore[reportUnknownMemberType]
        "seed": 20260704,
        "resamples": 1000,
    }
    metric = report_payload["metrics"][0]  # pyright: ignore[reportUnknownVariableType]
    json_excerpt = json.dumps(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        {
            "metric": {
                "metric_id": metric["metric_id"],
                "method": metric["method"],
                "status": metric["status"],
            },
            "suite_status": report_payload["suite_status"],
        },
        sort_keys=True,
    )
    return evidence, json_excerpt, markdown_excerpt  # pyright: ignore[reportUnknownVariableType]


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Run

    `compare` receives four verified summaries, two per cohort. The explicit
    seed and resample count make the bootstrap decision reproducible.
    """
    )
    return  # noqa: PLR1711


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Evidence

    Expected evidence: the fixture policy produces a passing suite decision and
    both report formats exist only at temporary paths. The next line places
    narrowed, stable JSON and Markdown excerpts side-by-side; no paths are shown.
    """
    )
    return  # noqa: PLR1711


@app.cell  # pyright: ignore[reportUnknownArgumentType]
def _(evidence, json_excerpt, markdown_excerpt):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    print("Goal: compare deterministic baseline and current evidence")  # noqa: T201
    print("Inputs: fixed UTC runs, local fixture, seed=20260704, resamples=1000")  # noqa: T201
    print(f"Run: compare exit status {evidence['comparison_status']}")  # noqa: T201
    print(f"Evidence: {evidence}")  # noqa: T201
    print(  # noqa: T201
        f"JSON report (temporary): {json_excerpt} | Markdown report (temporary): {markdown_excerpt}"  # noqa: E501
    )
    return  # noqa: PLR1711


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Takeaway

    CI can retain both portable formats for review while using the compare exit
    status as its decision signal. The paths in this lesson are temporary.
    """
    )
    return  # noqa: PLR1711


@app.cell
def _():  # noqa: ANN202
    print(  # noqa: T201
        "Takeaway: retain reports, then use the documented comparison exit status in CI."  # noqa: E501
    )
    return  # noqa: PLR1711


if __name__ == "__main__":
    app.run()  # pyright: ignore[reportUnusedCallResult]
