"""Explore oriented bootstrap decisions and a separate known-sigma CI experiment."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")

with app.setup:
    import math
    import sys
    from pathlib import Path

    import marimo as mo

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))

    from examples._inference import (
        BootstrapExperiment,
        CoverageExperiment,
        bootstrap_experiment,
        coverage_experiment,
    )
    from examples._inference_controls import lab_slider
    from examples._inference_plots import PlotSpec, histogram, interval_plot
    from examples._markdown import md


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    # Bootstrap evidence and decisions

    ## Goal

    Change a run-level cohort, inspect the **actual bootstrap distribution**, and
    distinguish its one-sided percentile decision bound from repeated-sampling
    confidence-interval coverage. These educational calculations are not a new
    product engine: use the CLI for validated perfcheck decisions.

    ## Inputs

    Baseline throughput is `(100,99,101,100)` units/s. The current cohort starts
    at `(90,89,91,90)` units/s. The shift control adds the same raw units/s to
    every current observation. With lower-is-worse, orientation is \(y=-x\), so
    positive current-minus-baseline effect means worsening.

    ## Run

    Orient both cohorts, then resample current followed by baseline in each
    PCG64 draw. Use float64 means and a linear percentile at effective alpha
    0.05/m, with at least 2000*m draws. Compare the lower bound strictly with
    the practical threshold: equality passes. The controls below recompute
    the actual distribution; the later known-sigma experiment is separate.
    """)


@app.cell
def _(bootstrap_seed: mo.ui.slider) -> None:
    md(f"Exact PCG64 seed: **{int(bootstrap_seed.value)}**")


@app.cell(hide_code=True)
def _(
    bootstrap_seed: mo.ui.slider,
    direction: mo.ui.switch,
    enabled: mo.ui.slider,
    shift: mo.ui.slider,
    threshold: mo.ui.slider,
) -> None:
    _inputs = BootstrapExperiment(
        current=tuple(x + float(shift.value) for x in (90.0, 89.0, 91.0, 90.0)),
        higher_is_worse=direction.value,
        enabled=int(enabled.value),
        seed=int(bootstrap_seed.value),
        threshold=float(threshold.value),
    )
    _result = bootstrap_experiment(_inputs)
    _alpha = 0.05 / _inputs.enabled
    _direction = "higher_is_worse" if direction.value else "lower_is_worse"
    _receipt = "\n".join(
        (
            "Goal: evaluate oriented percentile-bootstrap evidence",
            (
                f"Inputs: direction={_direction}; requested_alpha=0.050; "
                f"effective_alpha={_alpha:.3f}; seed={_inputs.seed}; "
                f"requested_resamples=1000; effective_resamples={len(_result.draws)}"
            ),
            "Run: PCG64 float64, current then baseline per draw; linear quantile",
            (
                f"Bootstrap PASS/FAIL decision: oriented_effect={_result.effect:.3f}; "
                f"lower_bound={_result.lower:.3f}; "
                f"strict comparison {_result.lower:.3f} "
                f"> {_inputs.threshold:.3f}; verdict={_result.verdict}"
            ),
            "Strict threshold note: equality with the threshold would PASS, not FAIL.",
            (
                f"Reference advisory: reference_effect={_result.reference_effect:.3f}; "
                f"anomaly={_result.reference_anomaly}; verdict=INCONCLUSIVE "
                "(advisory only; no perfcheck verdict)"
            ),
            (
                "Classical contrast only: "
                f"Welch t={(-10 + float(shift.value)) / math.sqrt(1 / 3):.3f}; "
                "p-value not computed; no perfcheck verdict; "
                "perfcheck does not calculate t-tests or p-values"
            ),
        )
    )
    _ = sys.stdout.write(_receipt + "\n")
    _evidence = (
        f"## Evidence\nEffect **{_result.effect:.3f} units/s**; "
        f"lower bound **{_result.lower:.3f}**; threshold **{_inputs.threshold:g}**. "
        f"Strict-rule demonstration: **{_result.verdict}**. "
        "Equality passes. Reference stays **INCONCLUSIVE**, even when anomalous."
    )
    _assumptions = (
        f"Effective alpha={_alpha:.5f}; resamples={len(_result.draws)}. "
        "IID independent runs within each cohort; no pairing "
        "or time dependence. This finite seeded distribution has "
        "Monte Carlo error. It does not establish nominal coverage "
        "for every population. The min-resample floor is 2000 * m, "
        "not a coverage guarantee."
    )
    mo.output.replace(
        mo.vstack(
            [
                mo.md(_evidence),
                mo.Html(
                    histogram(
                        _result.draws,
                        PlotSpec(
                            "Actual percentile bootstrap",
                            "Oriented effect (units/s)",
                            "Draws (count)",
                        ),
                        (_result.lower, "Lower decision bound"),
                    )
                ),
                mo.md(_assumptions),
            ]
        )
    )


