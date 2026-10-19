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
    # Summarize verified evidence

    ## Goal

    Independently collect a raw run, summarize it, and observe that the public
    CLI rejects altered raw evidence before it can produce a summary.
    """
    )
    return  # noqa: PLR1711


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Inputs

    This script has its own temporary workspace, policy fixture, and loopback
    matrix fixture. It teaches CLI outcomes and evidence identity fields without
    promising that the internal artifact schema is stable.
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
        summary_path = workspace / "summary.json"  # pyright: ignore[reportUnknownVariableType]
        collect_result = run_local_command(  # pyright: ignore[reportUnknownVariableType]
            (
                str(perfcheck_executable()),  # pyright: ignore[reportUnknownArgumentType]
                "collect",
                "--suite",
                str(policy_path),  # pyright: ignore[reportUnknownArgumentType]
                "--prometheus-url",
                endpoint,
                "--run-id",
                "lesson-summarize",
                "--start",
                "2026-07-01T10:00:00Z",
                "--end",
                "2026-07-01T10:10:00Z",
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
        raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        raw_payload["run_id"] = "altered-raw-run"
        _ = raw_path.write_text(json.dumps(raw_payload), encoding="utf-8")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        tampered_result = run_local_command(  # pyright: ignore[reportUnknownVariableType]
            (
                str(perfcheck_executable()),  # pyright: ignore[reportUnknownArgumentType]
                "summarize",
                "--policy",
                str(policy_path),  # pyright: ignore[reportUnknownArgumentType]
                "--run",
                str(raw_path),  # pyright: ignore[reportUnknownArgumentType]
                "--out",
                str(workspace / "rejected-summary.json"),  # pyright: ignore[reportUnknownArgumentType]
            ),
            cwd=workspace,
        )
    evidence = {  # pyright: ignore[reportUnknownVariableType]
        "summary_id": summary_payload["summary_id"],
        "source_run_id": summary_payload["source_run_id"],
        "metric_record_count": len(summary_payload["metric_records"]),  # pyright: ignore[reportUnknownArgumentType]
        "eligibility": summary_payload["metric_records"][0]["summary"]["eligibility"][
            "eligible"
        ],
        "tampered_raw_exit_status": tampered_result.returncode,  # pyright: ignore[reportUnknownMemberType]
    }
    return collect_result, evidence, summarize_result  # pyright: ignore[reportUnknownVariableType]


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Run

    The public `summarize` command reads the raw run and verifies its persisted
    identities before writing a canonical summary. A second summarize attempt
    uses an altered raw file and is expected to fail safely.
    """
    )
    return  # noqa: PLR1711


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Evidence

    This narrowed excerpt displays the summary and source identifiers, the
    number of summarized metric records, and the nonzero status from the altered
    raw-run probe. These are evidence fields, not a promise of schema stability.
    """
    )
    return  # noqa: PLR1711


@app.cell  # pyright: ignore[reportUnknownArgumentType]
def _(collect_result, evidence, summarize_result):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    print("Goal: summarize verified raw evidence")  # noqa: T201
    print("Inputs: independently collected temporary raw run")  # noqa: T201
    print(  # noqa: T201
        f"Run: collect={collect_result.returncode}, summarize={summarize_result.returncode}"  # noqa: E501  # pyright: ignore[reportUnknownMemberType]
    )
    print(f"Evidence: {evidence}")  # noqa: T201
    return  # noqa: PLR1711


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Takeaway

    Summarization is not just formatting: it accepts verified raw evidence and
    rejects a tampered artifact with the documented input-error outcome.
    """
    )
    return  # noqa: PLR1711


@app.cell
def _():  # noqa: ANN202
    print("Takeaway: summarize only trusted raw evidence through perfcheck.")  # noqa: T201
    return  # noqa: PLR1711


if __name__ == "__main__":
    app.run()  # pyright: ignore[reportUnusedCallResult]
