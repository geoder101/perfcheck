"""Reactive inference, power and multiplicity contrasts; never product verdicts."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


with app.setup:
    import sys
    from pathlib import Path

    import marimo as mo

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))

    from examples._comparative_receipts import comparative_receipt
    from examples._inference_controls import lab_slider
    from examples._markdown import md
    from examples._multiple_testing import FamilyExperiment
    from examples._multiplicity_panel import multiplicity_panel, selected_method
    from examples._power import NullExperiment, PowerExperiment
    from examples._power_panels import (
        normal_tail_panel,
        null_model_panel,
        power_model_panel,
    )


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    # Comparative methods

    ## Goal

    Ask different statistical questions without turning any answer into a
    perfcheck decision. The laboratories are educational models, not CLI modes.

    ## Inputs

    Independent toy run-level values: current `(4,5,6)`, baseline `(1,2,3)`.
    Ranks use current `(2,3,3)`, baseline `(1,2,4)` to expose ties.
    Bayesian framing uses fixed-cutoff indicators `(1,1,1,0)` and a Beta(1,1) prior.
    These are invented values, not verified artifacts or external observations.

    ## Run

    - **Welch/t:** separate sample variances, not equal-variance pooling.
      \(t=(\bar c-\bar b)/\sqrt{s_c^2/n_c+s_b^2/n_b}\).
      Independent runs, finite variances and a suitable normal/large-sample
      approximation support a usual t-tail reading. Welch-Satterthwaite df is
      approximate. Here t=3.674235, df=4; no Welch p-value is reported.
    - **Permutation:** exchangeability under the null must follow from the
      sampling/randomization design; dependent runs cannot simply be relabeled.
      Greater-tail mean difference includes equality. All 20 group-size-preserving
      allocations give exact p=1/20. The separate PCG64 seed-42 experiment draws
      15 allocations (which can repeat), with no replacement within each one:
      plus-one MC p=(1+1)/(15+1)=.125, resolution 1/16. Not a bootstrap, posterior
      null probability, causality result, or equivalence claim.
    - **Mann-Whitney:** average ranks for ties give U=5.5. U/9 is the pairwise
      win fraction with half credit for ties; ordering and independent samples
      are required. Not automatically a median test: a location-shift reading
      needs common distributional shapes. Ranks discard magnitude; no p-value.
    - **Bayesian:** IID Bernoulli indicators at a predeclared cutoff, fixed theta,
      Beta(1,1) prior yield Beta(4,2), mean 4/6. Integrating
      \(20\theta^3(1-\theta)\) gives CDF \(5x^4-4x^5\), so
      Pr(theta&gt;.5)=13/16. Conditional on model and prior; not a posterior on
      mean regression, not a bootstrap confidence statement.

    ## Evidence

    The calculated receipt below preserves the four methods' assumptions and
    non-verdict boundaries. Then explore normal tails, calibration, power and
    independent families. None of these educational methods determines perfcheck
    PASS/FAIL or changes product policy.
    """)


@app.cell
def _() -> None:
    _receipt = comparative_receipt()
    _ = sys.stdout.write(_receipt + "\n")
    mo.output.replace(
        mo.accordion({"Calculated comparative receipts": mo.plain(_receipt)})
    )


@app.cell
def _() -> None:
    mo.output.replace(normal_tail_panel())


@app.cell(hide_code=True)
def _() -> None:
    md("""
    ## Null p-value calibration laboratory

    Predict: which empirical curve should track the uniform diagonal, which
    should lie below it in expectation, and which model violates calibration?
    Change the seed and repetition budget to distinguish sampling noise from
    systematic model misspecification.
    """)


@app.cell
def _() -> tuple[mo.ui.slider, mo.ui.slider]:
    null_repetitions = lab_slider((32, 512, 32), 128, "Null repetitions")
    null_seed = lab_slider((0, 1000, 1), 42, "Null PCG64 seed")
    mo.output.replace(mo.vstack([null_repetitions, null_seed]))
    return null_repetitions, null_seed


@app.cell
def _(null_repetitions: mo.ui.slider, null_seed: mo.ui.slider) -> None:
    mo.output.replace(
        null_model_panel(
            NullExperiment(
                repetitions=int(null_repetitions.value),
                seed=int(null_seed.value),
            )
        )
    )


@app.cell(hide_code=True)
def _() -> None:
    md("""
    ## Power laboratory

    A prespecified **right-tailed** known-sigma design (unlike the earlier
    lower-tailed z example). Move the alternative effect, n, sigma and alpha.
    Predict how alpha (false rejection under H0), beta (non-rejection under
    the alternative),
    and power (rejection under the alternative) change.
    """)


