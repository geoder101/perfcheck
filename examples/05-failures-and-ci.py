"""Audit a real CLI performance-verification workflow and its CI outcome."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


with app.setup:
    import sys
    from pathlib import Path

    import marimo as mo

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))

    from examples._capstone import CapstoneReceipt, Scenario, run_capstone
    from examples._capstone_evidence import CapstoneReport
    from examples._capstone_view import render_capstone_evidence
    from examples._markdown import md
    from examples._support import parse_summary_evidence


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    # Performance verification: a CLI capstone

    ## Goal

    Ask whether current mean latency is worse than baseline, then trace the
    answer from timestamped observations to eligible per-run summaries and a
    real canonical JSON/Markdown report. Preserve the child exit status for CI.
    Lessons 01-04 introduced each link; here we audit the whole chain.
    """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Inputs

    Select **one** scenario. Pass and regression plan two baseline and two
    current runs; advisory-reference plans two baseline and one current run.
    Each selection starts a fresh temporary workspace and loopback fixture.
    No remote service, benchmark workload, or previous lesson output is used.

    The metric is mean latency in seconds, higher-is-worse, threshold **0 s**.
    Fixture warmup/cooldown are both zero. These reduced minima and constant
    synthetic samples demonstrate plumbing, **not statistical calibration**.
    Unique run IDs and nonoverlapping UTC intervals establish provenance,
    not independence or exchangeability. Labs 06-10 examine those limits.
    """)


@app.cell
def _() -> tuple[mo.ui.dropdown]:
    scenario_selector = mo.ui.dropdown(
        options=[scenario.value for scenario in Scenario],
        value="pass",
        allow_select_none=False,
        label="CLI scenario",
    )
    mo.output.replace(scenario_selector)
    return (scenario_selector,)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Run

    Only the selected workflow executes: public `collect` for each run,
    public `summarize` for each raw artifact, then public `compare` on the
    summaries under the same policy. Bootstrap uses seed 20260705 and requests
    1000 resamples (the engine records its effective floor of 2000).
    Reference receives **neither seed nor resamples**.

    A repeat compare intentionally omits `--force` at the same report paths.
    This is an input error (3), not a regression (1) or uncertainty (2).
    Temporary files and the fixture process are cleaned up on cell completion.
    """)


@app.cell
def _(scenario_selector: mo.ui.dropdown) -> tuple[CapstoneReceipt]:
    receipt = run_capstone(Scenario(scenario_selector.selected_key))
    return (receipt,)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Evidence

    Inspect the actual report fields below: cohort counts, oriented effect,
    alpha, lower decision bound, threshold, method, and stochastic provenance.
    Bootstrap FAIL requires a bound **strictly greater** than the threshold;
    equality is PASS. PASS means the configured rule did not flag regression,
    not proof of equivalence. A reference anomaly is advisory and remains
    INCONCLUSIVE even when the current value is elevated.

    Expected compare statuses: pass **0**, regression **1**, reference **2**.
    The notebook captures them; it does not convert a teaching FAIL to a
    notebook crash or silently relabel INCONCLUSIVE as PASS.
    """)


@app.cell
def _(receipt: CapstoneReceipt) -> None:
    report = CapstoneReport.model_validate_json(receipt.report_json)
    eligibility = tuple(
        parse_summary_evidence(payload)["eligible"]
        for payload in receipt.summary_artifacts
    )
    message = "\n".join(
        (
            "Goal: verify latency through the actual public CLI",
            f"Selected scenario: {receipt.scenario.value}",
            "Inputs: synthetic timestamped loopback observations; temporary outputs",
            (
                f"Run: stages={receipt.stage_statuses}; "
                f"compare={receipt.comparison_status}"
            ),
            (
                f"Evidence: eligible={all(eligibility)}; "
                f"suite_status={report.suite_status}"
            ),
            f"JSON report (temporary): {report.metrics[0].model_dump_json()}",
            f"Markdown report (temporary): {receipt.report_markdown}",
            (
                f"Handled failure: exit status {receipt.overwrite_status} — "
                f"{receipt.overwrite_context}"
            ),
        )
    )
    _ = sys.stdout.write(f"{message}\n")
    mo.output.replace(render_capstone_evidence(receipt))


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Takeaway

    Decide the question, metric direction, meaningful threshold, run plan and
    eligibility rules **before** observing outcomes. Retain real reports and
    investigate a FAIL rather than inferring a cause from a bound. In production,
    plan representative independent runs, realistic warmup/cooldown and a
    domain-justified threshold; do not copy this tiny fixture as a power study.

    Continue with the standalone documentation case study
    `docs/tutorials/performance-verification-case-study.rst` and labs 06-10.
    """)


@app.cell
def _() -> None:
    _ = sys.stdout.write(
        "Takeaway: preserve CLI status; synthetic reproducibility is not validation.\n"
    )


if __name__ == "__main__":
    _app_run_result = app.run()
