# pyright: basic
# ruff: noqa: ANN001, ANN202, D100, E501, I001, N999, PLC0415, PLR0913, PLR0917, PLR1711, T201

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
    # Summarize verified evidence

    ## Goal

    Independently collect a raw run, summarize it, and observe that the public
    CLI rejects altered raw evidence before it can produce a summary.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Inputs

    This script has its own temporary workspace, policy fixture, and loopback
    matrix fixture. It teaches CLI outcomes and evidence identity fields without
    promising that the internal artifact schema is stable.
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
        summary_path = workspace / "summary.json"
        collect_result = run_local_command(
            (
                str(perfcheck_executable()),
                "collect",
                "--suite",
                str(policy_path),
                "--prometheus-url",
                endpoint,
                "--run-id",
                "lesson-summarize",
                "--start",
                "2026-07-01T10:00:00Z",
                "--end",
                "2026-07-01T10:10:00Z",
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
        raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
        summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
        raw_payload["run_id"] = "altered-raw-run"
        _ = raw_path.write_text(json.dumps(raw_payload), encoding="utf-8")
        tampered_result = run_local_command(
            (
                str(perfcheck_executable()),
                "summarize",
                "--policy",
                str(policy_path),
                "--run",
                str(raw_path),
                "--out",
                str(workspace / "rejected-summary.json"),
            ),
            cwd=workspace,
        )
    evidence = {
        "summary_id": summary_payload["summary_id"],
        "source_run_id": summary_payload["source_run_id"],
        "metric_record_count": len(summary_payload["metric_records"]),
        "eligibility": summary_payload["metric_records"][0]["summary"]["eligibility"][
            "eligible"
        ],
        "tampered_raw_exit_status": tampered_result.returncode,
    }
    return collect_result, evidence, summarize_result


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Run

    The public `summarize` command reads the raw run and verifies its persisted
    identities before writing a canonical summary. A second summarize attempt
    uses an altered raw file and is expected to fail safely.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Evidence

    This narrowed excerpt displays the summary and source identifiers, the
    number of summarized metric records, and the nonzero status from the altered
    raw-run probe. These are evidence fields, not a promise of schema stability.
    """)
    return


@app.cell
def _(collect_result, evidence, summarize_result):
    print("Goal: summarize verified raw evidence")
    print("Inputs: independently collected temporary raw run")
    print(
        f"Run: collect={collect_result.returncode}, summarize={summarize_result.returncode}"
    )
    print(f"Evidence: {evidence}")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Takeaway

    Summarization is not just formatting: it accepts verified raw evidence and
    rejects a tampered artifact with the documented input-error outcome.
    """)
    return


@app.cell
def _():
    print("Takeaway: summarize only trusted raw evidence through perfcheck.")
    return


if __name__ == "__main__":
    app.run()
