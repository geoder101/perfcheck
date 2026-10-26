"""Expose statistical mechanics with deterministic educational Python formulas."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


with app.setup:
    import math
    import sys
    from pathlib import Path

    import marimo

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))

    from examples._markdown import md
    from examples._mechanics import (
        linear_quantile,
        mean,
        orient,
        resample_means,
        sample_variance,
        slope,
    )
    from examples._probability import PlotSeries, plot_svg


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
# Plain-Python mechanics

## Goal

Read the arithmetic behind lessons 06-08 without hiding it in array operations.
These small educational helpers are not a production implementation or an API.
The supported product surface remains the perfcheck CLI.

## Inputs

Reuse lesson 07's finite values `(4, 6, 10, 14, 20)` at elapsed seconds
`(0, 15, 30, 45, 60)`. For lower-is-worse throughput, baseline is `(30, 25, 35)`
and current is `(20, 22, 24)`. Fix baseline seed 42, current seed 43, and
32 resamples per cohort.

## Run

Mean uses `math.fsum(x) / n`. Linear quantiles sort values, locate
\(h=(n-1)q\), and interpolate the adjacent order statistics. Sample variance
uses \(s^2=\sum(x_i-\bar x)^2/(n-1)\); SD is `math.sqrt(squared_spread)`.
Slope divides centered cross-products by centered squared elapsed seconds.

Orientation leaves higher-is-worse values unchanged and negates lower-is-worse
values, so current mean minus baseline mean is positive for worsening.
Each resample draws n values with replacement. Subtract independent current
and baseline resample means, then select linear percentiles: effective alpha
for the lower decision bound, and 0.025/0.975 for diagnostic bounds.

`random.Random` bootstrap draws are educational and neither bitwise nor
evidence-compatible with production NumPy PCG64. Two separately seeded streams
here are also not production's interleaved current/baseline draw order. The
32 draws omit production's resample floor and do not establish a CI verdict.

## Evidence

The receipt checks transparent arithmetic, not persisted perfcheck evidence.
For a single current value, subtract the baseline's oriented upper-tail
quantile at `1 - effective_alpha`. A strict effect greater than the threshold
flags an advisory anomaly only: reference mode remains INCONCLUSIVE, not a CI
or an alternate PASS/FAIL path. See the companion Explanation page for limits.
        """)


@app.cell
def _() -> None:
    _values = (4.0, 6.0, 10.0, 14.0, 20.0)
    _seconds = (0.0, 15.0, 30.0, 45.0, 60.0)
    _baseline = orient((30.0, 25.0, 35.0), lower_is_worse=True)
    _current = orient((20.0, 22.0, 24.0), lower_is_worse=True)
    _baseline_means = resample_means(_baseline, 42, 32)
    _current_means = resample_means(_current, 43, 32)
    _differences = tuple(
        current - baseline
        for current, baseline in zip(_current_means, _baseline_means, strict=True)
    )
    _alpha = 0.05 / 2
    _reference = linear_quantile(_baseline, 1.0 - _alpha)
    _reference_effect = _current[0] - _reference
    _threshold = 5.0
    _message = "\n".join(
        (
            "Goal: expose plain-Python statistical mechanics",
            (
                "Inputs: finite lesson-07 values; throughput cohorts; "
                "seeds=42/43; draws=32"
            ),
            "Run: fsum, linear interpolation, n-1, sqrt, least squares, seeded draws",
            (
                f"Evidence: mean={mean(_values):.3f}; "
                f"q90={linear_quantile(_values, 0.9):.3f}; "
                f"variance={sample_variance(_values):.3f}; "
                f"sd={math.sqrt(sample_variance(_values)):.6f}; "
                f"slope={slope(_seconds, _values):.6f}"
            ),
            f"Evidence: current resample means first3={_current_means[:3]}",
            (
                f"Evidence: oriented_effect={mean(_current) - mean(_baseline):.3f}; "
                f"lower_bound={linear_quantile(_differences, _alpha):.6f}; "
                f"diagnostic_bounds=({linear_quantile(_differences, 0.025):.6f}, "
                f"{linear_quantile(_differences, 0.975):.6f}); "
                "decision_q=0.025; diagnostic_q=(0.025, 0.975)"
            ),
            (
                f"Evidence: reference_quantile={_reference:.3f}; "
                f"reference_effect={_reference_effect:.3f}; "
                f"anomaly={_reference_effect > _threshold}; "
                "status=INCONCLUSIVE (advisory only)"
            ),
            (
                "Evidence: random.Random is not bitwise or evidence-compatible "
                "with production NumPy PCG64; no perfcheck verdict"
            ),
        )
    )
    _ = sys.stdout.write(f"{_message}\n")


@app.cell(hide_code=True)
def _() -> tuple[marimo.ui.slider, marimo.ui.checkbox]:
    quantile_q = marimo.ui.slider(
        0.0, 1.0, step=0.05, value=0.9, label="Linear quantile q", show_value=True
    )
    lower_direction = marimo.ui.checkbox(
        value=True, label="Lower throughput is worse (negate before sorting)"
    )
    marimo.output.replace(marimo.vstack([quantile_q, lower_direction]))
    return quantile_q, lower_direction


@app.cell(hide_code=True)
def _(quantile_q: marimo.ui.slider, lower_direction: marimo.ui.checkbox) -> None:
    _ordered = tuple(
        sorted(orient((30.0, 25.0, 35.0), lower_is_worse=lower_direction.value))
    )
    _q = quantile_q.value
    _quantile = linear_quantile(_ordered, _q)
    _position = (len(_ordered) - 1) * _q
    _chart = plot_svg(
        (
            "Oriented order statistics",
            "Sorted index h (zero based)",
            "Oriented throughput (requests/s)",
        ),
        (
            PlotSeries(
                "solid: sorted oriented values",
                tuple((float(i), value) for i, value in enumerate(_ordered)),
            ),
            PlotSeries(
                "dot: selected interpolated quantile", ((_position, _quantile),)
            ),
        ),
    )
    md(f"""
### Interpolation and orientation laboratory
Sorted oriented values: `{_ordered}` requests/s. h=(n-1)q={_position:.3f};
neighbors {_ordered[math.floor(_position)]:.3f} and
{_ordered[math.ceil(_position)]:.3f}; interpolated q={_q:.2f} value:
**{_quantile:.3f} requests/s**. Negation reverses the order: an upper
oriented quantile is the negative of a lower original quantile, not the
negative of the original upper quantile. This is arithmetic, not a verdict.
""")
    marimo.output.append(marimo.Html(_chart))
    _ = sys.stdout.write(
        f"Interactive mechanics: q={_q:.2f}; lower_is_worse={lower_direction.value}\n"
    )


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Takeaway

Equivalent formulas agree numerically on these finite toy inputs; different
random generators do not produce interchangeable bootstrap evidence. Finite
input checks are not full eligibility, provenance, or numerical-overflow guards.
Use the CLI for verified evidence and policy decisions, not these helpers.
        """)
    _ = sys.stdout.write(
        "Takeaway: understand formulas here; use the CLI for verified evidence.\n"
    )


if __name__ == "__main__":
    _app_run_result = app.run()
