"""Explain per-run summary mathematics and eligibility with fixed toy data."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


with app.setup:
    import math
    import sys
    from datetime import UTC, datetime, timedelta
    from pathlib import Path

    import numpy as np

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))

    from examples._markdown import md


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
# Per-run summaries and eligibility

## Goal

Use fixed timestamped toy data to make each supported per-run summary family
visible, then separate an eligible run from a rejected one with explicit
evidence. The supported production interface remains `perfcheck summarize`;
this lesson demonstrates formulas and diagnostics only.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Inputs

The deliberately unordered raw observations span 90 seconds. We sort by UTC
timestamp before analysis, trim an inclusive 15-second warmup and cooldown,
then summarize the five retained values. These toy calculations do **not**
reproduce raw-artifact identity checks, schema validation, finite-value checks,
or duplicate-timestamp validation.
        """)


@app.cell
def _() -> tuple[datetime, datetime, int, tuple[tuple[datetime, float], ...]]:
    source_start = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    source_end = source_start + timedelta(seconds=90)
    step_seconds = 15
    raw_samples = (
        (source_start + timedelta(seconds=90), 30.0),
        (source_start + timedelta(seconds=45), 10.0),
        (source_start, 2.0),
        (source_start + timedelta(seconds=60), 14.0),
        (source_start + timedelta(seconds=30), 6.0),
        (source_start + timedelta(seconds=75), 20.0),
        (source_start + timedelta(seconds=15), 4.0),
    )
    return source_start, source_end, step_seconds, raw_samples


@app.cell
def _(
    raw_samples: tuple[tuple[datetime, float], ...],
    source_end: datetime,
    source_start: datetime,
    step_seconds: int,
) -> tuple[
    datetime, datetime, int, tuple[tuple[datetime, float], ...], tuple[float, ...]
]:
    analysis_start = source_start + timedelta(seconds=step_seconds)
    analysis_end = source_end - timedelta(seconds=step_seconds)
    ordered_samples = tuple(sorted(raw_samples, key=lambda sample: sample[0]))
    retained_samples = tuple(
        sample
        for sample in ordered_samples
        if analysis_start <= sample[0] <= analysis_end
    )
    retained_values = tuple(sample[1] for sample in retained_samples)
    expected_points = (
        math.floor((analysis_end - analysis_start).total_seconds() / step_seconds) + 1
    )
    return (
        analysis_end,
        analysis_start,
        expected_points,
        retained_samples,
        retained_values,
    )


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Run: summary families

For the retained values \(x_i\), quantiles use NumPy's `linear` method. The
sample standard deviation uses Bessel's correction, \(s =
\sqrt{\sum_i (x_i - \bar{x})^2 / (n - 1)}\). Slope is least-squares value per
second against the ordered retained timestamps:

\[
\hat{\beta}_1 =
\frac{\sum_i(t_i-\bar{t})(x_i-\bar{x})}{\sum_i(t_i-\bar{t})^2}.
\]

`first`, `last`, and `delta` therefore mean time order—not input order.
        """)


@app.cell
def _(
    analysis_start: datetime,
    retained_samples: tuple[tuple[datetime, float], ...],
    retained_values: tuple[float, ...],
) -> tuple[tuple[str, ...]]:
    values: np.ndarray[tuple[int], np.dtype[np.float64]] = np.array(
        retained_values, dtype=np.float64
    )
    mean = math.fsum(retained_values) / len(retained_values)
    p50 = float(np.quantile(values, 0.50, method="linear"))
    p90 = float(np.quantile(values, 0.90, method="linear"))
    p95 = float(np.quantile(values, 0.95, method="linear"))
    p99 = float(np.quantile(values, 0.99, method="linear"))
    sample_standard_deviation = math.sqrt(
        math.fsum((value - mean) ** 2 for value in retained_values)
        / (len(retained_values) - 1)
    )
    seconds = tuple(
        (timestamp - analysis_start).total_seconds()
        for timestamp, _ in retained_samples
    )
    mean_seconds = math.fsum(seconds) / len(seconds)
    slope_numerator = math.fsum(
        (second - mean_seconds) * (value - mean)
        for second, value in zip(seconds, retained_values, strict=True)
    )
    slope_denominator = math.fsum((second - mean_seconds) ** 2 for second in seconds)
    slope = slope_numerator / slope_denominator
    summary_labels = (
        f"mean={mean:.2f}",
        f"p50={p50:.2f}",
        f"p90={p90:.2f}",
        f"p95={p95:.2f}",
        f"p99={p99:.2f}",
        f"min={min(retained_values):.2f}",
        f"max={max(retained_values):.2f}",
        f"std_sample={sample_standard_deviation:.5f}",
        f"first={retained_values[0]:.2f}",
        f"last={retained_values[-1]:.2f}",
        f"delta={retained_values[-1] - retained_values[0]:.2f}",
        f"slope_per_second={slope:.5f}",
    )
    return (summary_labels,)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Eligibility evidence

The inclusive analysis window has expected point count
\(\lfloor\mathrm{duration}/\mathrm{step}\rfloor + 1\); coverage is retained
points divided by that count. We also measure the leading, largest adjacent,
and trailing timestamp gaps. Here the eligible run has full coverage and no
gap larger than one 15-second step. The rejected run omits the middle point:
it still has 80% coverage, but its 30-second adjacent gap exceeds the allowed
15 seconds, so its evidence reason is `gap_too_large`.

Eligibility gates precede cohort comparison. A rejected value is neither a
cohort observation nor an imputed replacement.
        """)


