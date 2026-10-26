"""Native Marimo evidence panels for explicitly modeled inference experiments."""

import math
from typing import TYPE_CHECKING, Final

import marimo as mo

from examples._inference_plots import PlotSpec, Series, line_plot
from examples._power import analytic_power, known_sigma_z, null_pvalues

CALIBRATION_ALPHA: Final = 0.05

if TYPE_CHECKING:
    from examples._power import NullExperiment, PowerExperiment


def normal_tail_panel() -> mo.Html:
    """Show the observed lower tail under a fixed known-sigma null model."""
    result = known_sigma_z(96.0)
    points = tuple(
        (x / 20, math.exp(-0.5 * (x / 20) ** 2) / math.sqrt(2 * math.pi))
        for x in range(-90, 91)
    )
    description = (
        "## Known-sigma z: a tail is not a posterior\n"
        "IID normal observations; null mean 100 ms, known sigma 10 ms, "
        "n=25, observed mean 96 ms. The **prespecified lower-tail** "
        "question is P(Z <= observed z | H0), not P(H0 | data). "
        f"**SE={result.standard_error:g} ms; z={result.z:g}; "
        f"p={result.p:.8f}**. This does not determine perfcheck PASS/FAIL."
    )
    return mo.vstack(
        [
            mo.md(description),
            mo.Html(
                line_plot(
                    PlotSpec(
                        "Known-sigma lower tail",
                        "z (standard-error units)",
                        "Density (1/z unit)",
                    ),
                    (
                        Series("Null N(0,1): solid", points),
                        Series(
                            "Shaded: P(Z ≤ -2)",
                            tuple(p for p in points if p[0] <= result.z),
                            shade=True,
                        ),
                    ),
                    (-2.0, "Observed z = -2"),
                )
            ),
        ]
    )


def null_model_panel(inputs: NullExperiment) -> mo.Html:
    """Compare empirical CDFs to the diagonal with finite-simulation uncertainty."""
    result = null_pvalues(inputs)
    curves = (
        ("Valid continuous: solid", result.continuous),
        ("Coarse conservative: dashed", result.discrete),
        ("Wrong sigma/2: dotted", result.violated),
    )
    grid = tuple(x / 100 for x in range(101))
    series = (
        *tuple(
            Series(
                label,
                tuple((x, sum(p <= x for p in values) / len(values)) for x in grid),
            )
            for label, values in curves
        ),
        Series("Uniform reference: dash-dot", ((0.0, 0.0), (1.0, 1.0))),
    )
    rates = tuple(
        sum(p <= CALIBRATION_ALPHA for p in values) / len(values)
        for _, values in curves
    )
    uncertainty = math.sqrt(0.05 * 0.95 / inputs.repetitions)
    description = (
        f"At alpha=.05: continuous **{rates[0]:.3f}**, "
        f"discrete **{rates[1]:.3f}**, violated **{rates[2]:.3f}**; "
        f"{inputs.repetitions} draws, seed {inputs.seed}. "
        f"Reference MC SE at rate .05 is **{uncertainty:.3f}**.\n\n"
        "**Models:** Z~N(0,1) and p=Phi(-Z) is uniform under H0. "
        "Rounding upward to the next 1/20 yields a discrete, valid "
        "super-uniform p-value (coarsening, not an exact binomial test). "
        "The violated model uses p=Phi(-2Z): true sigma is twice "
        "the assumed sigma. It is anti-conservative even though "
        "the null mean is correct. Curves share matched Z draws; "
        "repetitions are independent. Finite ECDFs need not equal "
        "the diagonal. No result creates a product verdict."
    )
    return mo.vstack(
        [
            mo.Html(
                line_plot(
                    PlotSpec(
                        "Null p-value calibration",
                        "p-value cutoff (probability)",
                        "Fraction ≤ cutoff",
                    ),
                    series,
                )
            ),
            mo.md(description),
        ]
    )


def power_model_panel(inputs: PowerExperiment) -> mo.Html:
    """Plot fixed null and alternative sampling laws with their decision regions."""
    result = analytic_power(inputs)
    se = result.standard_error
    left = min(0.0, inputs.effect) - 4 * se
    right = max(0.0, inputs.effect, result.critical_shift) + 4 * se
    xs = sorted(
        {left + (right - left) * index / 200 for index in range(201)}
        | {result.critical_shift}
    )
    null = tuple(
        (x, math.exp(-0.5 * (x / se) ** 2) / (se * math.sqrt(2 * math.pi))) for x in xs
    )
    alternative = tuple(
        (
            x,
            math.exp(-0.5 * ((x - inputs.effect) / se) ** 2)
            / (se * math.sqrt(2 * math.pi)),
        )
        for x in xs
    )
    description = (
        f"**alpha={inputs.alpha:.3f}; beta={result.beta:.3f}; "
        f"power=1-beta={result.power:.3f}**. "
        f"Critical shift {result.critical_shift:.3f} ms; SE {se:.3f} ms. "
        "Diagonal hatching marks alpha (null right tail); dots mark beta "
        "(alternative left region). The unfilled alternative right tail is power. "
        "Assumptions: IID normal observations, known population sigma, "
        "one prespecified right-tailed test. These are analytic "
        "probabilities, not MC estimates or observed/post-hoc power. "
        "At zero effect power equals alpha; at the critical shift "
        "power is 1/2. Not percentile-bootstrap power or a product verdict."
    )
    return mo.vstack(
        [
            mo.Html(
                line_plot(
                    PlotSpec(
                        "Right-tailed known-sigma power",
                        "Mean shift from H₀ (ms)",
                        "Density (1/ms)",
                    ),
                    (
                        Series("Null: solid", null),
                        Series("Alternative: dashed", alternative),
                        Series(
                            "alpha: null right tail (diagonal hatch)",
                            tuple(p for p in null if p[0] >= result.critical_shift),
                            shade=True,
                        ),
                        Series(
                            "beta: alternative left region (dots)",
                            tuple(
                                p for p in alternative if p[0] <= result.critical_shift
                            ),
                            shade=True,
                        ),
                    ),
                    (result.critical_shift, "Reject to the right"),
                )
            ),
            mo.md(description),
        ]
    )
