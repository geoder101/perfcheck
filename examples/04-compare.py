# pyright: basic
# ruff: noqa: ANN001, ANN202, D100, E501, N999, PLC0415, PLR0913, PLR0917, PLR1711, T201

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
    # Compare verified evidence

    ## Goal

    Independently create baseline and current summaries, compare them under one
    policy, and inspect the portable JSON and Markdown decision reports.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Inputs

    Fixed run IDs, UTC intervals, a policy fixture, explicit bootstrap seed and
    resamples, and a bundled loopback matrix fixture make this lesson repeatable.
    Every raw run, summary, and report stays in a temporary workspace.
    """)
    return


@app.cell
def _():
    import json
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
    runs = (
        ("lesson-baseline-1", "2026-07-01"),
        ("lesson-baseline-2", "2026-07-02"),
        ("lesson-current-1", "2026-07-03"),
        ("lesson-current-2", "2026-07-04"),
    )
    with (
        example_workspace() as workspace,
        mock_prometheus_endpoint(fixture_path) as endpoint,
    ):
        summaries = {}
        stage_statuses: list[int] = []
        for run_id, day in runs:
            raw_path = workspace / f"{run_id}.json"
            summary_path = workspace / f"{run_id}.summary.json"
            collect_result = run_local_command(
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
            summarize_result = run_local_command(
                (
                    str(perfcheck_executable()),
                    "summarize",
                    "--policy",
                    str(policy_path),
                    "--run",
                    str(raw_path),
                    "--out",
                    str(summary_path),
                ),
                cwd=workspace,
            )
            summaries[run_id] = summary_path
            stage_statuses.extend(
                (collect_result.returncode, summarize_result.returncode)
            )
        json_report_path = workspace / "comparison.json"
        markdown_report_path = workspace / "comparison.md"
        compare_result = run_local_command(
            (
                str(perfcheck_executable()),
                "compare",
                "--policy",
                str(policy_path),
                "--current",
                str(summaries["lesson-current-1"]),
                "--current",
                str(summaries["lesson-current-2"]),
                "--baseline",
                str(summaries["lesson-baseline-1"]),
                "--baseline",
                str(summaries["lesson-baseline-2"]),
                "--report-json",
                str(json_report_path),
                "--report-md",
                str(markdown_report_path),
                "--seed",
                "20260704",
                "--resamples",
                "1000",
            ),
            cwd=workspace,
        )
        report_payload = json.loads(json_report_path.read_text(encoding="utf-8"))
        markdown_excerpt = " / ".join(
            markdown_report_path.read_text(encoding="utf-8").splitlines()[:4]
        )
    evidence = {
        "suite_status": report_payload["suite_status"],
        "metric_status": report_payload["metrics"][0]["status"],
        "run_count": len(runs),
        "stage_statuses": tuple(stage_statuses),
        "comparison_status": compare_result.returncode,
        "seed": 20260704,
        "resamples": 1000,
    }
    metric = report_payload["metrics"][0]
    json_excerpt = json.dumps(
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
    return evidence, json_excerpt, markdown_excerpt


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Run

    `compare` receives four verified summaries, two per cohort. The explicit
    seed and resample count make the bootstrap decision reproducible.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Evidence

    Expected evidence: the fixture policy produces a passing suite decision and
    both report formats exist only at temporary paths. The next line places
    narrowed, stable JSON and Markdown excerpts side-by-side; no paths are shown.
    """)
    return


@app.cell
def _(evidence, json_excerpt, markdown_excerpt):
    print("Goal: compare deterministic baseline and current evidence")
    print("Inputs: fixed UTC runs, local fixture, seed=20260704, resamples=1000")
    print(f"Run: compare exit status {evidence['comparison_status']}")
    print(f"Evidence: {evidence}")
    print(
        f"JSON report (temporary): {json_excerpt} | Markdown report (temporary): {markdown_excerpt}"
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Takeaway

    CI can retain both portable formats for review while using the compare exit
    status as its decision signal. The paths in this lesson are temporary.
    """)
    return


@app.cell
def _():
    print(
        "Takeaway: retain reports, then use the documented comparison exit status in CI."
    )
    return


if __name__ == "__main__":
    app.run()