@app.cell
def _(
    analysis_end: datetime,
    analysis_start: datetime,
    expected_points: int,
    retained_samples: tuple[tuple[datetime, float], ...],
    step_seconds: int,
) -> tuple[str, str]:
    analysis_seconds = (analysis_end - analysis_start).total_seconds()
    retained_count = len(retained_samples)
    coverage = retained_count / expected_points
    adjacent_gaps = tuple(
        (retained_samples[index][0] - retained_samples[index - 1][0]).total_seconds()
        for index in range(1, retained_count)
    )
    leading_gap = (retained_samples[0][0] - analysis_start).total_seconds()
    trailing_gap = (analysis_end - retained_samples[-1][0]).total_seconds()
    eligible_evidence = ", ".join(
        (
            "eligible=true",
            "reason=none",
            f"window_seconds={analysis_seconds:.0f}",
            f"points={retained_count}/{expected_points}",
            f"coverage={coverage:.2f}",
            f"gaps={leading_gap:.0f}/{max(adjacent_gaps):.0f}/{trailing_gap:.0f}s",
        )
    )
    rejected_samples = (
        retained_samples[0],
        retained_samples[1],
        retained_samples[3],
        retained_samples[4],
    )
    rejected_adjacent_gap = max(
        (rejected_samples[index][0] - rejected_samples[index - 1][0]).total_seconds()
        for index in range(1, len(rejected_samples))
    )
    rejected_coverage = len(rejected_samples) / expected_points
    rejected_evidence = (
        "eligible=false, reason=gap_too_large, "
        f"points={len(rejected_samples)}/{expected_points}, "
        f"coverage={rejected_coverage:.2f}, "
        f"max_adjacent_gap={rejected_adjacent_gap:.0f}s > allowed={step_seconds}s"
    )
    return eligible_evidence, rejected_evidence


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Evidence

The receipt below is fixed: it labels every summary family, records the
timestamp-trimmed analysis window, and states both the eligible evidence and
the precise rejection rationale.
        """)


@app.cell
def _(
    analysis_end: datetime,
    analysis_start: datetime,
    eligible_evidence: str,
    rejected_evidence: str,
    summary_labels: tuple[str, ...],
) -> None:
    analysis_window = f"{analysis_start.isoformat()}..{analysis_end.isoformat()}"
    message = "\n".join(
        (
            "Goal: explain deterministic per-run summaries and eligibility",
            "Inputs: fixed UTC samples, 15-second step, inclusive warmup/cooldown",
            f"Run: analysis_window={analysis_window}",
            f"Evidence: {', '.join(summary_labels)}",
            f"Eligible evidence: {eligible_evidence}",
            f"Rejected evidence: {rejected_evidence}",
        )
    )
    _ = sys.stdout.write(f"{message}\n")


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Takeaway

Use the selected statistic only after timestamp ordering, inclusive trimming,
and the policy eligibility gates have established a comparable per-run value.
        """)


@app.cell
def _() -> None:
    _ = sys.stdout.write(
        "Takeaway: rejected evidence is excluded from comparison, never imputed.\n"
    )


if __name__ == "__main__":
    _app_run_result = app.run()
