"""Contrast four educational questions without creating perfcheck verdicts."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


with app.setup:
    import math
    import sys
    from pathlib import Path
    from statistics import mean, variance

    import numpy as np
    import numpy.typing as npt

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))

    from examples._markdown import md

    def mean_difference(
        current: npt.NDArray[np.float64], baseline: npt.NDArray[np.float64]
    ) -> float:
        """Measure current-minus-baseline means for each label allocation."""
        return float(np.mean(current) - np.mean(baseline))


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
# Comparative methods

## Goal

Ask four different statistical questions without turning any answer into a
perfcheck policy decision. This is educational arithmetic, not a new CLI mode.

## Inputs

Welch/t and permutation use independent toy run-level values: current
`(4, 5, 6)`, baseline `(1, 2, 3)`. Ranks use current `(2, 3, 3)` and baseline
`(1, 2, 4)` to expose ties. Bayesian framing uses indicators `(1, 1, 1, 0)`
for exceeding a fixed, predeclared latency cutoff, with a Beta(1,1) prior.
These are invented finite data, not external observations or verified artifacts.

## Run

### Welch/t

Question: how far apart are the means in estimated standard-error units?
Assumptions: independent run-level samples with finite variance; normal
populations or an adequate approximation are needed for a usual t-tail reading.
Welch uses separate sample variances, not an equal-variance pooled estimator:
\(t=(\bar c-\bar b)/\sqrt{s_c^2/n_c+s_b^2/n_b}\).
Its Welch--Satterthwaite degrees of freedom are approximate. Equal sample
variances happen in this fixture, but the formula does not require them.
No Welch p-value is reported; a statistic is not a practical-effect decision.
Welch/t does not determine perfcheck PASS/FAIL and does not change product policy.

### Seeded permutation

Question: is the current-minus-baseline mean difference unusually large under
independent label relabeling? Assumptions: exchangeability under the null,
justified by the sampling/randomization design; dependent runs cannot simply
be relabeled. Perform 15 random label allocations with PCG64 seed 42,
preserving group sizes, without replacement *within* an allocation. Allocations
can repeat across draws. This is not a with-replacement bootstrap.
Use the greater tail, including equality. Following the standard plus-one
Monte Carlo convention, add one to the extreme count and draw count: resolution
is only 1/16 here. This transparent toy calculation is not a reusable test API.
This deliberately coarse teaching result is not a production p-value routine,
the probability the null is true, proof of causality, or an equivalence claim.
Permutation does not determine perfcheck PASS/FAIL and does not change product policy.

### Mann--Whitney ranks

Question: how often does a current observation outrank a baseline observation?
Assumptions: independent samples with meaningful ordering. Pool observations,
assign average ranks to ties, and subtract n_current*(n_current+1)/2 from the
current rank sum to obtain U. U/(n_current*n_baseline) is the observed pairwise
win fraction with half credit for ties. It is not automatically a median test;
a pure location-shift interpretation needs common distributional shapes.
No rank-test p-value is computed, and ranks discard magnitude information.
Mann--Whitney does not determine perfcheck PASS/FAIL and does not change product policy.

### Bayesian posterior

Question: given the indicators, likelihood and prior, what is theta, the
exceedance probability? Assumptions: IID Bernoulli observations at one fixed
cutoff, constant theta, and the chosen Beta(1,1) prior. Conjugacy gives
Beta(1+3,1+1)=Beta(4,2). Its mean is 4/6; integrating density
20*theta^3*(1-theta) gives CDF(x)=5*x^4-4*x^5. Hence
Pr(theta>0.5)=13/16. No simulation or MCMC is needed.
This is conditional on the model and prior, not the probability of regression,
not a posterior on a mean difference, and not a bootstrap confidence statement.
Bayesian does not determine perfcheck PASS/FAIL and does not change product policy.

## Evidence

The script receipt repeats each method's dataset, question, assumptions,
computed result and non-verdict boundary. See the linked comparative-methods
Explanation chapter for interpretation, sources and limits.
        """)


