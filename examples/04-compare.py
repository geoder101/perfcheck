"""Compare deterministic perfcheck summary cohorts."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


with app.setup:
    import json
    import sys
    from pathlib import Path

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))

    from examples._markdown import md
    from examples._support import (
        COMPARE_COHORT,
        CollectRequest,
        CompareRequest,
        LessonContext,
        LessonRun,
        ReportEvidence,
        SummaryRequest,
        collect_arguments,
        compare_arguments,
        example_workspace,
        lesson_context,
        mock_prometheus_endpoint,
        parse_report_evidence,
        run_local_command,
        summarize_arguments,
    )


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    # Compare verified evidence

    ## Goal

    Independently create baseline and current summaries, compare them under one
    policy, and inspect the portable JSON and Markdown decision reports.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Inputs

    Fixed run IDs, UTC intervals, a policy fixture, explicit bootstrap seed and
    resamples, and a bundled loopback matrix fixture make this lesson repeatable.
    Every raw run, summary, and report stays in a temporary workspace.
        """)


@app.cell
def _() -> tuple[LessonContext, tuple[LessonRun, ...]]:
    context = lesson_context()
    runs = COMPARE_COHORT
    return context, runs


@app.cell
def _(
    context: LessonContext, runs: tuple[LessonRun, ...]
) -> tuple[tuple[int, ...], int, ReportEvidence, str, str]:
    with (
        example_workspace() as workspace,
        mock_prometheus_endpoint(context.fixture_path) as endpoint,
    ):
        summary_paths: list[Path] = []
        stage_statuses: list[int] = []
        for run in runs:
            raw_path = workspace / f"{run.run_id}.json"
            summary_path = workspace / f"{run.run_id}.summary.json"
            collect_result = run_local_command(
                collect_arguments(
                    context,
                    CollectRequest(endpoint=endpoint, run=run, output_path=raw_path),
                ),
                cwd=workspace,
            )
            summarize_result = run_local_command(
                summarize_arguments(
                    context,
                    SummaryRequest(raw_path=raw_path, output_path=summary_path),
                ),
                cwd=workspace,
            )
            summary_paths.append(summary_path)
            stage_statuses.extend(
                (collect_result.returncode, summarize_result.returncode)
            )
        json_report_path = workspace / "comparison.json"
        markdown_report_path = workspace / "comparison.md"
        compare_result = run_local_command(
            compare_arguments(
                context,
                CompareRequest(
                    current_paths=tuple(summary_paths[2:]),
                    baseline_paths=tuple(summary_paths[:2]),
                    report_json_path=json_report_path,
                    report_markdown_path=markdown_report_path,
                    seed=20260704,
                    resamples=1000,
                ),
            ),
            cwd=workspace,
        )
        report_evidence = parse_report_evidence(json_report_path.read_bytes())
        markdown_excerpt = " / ".join(
            markdown_report_path.read_text(encoding="utf-8").splitlines()[:4]
        )
        comparison_status = compare_result.returncode
        stage_statuses_tuple = tuple(stage_statuses)
    json_excerpt = json.dumps(
        {
            "metric": {
                "metric_id": report_evidence["metric_id"],
                "method": report_evidence["method"],
                "status": report_evidence["metric_status"],
            },
            "suite_status": report_evidence["suite_status"],
        },
        sort_keys=True,
    )
    return (
        stage_statuses_tuple,
        comparison_status,
        report_evidence,
        json_excerpt,
        markdown_excerpt,
    )


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Run

    `compare` receives four verified summaries, two per cohort. The explicit
    seed and resample count make the bootstrap decision reproducible.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Evidence

    Expected evidence: the fixture policy produces a passing suite decision and
    both report formats exist only at temporary paths. The next line places
    narrowed, stable JSON and Markdown excerpts side-by-side; no paths are shown.
        """)


@app.cell
def _(
    comparison_status: int,
    json_excerpt: str,
    markdown_excerpt: str,
    report_evidence: ReportEvidence,
    stage_statuses_tuple: tuple[int, ...],
) -> None:
    evidence = {
        "suite_status": report_evidence["suite_status"],
        "metric_status": report_evidence["metric_status"],
        "run_count": len(COMPARE_COHORT),
        "stage_statuses": stage_statuses_tuple,
        "comparison_status": comparison_status,
        "seed": 20260704,
        "resamples": 1000,
    }
    report_line = f"JSON report (temporary): {json_excerpt} | \
Markdown report (temporary): {markdown_excerpt}"
    message = "\n".join(
        (
            "Goal: compare deterministic baseline and current evidence",
            "Inputs: fixed UTC runs, local fixture, seed=20260704, resamples=1000",
            f"Run: compare exit status {comparison_status}",
            f"Evidence: {evidence}",
            report_line,
        )
    )
    _ = sys.stdout.write(f"{message}\n")


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Takeaway

    CI can retain both portable formats for review while using the compare exit
    status as its decision signal. The paths in this lesson are temporary.
        """)


@app.cell
def _() -> None:
    _ = sys.stdout.write(
        "Takeaway: retain reports, then use the documented comparison exit \
status in CI.\n"
    )


if __name__ == "__main__":
    _app_run_result = app.run()