@app.cell(hide_code=True)
def _() -> tuple[mo.ui.slider, mo.ui.switch, mo.ui.slider, mo.ui.slider, mo.ui.slider]:
    direction = mo.ui.switch(value=False, label="Higher is worse (off: lower is worse)")
    shift = lab_slider((-15, 20, 1), 0, "Current shift (units/s)")
    threshold = lab_slider((0, 20, 0.25), 3, "Practical threshold (units/s)")
    enabled = lab_slider((1, 20, 1), 2, "Enabled metrics m")
    bootstrap_seed = lab_slider((0, 20260850, 1), 20260808, "PCG64 seed")
    mo.output.replace(mo.vstack([direction, shift, threshold, enabled, bootstrap_seed]))
    return bootstrap_seed, direction, enabled, shift, threshold


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## A different question — repeated confidence intervals

    Model: IID Normal observations, true mean **100 ms**, **known population
    sigma**. Each repetition draws a fresh mean from its exact sampling law
    \(\bar X\sim N(100,\sigma^2/n)\), then forms
    \(\bar X\pm z_{(1+c)/2}\sigma/\sqrt n\).
    The fixed mean is either contained or missed by each realized interval.
    **This is not percentile-bootstrap coverage or perfcheck validation.**
    """)


@app.cell
def _() -> tuple[mo.ui.slider, mo.ui.slider, mo.ui.slider, mo.ui.slider]:
    ci_n = lab_slider((2, 100, 1), 25, "CI sample size n")
    ci_sigma = lab_slider((1, 30, 1), 10, "Known sigma (ms)")
    ci_confidence = lab_slider((0.80, 0.99, 0.01), 0.95, "Nominal confidence")
    ci_repetitions = lab_slider((32, 512, 32), 128, "CI repetitions")
    mo.output.replace(mo.vstack([ci_n, ci_sigma, ci_confidence, ci_repetitions]))
    return ci_confidence, ci_n, ci_repetitions, ci_sigma


@app.cell(hide_code=True)
def _(
    ci_confidence: mo.ui.slider,
    ci_n: mo.ui.slider,
    ci_repetitions: mo.ui.slider,
    ci_sigma: mo.ui.slider,
) -> None:
    _inputs = CoverageExperiment(
        n=int(ci_n.value),
        sigma=float(ci_sigma.value),
        confidence=float(ci_confidence.value),
        repetitions=int(ci_repetitions.value),
    )
    _result = coverage_experiment(_inputs)
    _message = (
        f"Known-sigma CI: achieved coverage={_result.coverage:.4f}; "
        f"nominal={_inputs.confidence:.4f}; MC SE={_result.mc_se:.4f}; "
        f"repetitions={_inputs.repetitions}; seed=42; no perfcheck verdict"
    )
    _ = sys.stdout.write(_message + "\n")
    _explanation = (
        f"**Achieved coverage {_result.coverage:.1%} versus nominal "
        f"{_inputs.confidence:.1%}**, over all {_inputs.repetitions} repetitions. "
        f"Monte Carlo SE: {_result.mc_se:.2%} "
        "(plug-in binomial estimate; rough +/-2 SE is not exact). "
        "Chart shows the first 40 only. Seed 42 fixes the "
        "demonstration, not the general coverage rate. Coverage "
        "is a property of the procedure under this model, not a "
        "probability that a fixed parameter changes between repetitions."
    )
    mo.output.replace(
        mo.vstack(
            [
                mo.Html(interval_plot(_result)),
                mo.md(_explanation),
            ]
        )
    )


@app.cell(hide_code=True)
def _() -> None:
    md("""
    ## Takeaway

    Only validated oriented bootstrap evidence feeds the CLI policy decision.
    Reference anomalies stay advisory; known-sigma CI coverage is a distinct,
    explicitly modeled experiment, not evidence of bootstrap calibration.
    """)
    _takeaway = (
        "Takeaway: only the oriented bootstrap bound can produce "
        "a perfcheck PASS or FAIL.\n"
    )
    _ = sys.stdout.write(_takeaway)


if __name__ == "__main__":
    _app_run_result = app.run()
