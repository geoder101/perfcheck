"""Explain perfcheck bootstrap evidence and decision boundaries."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


with app.setup:
    import math
    import sys
    from pathlib import Path

    import numpy as np
    import numpy.typing as npt

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))

    from examples._markdown import md

    type LessonInputs = tuple[
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
        float,
        int,
        int,
        int,
        float,
    ]
    type BootstrapEvidence = tuple[float, float, str, float, bool, str]
    type ClassicalContrast = tuple[float]


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    # Bootstrap evidence and decisions

    ## Goal

    Inspect a transparent, reproducible bootstrap demonstration, then contrast
    it with advisory reference evidence and a classical test. This lesson is not
    an alternate implementation: the supported perfcheck surface remains its CLI.
    For a lower-is-worse metric, orientation is \(y=-x\), so a positive effect
    \(\Delta=\bar y_{current}-\bar y_{baseline}\) means worsening.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Inputs

    The fixed throughput cohorts below are lower-is-worse. The nominal
    \(\alpha=0.05\) is divided across two enabled metrics, giving effective
    \(\alpha=0.025\). A fixed PCG64 seed and requested resample count make the
    with-replacement cohort draws reproducible. The displayed floor reproduces
    the documented demonstration semantics without calling product internals.
        """)


@app.cell
def _() -> tuple[LessonInputs]:
    baseline = np.asarray((100.0, 99.0, 101.0, 100.0), dtype=np.float64)
    current = np.asarray((90.0, 89.0, 91.0, 90.0), dtype=np.float64)
    requested_alpha = 0.05
    enabled_metric_count = 2
    effective_alpha = requested_alpha / enabled_metric_count
    seed = 20260808
    requested_resamples = 1000
    effective_resamples = max(requested_resamples, 2000 * enabled_metric_count)
    practical_threshold = 3.0
    lesson_inputs: LessonInputs = (
        baseline,
        current,
        effective_alpha,
        effective_resamples,
        requested_resamples,
        seed,
        practical_threshold,
    )
    return (lesson_inputs,)


@app.cell
def _(lesson_inputs: LessonInputs) -> tuple[BootstrapEvidence]:
    (
        _baseline,
        _current,
        _effective_alpha,
        _effective_resamples,
        _,
        _seed,
        _practical_threshold,
    ) = lesson_inputs
    _oriented_baseline = -_baseline
    _oriented_current = -_current
    _generator = np.random.Generator(np.random.PCG64(_seed))
    _differences = np.asarray(
        tuple(
            float(
                np.mean(
                    _oriented_current[
                        _generator.integers(
                            0,
                            len(_oriented_current),
                            size=len(_oriented_current),
                        )
                    ],
                ),
            )
            - float(
                np.mean(
                    _oriented_baseline[
                        _generator.integers(
                            0,
                            len(_oriented_baseline),
                            size=len(_oriented_baseline),
                        )
                    ],
                ),
            )
            for _ in range(_effective_resamples)
        ),
        dtype=np.float64,
    )
    _oriented_effect = float(np.mean(_oriented_current) - np.mean(_oriented_baseline))
    _lower_decision_bound = float(
        np.quantile(_differences, _effective_alpha, method="linear"),
    )
    _bootstrap_verdict = (
        "FAIL" if _lower_decision_bound > _practical_threshold else "PASS"
    )
    _reference_quantile = float(
        np.quantile(
            _oriented_baseline,
            1.0 - _effective_alpha,
            method="linear",
        ),
    )
    _reference_effect = float(np.mean(_oriented_current[:1]) - _reference_quantile)
    _reference_anomaly = _reference_effect > _practical_threshold
    _reference_status = "INCONCLUSIVE"
    bootstrap_evidence: BootstrapEvidence = (
        _oriented_effect,
        _lower_decision_bound,
        _bootstrap_verdict,
        _reference_effect,
        _reference_anomaly,
        _reference_status,
    )
    return (bootstrap_evidence,)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Run

    This transparent demonstration negates the lower-is-worse inputs, creates
    PCG64 index draws with replacement for each cohort, and subtracts the drawn
    means. Its linear percentile at effective \(\alpha\) is compared strictly:
    \(L_{\alpha}>\tau\) fails, while equality with \(\tau\) passes.
        """)


@app.cell
def _(lesson_inputs: LessonInputs) -> tuple[ClassicalContrast]:
    _baseline, _current, _, _, _, _, _ = lesson_inputs
    _standard_error = math.sqrt(
        float(np.var(_current, ddof=1) / len(_current))
        + float(np.var(_baseline, ddof=1) / len(_baseline)),
    )
    _welch_t_statistic = float(np.mean(_current) - np.mean(_baseline)) / _standard_error
    classical_contrast: ClassicalContrast = (_welch_t_statistic,)
    return (classical_contrast,)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Evidence

    The reference demonstration compares one current observation against the
    upper-tail oriented baseline quantile. It can flag an anomaly but is always
    **INCONCLUSIVE** and cannot yield a perfcheck pass or fail. Separately, the
    Welch t-statistic and p-value concepts are classical contrast material; this
    lesson does not compute a p-value, and neither concept creates a perfcheck
    verdict.
        """)


@app.cell
def _(
    bootstrap_evidence: BootstrapEvidence,
    classical_contrast: ClassicalContrast,
    lesson_inputs: LessonInputs,
) -> None:
    (
        _oriented_effect,
        _lower_decision_bound,
        _bootstrap_verdict,
        _reference_effect,
        _reference_anomaly,
        _reference_status,
    ) = bootstrap_evidence
    (_welch_t_statistic,) = classical_contrast
    _, _, _, _effective_resamples, _requested_resamples, _seed, _practical_threshold = (
        lesson_inputs
    )
    message = "\n".join(
        (
            "Goal: evaluate oriented percentile-bootstrap evidence",
            (
                "Inputs: direction=lower_is_worse; requested_alpha=0.050; "
                "effective_alpha=0.025; "
                f"seed={_seed}; requested_resamples={_requested_resamples}; "
                f"effective_resamples={_effective_resamples}"
            ),
            (
                "Bootstrap PASS/FAIL decision: "
                f"oriented_effect={_oriented_effect:.3f}; "
                f"lower_bound={_lower_decision_bound:.3f}; "
                f"strict comparison {_lower_decision_bound:.3f} "
                f"> {_practical_threshold:.3f}; verdict={_bootstrap_verdict}"
            ),
            "Strict threshold note: equality with the threshold would PASS, not FAIL.",
            (
                "Reference advisory: "
                f"reference_effect={_reference_effect:.3f}; "
                f"anomaly={_reference_anomaly}; verdict={_reference_status} "
                "(advisory only; no perfcheck verdict)"
            ),
            (
                "Classical contrast only: "
                f"Welch t={_welch_t_statistic:.3f}; p-value not computed; "
                "no perfcheck verdict; "
                "perfcheck does not calculate t-tests or p-values"
            ),
        ),
    )
    _ = sys.stdout.write(f"{message}\n")


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Takeaway

    Perfcheck's verdict comes from the seeded, oriented percentile bound and its
    strict practical-threshold comparison. Reference evidence and classical
    inference remain explanatory contrasts, not alternate decision paths.
        """)


@app.cell
def _() -> None:
    _takeaway = (
        "Takeaway: only the oriented bootstrap bound can produce a perfcheck "
        "PASS or FAIL.\n"
    )
    _ = sys.stdout.write(
        _takeaway,
    )


if __name__ == "__main__":
    _app_run_result = app.run()
