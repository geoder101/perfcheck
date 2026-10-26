"""Teach deterministic statistical foundations for reading performance evidence."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


with app.setup:
    import math
    import sys
    from itertools import combinations
    from pathlib import Path
    from statistics import stdev

    import marimo
    import numpy as np

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))

    from examples._markdown import md
    from examples._probability import (
        coin_distribution,
        coin_plot,
        mean_experiment,
        means_plot,
        normal_plots,
        normal_region,
    )


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
# Statistical foundations

## Goal

Separate population, sample, and realization; explore probability, spread,
CDFs, quantiles, and the uncertainty of repeated sample means.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Inputs

Population: `(8, 9, 10, 11, 12, 13, 14, 15)`; one fixed sample realization:
`(8, 9, 12, 15)`. Every displayed reference calculation is repeatable.
        """)


@app.cell
def _() -> tuple[tuple[float, ...], tuple[float, ...], float]:
    population = (8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0)
    realization = (8.0, 9.0, 12.0, 15.0)
    evaluation_point = 11.0
    return population, realization, evaluation_point


@app.cell
def _(
    evaluation_point: float,
    population: tuple[float, ...],
    realization: tuple[float, ...],
) -> tuple[tuple[str, str, str]]:
    population_values: np.ndarray[tuple[int], np.dtype[np.float64]] = np.array(
        population, dtype=np.float64
    )
    realization_values: np.ndarray[tuple[int], np.dtype[np.float64]] = np.array(
        realization, dtype=np.float64
    )
    population_mean = float(np.mean(population_values))
    realization_mean = float(np.mean(realization_values))
    realization_standard_deviation = float(np.std(realization_values, ddof=1))
    empirical_cdf = sum(value <= evaluation_point for value in realization) / len(
        realization
    )
    quartiles = np.quantile(realization_values, (0.25, 0.5, 0.75), method="linear")
    sampling_means = tuple(
        math.fsum(values) / len(values) for values in combinations(population, 3)
    )
    sampling_distribution_mean = math.fsum(sampling_means) / len(sampling_means)
    sampling_distribution_standard_deviation = math.sqrt(
        math.fsum((value - sampling_distribution_mean) ** 2 for value in sampling_means)
        / len(sampling_means)
    )
    _sd_label = "realization sample standard deviation"
    evidence_lines = (
        "".join(
            (
                f"Evidence: population mean {population_mean:.3f}; ",
                f"realization mean {realization_mean:.3f}; ",
                f"{_sd_label} {realization_standard_deviation:.3f}",
            )
        ),
        "".join(
            (
                f"Evidence: F_n({evaluation_point:.1f}) = {empirical_cdf:.3f}; ",
                f"q25 = {quartiles[0]:.3f}; q50 = {quartiles[1]:.3f}; ",
                f"q75 = {quartiles[2]:.3f}",
            )
        ),
        "".join(
            (
                f"Evidence: {len(sampling_means)} size-3 sample means; ",
                f"sampling-distribution center {sampling_distribution_mean:.3f}; ",
                f"standard error {sampling_distribution_standard_deviation:.3f}",
            )
        ),
    )
    return (evidence_lines,)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Run

First compare the mean (location) and sample standard deviation (spread).
Next evaluate the empirical CDF,
\(\widehat F_n(x) = n^{-1}\sum_{i=1}^{n}\mathbf{1}\{X_i \leq x\}\), at
\(x = 11\) and report the 25th, 50th, and 75th percentiles. Finally enumerate
every size-three sample without replacement from the population and examine the
distribution of their means.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Evidence

