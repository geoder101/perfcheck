"""Handle a documented perfcheck CLI failure safely in CI."""

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
        FAILURE_COHORT,
        CollectRequest,
        CompareRequest,
        LessonContext,
        LessonRun,
        collect_arguments,
        compare_arguments,
        example_workspace,
        lesson_context,
        mock_prometheus_endpoint,
        run_local_command,
    )


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    # Handle a CLI failure safely in CI

    ## Goal

    Construct local raw-run comparison inputs, then safely demonstrate the documented
    preflight failure caused by attempting to overwrite report outputs.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Inputs

    This lesson independently makes four fixed UTC runs from the bundled policy
    and loopback fixtures. `compare` accepts those raw-run convenience inputs;
    a fixed seed and resample count make the first call reproducible before the
    second intentionally omits `--force`.
        """)


@app.cell
def _() -> tuple[LessonContext, tuple[LessonRun, ...]]:
    context = lesson_context()
    runs = FAILURE_COHORT
    return context, runs


@app.cell
def _(context: LessonContext, runs: tuple[LessonRun, ...]) -> tuple[int, int, str]:
    with (
        example_workspace() as workspace,
        mock_prometheus_endpoint(context.fixture_path) as endpoint,
    ):
        raw_paths: list[Path] = []
        for run in runs:
            raw_path = workspace / f"{run.run_id}.json"
            _ = run_local_command(
                collect_arguments(
                    context,
                    CollectRequest(endpoint=endpoint, run=run, output_path=raw_path),
                ),
                cwd=workspace,
            )
            raw_paths.append(raw_path)
        compare_request = CompareRequest(
            current_paths=tuple(raw_paths[2:]),
            baseline_paths=tuple(raw_paths[:2]),
            report_json_path=workspace / "existing-report.json",
            report_markdown_path=workspace / "existing-report.md",
            seed=20260705,
            resamples=1000,
        )
        compare_command = compare_arguments(context, compare_request)
        initial_compare = run_local_command(compare_command, cwd=workspace)
        handled_failure = run_local_command(compare_command, cwd=workspace)
    initial_compare_status = initial_compare.returncode
    handled_failure_status = handled_failure.returncode
    failure_context = (handled_failure.stderr or "").strip()
    return initial_compare_status, handled_failure_status, failure_context


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Run

    The first comparison writes its reports. The second uses the same paths
    without `--force`; the CLI preflight rejects stale output before it reads or
    overwrites evidence. The nonzero child status is captured, not propagated.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Evidence

    Expected handled failure: exit status 3 with `error: invalid command input`.
    Only sanitized stderr is displayed, and this lesson itself exits 0 so CI can
    test its failure-handling branch rather than accidentally failing the job.
        """)


@app.cell
def _(
    failure_context: str, handled_failure_status: int, initial_compare_status: int
) -> None:
    handled_failure_line = " — ".join(
        (f"Handled failure: exit status {handled_failure_status}", failure_context)
    )
    message = "\n".join(
        (
            "Goal: handle a documented CLI failure without failing the lesson",
            "Inputs: fixture reports intentionally left at temporary output paths",
            f"Run: initial compare exit status {initial_compare_status}",
            handled_failure_line,
        )
    )
    _ = sys.stdout.write(f"{message}\n")


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Takeaway

    In CI, preserve the child process status and sanitized context as evidence.
    Decide whether that status should fail the job at the workflow boundary; a
    teaching probe must catch it so the notebook remains a successful process.
        """)


@app.cell
def _() -> None:
    _ = sys.stdout.write(
        "Takeaway: CI owns policy for a captured nonzero child status.\n"
    )


if __name__ == "__main__":
    _app_run_result = app.run()
