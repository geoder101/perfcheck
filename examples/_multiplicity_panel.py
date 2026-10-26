"""Reactive independent-family multiplicity evidence with known synthetic truth."""

from typing import TYPE_CHECKING, Final, assert_never

import marimo as mo
from pydantic import TypeAdapter

from examples._inference_plots import PlotSpec, Series, line_plot
from examples._multiple_testing import Method, independent_fwer, simulate_families

_METHOD_LABEL: Final = TypeAdapter[Method](Method)

if TYPE_CHECKING:
    from examples._multiple_testing import FamilyExperiment


def selected_method(label: str) -> Method:
    """Parse the native method tab's label at the UI boundary."""
    return _METHOD_LABEL.validate_python(label, strict=True)


def multiplicity_panel(inputs: FamilyExperiment) -> mo.Html:
    """Show one family's adjusted decisions plus repeated-family error estimates."""
    result = simulate_families(inputs)
    first = result.families[0]
    match inputs.method:
        case "none":
            guarantee = "No family-wise correction is applied."
        case "Bonferroni" | "Holm":
            guarantee = (
                "Controls FWER at alpha for valid marginal p-values, "
                "including arbitrary dependence."
            )
        case "BH":
            guarantee = (
                "BH controls FDR under independent valid p-values (also certain "
                "positive dependence conditions); not arbitrary dependence. "
                "It does not control FWER."
            )
        case _:
            assert_never(inputs.method)
    table = "\n".join(
        (
            f"| {index + 1} | {'true' if index < inputs.true_nulls else 'false'} | "
            f"{p:.5f} | {adjusted:.5f} | {'reject' if rejected else 'retain'} |"
        )
        for index, (p, adjusted, rejected) in enumerate(
            zip(first.pvalues, first.adjusted, first.rejected, strict=True)
        )
    )
    series = (
        Series(
            "Raw p: solid",
            tuple((float(i + 1), p) for i, p in enumerate(first.pvalues)),
        ),
        Series(
            "Adjusted p: dashed",
            tuple((float(i + 1), p) for i, p in enumerate(first.adjusted)),
        ),
        Series(
            "alpha cutoff: dotted",
            ((1.0, inputs.alpha), (float(inputs.size), inputs.alpha)),
        ),
    )
    model = (
        f"**Family size {inputs.size}: {inputs.true_nulls} true nulls, "
        f"{inputs.size - inputs.true_nulls} false nulls.** "
        f"{inputs.method}. {guarantee}\n\n"
        "Simulation: independent Z~N(0,1) for true nulls, Z~N(3,1) "
        "for false nulls; right-tail p=Phi(-Z). First indices are true "
        "nulls. Families and tests are independent; no dependence claim is simulated."
    )
    evidence = (
        f"First family: **FDP={first.fdp:.3f}**, false rejections "
        f"{first.false_rejections}, total rejected {sum(first.rejected)}. "
        "FDP=V/max(R,1). Retain is not proof of H0.\n\n"
        f"Across {inputs.repetitions} families: **FWER={result.fwer:.3f}** "
        f"(MC SE {result.fwer_mc_se:.3f}); **mean FDP={result.mean_fdp:.3f}** "
        f"(FDR estimate; MC SE {result.fdr_mc_se:.3f}). "
        "Plug-in SEs can be zero at finite-sample extremes: zero observed "
        "errors is not proof of zero risk. One realization's FDP is not its FDR.\n\n"
        "Independent all-null unadjusted reference 1-(1-alpha)^m="
        f"{independent_fwer(inputs.size, inputs.alpha):.6f}; "
        f"Bonferroni alpha/m={inputs.alpha / inputs.size:.6f}. "
        "At m=20, alpha=.05: .641514 and .0025. "
        "Educational choices never alter perfcheck policy.\n\n"
        "| Test | H0 true? | Raw p | Adjusted p | Decision (p <= alpha) |\n"
        "|---:|:---|---:|---:|:---|\n"
    )
    return mo.vstack(
        [
            mo.md(model),
            mo.Html(
                line_plot(
                    PlotSpec(
                        "First family's adjusted decisions",
                        "Hypothesis (original index)",
                        "p-value (probability)",
                    ),
                    series,
                )
            ),
            mo.md(evidence + table),
        ]
    )