@app.cell
def _() -> None:
    _current = (4.0, 5.0, 6.0)
    _baseline = (1.0, 2.0, 3.0)
    _current_term = variance(_current) / len(_current)
    _baseline_term = variance(_baseline) / len(_baseline)
    _t = (mean(_current) - mean(_baseline)) / math.sqrt(_current_term + _baseline_term)
    _df = (_current_term + _baseline_term) ** 2 / (
        _current_term**2 / (len(_current) - 1)
        + _baseline_term**2 / (len(_baseline) - 1)
    )
    _generator = np.random.Generator(np.random.PCG64(42))
    _permutation_pool = np.asarray(_current + _baseline, dtype=np.float64)
    _observed = mean(_current) - mean(_baseline)
    _null = tuple(
        mean_difference(_allocation[:3], _allocation[3:])
        for _allocation in (
            _generator.permutation(_permutation_pool) for _ in range(15)
        )
    )
    _extreme = sum(value >= _observed for value in _null)
    _monte_carlo_p = (_extreme + 1) / (len(_null) + 1)
    _rank_current = (2.0, 3.0, 3.0)
    _rank_baseline = (1.0, 2.0, 4.0)
    _pooled = _rank_current + _rank_baseline
    _ranks = tuple(
        1.0
        + sum(other < value for other in _pooled)
        + (sum(other == value for other in _pooled) - 1) / 2
        for value in _pooled
    )
    _rank_sum = math.fsum(_ranks[: len(_rank_current)])
    _u = _rank_sum - len(_rank_current) * (len(_rank_current) + 1) / 2
    _pairwise_score = _u / (len(_rank_current) * len(_rank_baseline))
    _indicators = (1, 1, 1, 0)
    _posterior_a = 1 + sum(_indicators)
    _posterior_b = 1 + len(_indicators) - sum(_indicators)
    _posterior_mean = _posterior_a / (_posterior_a + _posterior_b)
    _posterior_tail = 1 - (5 * 0.5**4 - 4 * 0.5**5)
    _boundary = "does not determine perfcheck PASS/FAIL; does not change product policy"
    _message = "\n".join(
        (
            "Goal: contrast statistical questions, not perfcheck verdicts",
            "Inputs: fixed toy datasets; PCG64 seed=42; no external data",
            "Run: Welch statistic, seeded permutation, tied ranks, Beta posterior",
            (
                f"Evidence: Welch t={_t:.6f}; df={_df:.6f}; "
                "Welch p-value not reported; dataset=current(4,5,6)/baseline(1,2,3); "
                "Question: mean separation in SE units? "
                f"Assumptions: independent samples, appropriate t model; {_boundary}"
            ),
            (
                f"Evidence: Permutation observed={_observed:.3f}; "
                "seed=42; draws=15; "
                f"extreme={_extreme}; Monte Carlo p={_monte_carlo_p:.6f}; "
                f"null={_null}; resolution=1/16; "
                "dataset=current(4,5,6)/baseline(1,2,3); "
                "Question: unusually large mean difference under relabeling? "
                f"Assumptions: null exchangeability; {_boundary}"
            ),
            (
                f"Evidence: Mann--Whitney ranks={_ranks}; "
                f"rank_sum={_rank_sum:.3f}; U={_u:.3f}; "
                f"pairwise_score={_pairwise_score:.6f}; "
                "dataset=current(2,3,3)/baseline(1,2,4); "
                "Question: current outranks baseline? "
                "Assumptions: independent ordered samples; "
                f"not automatically a median test; {_boundary}"
            ),
            (
                f"Evidence: Bayesian posterior=Beta({_posterior_a},{_posterior_b}); "
                f"mean={_posterior_mean:.6f}; Pr(theta>0.5)={_posterior_tail:.6f}; "
                "dataset=indicators(1,1,1,0); prior=Beta(1,1); "
                "Question: exceedance probability given model and prior? "
                f"Assumptions: IID Bernoulli, fixed cutoff and theta; {_boundary}"
            ),
        )
    )
    _ = sys.stdout.write(f"{_message}\n")


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Takeaway

Different questions require different assumptions and interpretations. None of
these four results is a perfcheck decision. Only the CLI's validated comparison
and existing policy determine product outcomes; this lesson changes neither.
        """)
    _ = sys.stdout.write(
        "Takeaway: educational contrasts only; use the CLI for policy.\n"
    )


if __name__ == "__main__":
    _app_run_result = app.run()
