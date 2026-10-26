"""Summarize verified perfcheck raw-run evidence."""

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
        SummaryEvidence,
        SummaryRequest,
        collect_arguments,
        example_workspace,
        lesson_context,
        mock_prometheus_endpoint,
        parse_summary_evidence,
        run_local_command,
        summarize_arguments,
    )


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    # Summarize verified evidence

    ## Goal

    Independently collect a raw run, summarize it, and observe that the public
    CLI rejects altered raw evidence before it can produce a summary.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Inputs

    This script has its own temporary workspace, policy fixture, and loopback
    matrix fixture. It teaches CLI outcomes and evidence identity fields without
    promising that the internal artifact schema is stable.

    The latency policy chooses the mean in seconds, zero warmup/cooldown,
    at least 20 retained points, 80% coverage and a 300-second analysis window.
    Eligibility checks data usability, not IID sampling or representativeness.
        """)


@app.cell
def _() -> tuple[LessonContext, LessonRun]:
    context = lesson_context()
    run = LessonRun("lesson-summarize", "2026-07-01")
    return context, run


@app.cell
def _(context: LessonContext, run: LessonRun) -> tuple[int, int, int, SummaryEvidence]:
    with (
        example_workspace() as workspace,
        mock_prometheus_endpoint(context.fixture_path) as endpoint,
    ):
        raw_path = workspace / "raw-run.json"
        summary_path = workspace / "summary.json"
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
        summary_evidence = parse_summary_evidence(summary_path.read_bytes())
        tampered_raw = raw_path.read_bytes().replace(
            b'"run_id":"lesson-summarize"', b'"run_id":"altered-raw-run"', 1
        )
        _ = raw_path.write_bytes(tampered_raw)
        tampered_result = run_local_command(
            summarize_arguments(
                context,
                SummaryRequest(
                    raw_path=raw_path,
                    output_path=workspace / "rejected-summary.json",
                ),
            ),
            cwd=workspace,
        )
        collect_status = collect_result.returncode
        summarize_status = summarize_result.returncode
        tampered_status = tampered_result.returncode
    return collect_status, summarize_status, tampered_status, summary_evidence


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Run

    The public `summarize` command reads the raw run and verifies its persisted
    identities before writing a canonical summary. A second summarize attempt
    uses an altered raw file and is expected to fail safely.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Evidence

    This narrowed excerpt displays the summary and source identifiers, the
    number of summarized metric records, eligibility, and the nonzero status
    from the altered raw-run probe. These are evidence fields, not a promise of
    schema stability.
        """)


@app.cell
def _(
    collect_status: int,
    summarize_status: int,
    summary_evidence: SummaryEvidence,
    tampered_status: int,
) -> None:
    evidence = {
        "summary_id": summary_evidence["summary_id"],
        "source_run_id": summary_evidence["source_run_id"],
        "metric_record_count": summary_evidence["metric_record_count"],
        "eligibility": summary_evidence["eligible"],
        "tampered_raw_exit_status": tampered_status,
    }
    message = "\n".join(
        (
            "Goal: summarize verified raw evidence",
            "Inputs: independently collected temporary raw run",
            f"Run: collect={collect_status}, summarize={summarize_status}",
            f"Evidence: {evidence}",
        )
    )
    _ = sys.stdout.write(f"{message}\n")


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Takeaway

    Summarization is not just formatting: it accepts verified raw evidence and
    rejects a tampered artifact with the documented input-error outcome.
    A scalar summarizes one run; 41 observations within that run do not become
    41 independent cohort runs. Next compare uses run-level scalars, and the
    capstone audits the same chain for each selected scenario.
        """)


@app.cell
def _() -> None:
    _ = sys.stdout.write(
        "Takeaway: summarize only trusted raw evidence through perfcheck.\n"
    )


if __name__ == "__main__":
    _app_run_result = app.run()
