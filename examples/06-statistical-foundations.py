"""Teach deterministic statistical foundations for reading performance evidence."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


with app.setup:
    import math
    import sys
    from itertools import combinations
    from pathlib import Path

    import numpy as np

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))

    from examples._markdown import md


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
# Statistical foundations

## Goal

Separate a **population** from a **sample** and its realized values, then use
location, spread, empirical distribution functions, quantiles, and repeated
sampling to describe what a single observed cohort can and cannot tell us.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Inputs

The population is a fixed eight-value reference set. The four-value sample is
one fixed realization from it, so every displayed calculation is repeatable:

\[
\text{population} = (8, 9, 10, 11, 12, 13, 14, 15),
\qquad \text{realization} = (8, 9, 12, 15).
\]
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
    _formatted_standard_deviation = f"{realization_standard_deviation:.3f}"
    _standard_deviation_label = "realization sample standard deviation"
    evidence_lines = (
        "; ".join(
            (
                f"Evidence: population mean {population_mean:.3f}",
                f"realization mean {realization_mean:.3f}",
                f"{_standard_deviation_label} {_formatted_standard_deviation}",
            )
        ),
        "; ".join(
            (
                f"Evidence: F_n({evaluation_point:.1f}) = {empirical_cdf:.3f}",
                f"q25 = {quartiles[0]:.3f}",
                f"q50 = {quartiles[1]:.3f}",
                f"q75 = {quartiles[2]:.3f}",
            )
        ),
        "; ".join(
            (
                f"Evidence: {len(sampling_means)} size-3 sample means",
                f"sampling-distribution center {sampling_distribution_mean:.3f}",
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

The sample realization has its own descriptive statistics. The sampling
distribution is different: it summarizes how the mean varies across all
possible equal-sized samples, not variation among the four observed values.
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
def _() -> None:
    md(r"""
## Takeaway

A realization is only one sample from a population. Describe its location and
spread, inspect its empirical CDF and quantiles, then remember that a sampling
distribution describes the uncertainty of a statistic across repeated samples.
        """)


@app.cell
def _() -> None:
    _first_clause = "Takeaway: a sampling distribution describes a statistic across"
    _second_clause = "repeated samples, not the spread within one realization."
    _ = sys.stdout.write(f"{_first_clause} {_second_clause}\n")


if __name__ == "__main__":
    _app_run_result = app.run()
