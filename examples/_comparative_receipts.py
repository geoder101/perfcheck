"""Preserved deterministic arithmetic receipts for the comparative lesson."""

import math
from itertools import combinations
from statistics import mean, variance

import numpy as np

from examples._power import known_sigma_z


def comparative_receipt() -> str:
    """Calculate each toy method afresh, keeping its assumptions beside its result."""
    current = (4.0, 5.0, 6.0)
    baseline = (1.0, 2.0, 3.0)
    current_term = variance(current) / len(current)
    baseline_term = variance(baseline) / len(baseline)
    t = (mean(current) - mean(baseline)) / math.sqrt(current_term + baseline_term)
    df = (current_term + baseline_term) ** 2 / (
        current_term**2 / (len(current) - 1) + baseline_term**2 / (len(baseline) - 1)
    )
    generator = np.random.Generator(np.random.PCG64(42))
    pool = np.asarray(current + baseline, dtype=np.float64)
    observed = mean(current) - mean(baseline)
    null = tuple(
        float(np.mean(allocation[:3]) - np.mean(allocation[3:]))
        for allocation in (generator.permutation(pool) for _ in range(15))
    )
    extreme = sum(value >= observed for value in null)
    monte_carlo_p = (extreme + 1) / (len(null) + 1)
    exact = tuple((2 * sum(group) - 21) / 3 for group in combinations(range(1, 7), 3))
    exact_p = sum(value >= observed for value in exact) / len(exact)
    rank_current = (2.0, 3.0, 3.0)
    rank_baseline = (1.0, 2.0, 4.0)
    pooled = rank_current + rank_baseline
    ranks = tuple(
        1.0
        + sum(other < value for other in pooled)
        + (sum(other == value for other in pooled) - 1) / 2
        for value in pooled
    )
    rank_sum = math.fsum(ranks[: len(rank_current)])
    u = rank_sum - len(rank_current) * (len(rank_current) + 1) / 2
    pairwise = u / (len(rank_current) * len(rank_baseline))
    indicators = (1, 1, 1, 0)
    a = 1 + sum(indicators)
    b = 1 + len(indicators) - sum(indicators)
    posterior_tail = 1 - (5 * 0.5**4 - 4 * 0.5**5)
    boundary = "does not determine perfcheck PASS/FAIL; does not change product policy"
    z = known_sigma_z(96.0)
    return "\n".join(
        (
            "Goal: contrast statistical questions, not perfcheck verdicts",
            "Inputs: fixed toy datasets; PCG64 seed=42; no external data",
            "Run: Welch statistic, seeded permutation, tied ranks, Beta posterior",
            (
                f"Evidence: Welch t={t:.6f}; df={df:.6f}; "
                "Welch p-value not reported; dataset=current(4,5,6)/baseline(1,2,3); "
                "Question: mean separation in SE units? "
                f"Assumptions: independent samples, appropriate t model; {boundary}"
            ),
            (
                f"Evidence: Permutation observed={observed:.3f}; seed=42; draws=15; "
                f"extreme={extreme}; Monte Carlo p={monte_carlo_p:.6f}; "
                f"null={null}; resolution=1/16; "
                "dataset=current(4,5,6)/baseline(1,2,3); "
                "Question: unusually large mean difference under relabeling? "
                f"Assumptions: null exchangeability; {boundary}"
            ),
            (
                f"Evidence: Mann--Whitney ranks={ranks}; rank_sum={rank_sum:.3f}; "
                f"U={u:.3f}; pairwise_score={pairwise:.6f}; "
                "dataset=current(2,3,3)/baseline(1,2,4); "
                "Question: current outranks baseline? "
                "Assumptions: independent ordered samples; "
                f"not automatically a median test; {boundary}"
            ),
            (
                f"Evidence: Bayesian posterior=Beta({a},{b}); mean={a / (a + b):.6f}; "
                f"Pr(theta>0.5)={posterior_tail:.6f}; "
                "dataset=indicators(1,1,1,0); prior=Beta(1,1); "
                "Question: exceedance probability given model and prior? "
                f"Assumptions: IID Bernoulli, fixed cutoff and theta; {boundary}"
            ),
            (
                f"Exact permutation p={exact_p:.6f}; allocations={len(exact)}; "
                "greater tail includes equality; distinct from plus-one Monte Carlo; "
            )
            + boundary,
            (
                "Known-sigma z: known sigma=10; n=25; null mean=100; observed mean=96; "
                f"SE={z.standard_error:.3f}; z={z.z:.3f}; lower-tail p={z.p:.8f}; "
                "Assumptions: IID normal observations, known population sigma; "
            )
            + boundary,
        )
    )