The sampling distribution describes variation across equal-sized samples,
not variation among the four values in one realization.
        """)


@app.cell
def _(evidence_lines: tuple[str, str, str]) -> None:
    message = "\n".join(
        (
            "Goal: distinguish population, sample, and realization",
            "Inputs: fixed population of 8 values and realization of 4 values",
            "Run: location, spread, empirical CDF, quantiles, and sample means",
            *evidence_lines,
        )
    )
    _ = sys.stdout.write(f"{message}\n")


@app.cell(hide_code=True)
def _() -> tuple[
    marimo.ui.slider, marimo.ui.slider, marimo.ui.slider, marimo.ui.range_slider
]:
    coin_n = marimo.ui.slider(
        1, 40, value=10, label="Fair flips per experiment n", show_value=True
    )
    coin_repetitions = marimo.ui.slider(
        100,
        2000,
        step=100,
        value=1000,
        label="Repeated experiments (seed 601)",
        show_value=True,
    )
    sample_n = marimo.ui.slider(
        steps=[4, 16, 64],
        value=16,
        label="IID observations per sample",
        show_value=True,
    )
    normal_bounds = marimo.ui.range_slider(
        -4.0,
        4.0,
        step=0.1,
        value=(-1.0, 1.0),
        label="Standard normal interval [a, b] (z units)",
        show_value=True,
    )
    marimo.output.replace(
        marimo.vstack([coin_n, coin_repetitions, sample_n, normal_bounds])
    )
    return coin_n, coin_repetitions, sample_n, normal_bounds


@app.cell(hide_code=True)
def _(coin_n: marimo.ui.slider) -> tuple[marimo.ui.slider]:
    coin_heads = marimo.ui.slider(
        0,
        coin_n.value,
        value=min(8, coin_n.value),
        label="Observed heads k (upper-tail cutoff)",
        show_value=True,
    )
    marimo.output.replace(coin_heads)
    return (coin_heads,)


@app.cell(hide_code=True)
def _(
    coin_n: marimo.ui.slider,
    coin_heads: marimo.ui.slider,
    coin_repetitions: marimo.ui.slider,
) -> None:
    _n, _k, _reps = (
        int(coin_n.value),
        int(coin_heads.value),
        int(coin_repetitions.value),
    )
    _mass = coin_distribution(_n)
    _chart = coin_plot(_n, _k, _reps)
    marimo.output.replace(
        marimo.vstack(
            [
                marimo.md(f"""
### Fair-coin bridge to a p-value
Assume independent flips, P(head)=1/2, fixed n, and an **upper-tail rule
chosen before observing data**. For k={_k} of n={_n}, exact mass
P(X=k)={_mass[_k]:.6f}; tail P(X≥k)={math.fsum(_mass[_k:]):.6f}.
At 8/10 the mass is 45/1024, but the tail is **56/1024 ≈ 0.0547**.
A p-value is a probability of data at least as extreme **under a specified
null model**, not the probability that the null is true. A two-sided rule
would select a different region. Simulation approximates, not replaces, the
exact sum; finite seeded estimates need not improve monotonically.
"""),
                marimo.Html(_chart),
            ]
        )
    )
    _ = sys.stdout.write("Evidence: fair coin 8/10 mass=45/1024; upper_tail=56/1024\n")


@app.cell(hide_code=True)
def _(normal_bounds: marimo.ui.range_slider) -> None:
    _low, _high = normal_bounds.value
    _density, _area, _cdf = normal_region((_low, _high))
    _density_chart, _cdf_chart = normal_plots((_low, _high))
    marimo.output.replace(
        marimo.vstack(
            [
                marimo.md(f"""
Discrete probability **sums masses** over selected integers. Continuous
probability **integrates density**: P(a≤Z≤b)=F(b)-F(a)={_area:.4f}.
F(b)={_cdf:.4f}; density at b={_density:.4f} per z unit, not a probability.
P(Z=b)=0.
"""),
                marimo.Html(_density_chart),
                marimo.Html(_cdf_chart),
            ]
        )
    )


@app.cell(hide_code=True)
def _(sample_n: marimo.ui.slider, coin_repetitions: marimo.ui.slider) -> None:
    _experiment = mean_experiment(int(sample_n.value), int(coin_repetitions.value))
    _chart = means_plot(_experiment)
    marimo.output.replace(
        marimo.vstack(
            [
                marimo.md(f"""
### Sample-size experiment: spread is not standard error
Model: IID Normal(100 ms, (8 ms)²), sampling **with replacement** from the
model, fixed RNG seed 602. At n={sample_n.value}, individual sample SD is
{stdev(_experiment.individuals):.3f} ms; empirical SD of repeated means is
{stdev(_experiment.means):.3f} ms; theoretical SE=8/√n=
{_experiment.theoretical_se:.3f} ms. Try n=4,16,64. Individual variability
does not vanish when a mean becomes more precise. This differs from the
finite-population, without-replacement enumeration above; independence and
finite variance are assumptions, not gifts of a large reading count.
The explanation above works offline. Companion source (open in your checkout):
<code>docs/explanation/<wbr>probability-and-distributions.rst</code>
"""),
                marimo.Html(_chart),
            ]
        )
    )


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Takeaway

A realization is one sample: describe its spread, CDF, and quantiles.
A sampling distribution describes a statistic across repeated samples.
        """)


@app.cell
def _() -> None:
    _first_clause = "Takeaway: a sampling distribution describes a statistic across"
    _second_clause = "repeated samples, not the spread within one realization."
    _ = sys.stdout.write(f"{_first_clause} {_second_clause}\n")


if __name__ == "__main__":
    _app_run_result = app.run()