@app.cell
def _() -> tuple[mo.ui.slider, mo.ui.slider, mo.ui.slider, mo.ui.slider]:
    power_effect = lab_slider((-5, 15, 0.25), 4, "Alternative effect (ms)")
    power_n = lab_slider((2, 100, 1), 25, "Power sample size n")
    power_sigma = lab_slider((1, 30, 1), 10, "Power known sigma (ms)")
    power_alpha = lab_slider((0.01, 0.20, 0.01), 0.05, "Test alpha")
    mo.output.replace(mo.vstack([power_effect, power_n, power_sigma, power_alpha]))
    return power_effect, power_n, power_sigma, power_alpha


@app.cell
def _(
    family_repetitions: mo.ui.slider,
    family_seed: mo.ui.slider,
) -> tuple[NullExperiment]:
    family_budget = NullExperiment(
        repetitions=int(family_repetitions.value),
        seed=int(family_seed.value),
    )
    return (family_budget,)


@app.cell
def _(
    power_effect: mo.ui.slider,
    power_n: mo.ui.slider,
    power_sigma: mo.ui.slider,
    power_alpha: mo.ui.slider,
) -> None:
    mo.output.replace(
        power_model_panel(
            PowerExperiment(
                effect=float(power_effect.value),
                n=int(power_n.value),
                sigma=float(power_sigma.value),
                alpha=float(power_alpha.value),
            )
        )
    )


@app.cell(hide_code=True)
def _() -> None:
    md("""
    ## Multiplicity laboratory

    More opportunities to reject can create more false positives. Choose a
    complete family, its true-null count (remaining nulls are false), and a
    correction. Read **adjusted decisions**, realized FDP, repeated-family FWER,
    and mean FDP separately. No dependence toggle is offered: this model is
    deliberately independent, and BH has conditional—not universal—guarantees.
    """)


@app.cell
def _() -> tuple[mo.ui.slider, mo.ui.slider, mo.ui.tabs, mo.ui.slider, mo.ui.slider]:
    family_size = lab_slider((1, 40, 1), 20, "Family size m")
    family_alpha = lab_slider((0.01, 0.20, 0.01), 0.05, "Family alpha")
    family_method = mo.ui.tabs(
        {
            "none": mo.md("Unadjusted: test each p-value against alpha."),
            "Bonferroni": mo.md("Multiply each p-value by the family size."),
            "Holm": mo.md("Step-down adjustment for family-wise error."),
            "BH": mo.md("Step-up adjustment for false discovery rate."),
        },
        value="none",
        label="Adjustment",
    )
    family_repetitions = lab_slider((32, 512, 32), 128, "Independent families")
    family_seed = lab_slider((0, 1000, 1), 42, "Family PCG64 seed")
    mo.output.replace(
        mo.vstack(
            [family_size, family_alpha, family_method, family_repetitions, family_seed]
        )
    )
    return family_size, family_alpha, family_method, family_repetitions, family_seed


@app.cell
def _(family_size: mo.ui.slider) -> tuple[mo.ui.slider]:
    family_true = lab_slider(
        (0, int(family_size.value), 1),
        min(15, int(family_size.value)),
        "True nulls (remaining are false)",
    )
    mo.output.replace(family_true)
    return (family_true,)


@app.cell
def _(
    family_size: mo.ui.slider,
    family_alpha: mo.ui.slider,
    family_method: mo.ui.tabs,
    family_budget: NullExperiment,
    family_true: mo.ui.slider,
) -> None:
    mo.output.replace(
        multiplicity_panel(
            FamilyExperiment(
                size=int(family_size.value),
                true_nulls=int(family_true.value),
                alpha=float(family_alpha.value),
                method=selected_method(family_method.value),
                repetitions=family_budget.repetitions,
                seed=family_budget.seed,
            )
        )
    )


@app.cell(hide_code=True)
def _() -> None:
    md("""
    ## Takeaway

    A p-value is not a posterior probability, retaining a null is not proof of
    equivalence, power is model-dependent, and FWER differs from FDR. Different
    questions need different assumptions. Only the CLI's validated comparison
    and existing policy determine product outcomes; this lesson changes neither.
    """)
    _ = sys.stdout.write(
        "Takeaway: educational contrasts only; use the CLI for policy.\n"
    )


if __name__ == "__main__":
    _app_run_result = app.run()
