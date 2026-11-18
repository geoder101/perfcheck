"""Trace the internal comparison flow end to end."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


with app.setup:
    import contextlib
    import io
    import sys
    from dataclasses import dataclass, replace
    from pathlib import Path

    import marimo as mo

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))

    from examples._comparison import (
        BootstrapOptions,
        Cohort,
        ComparisonMethod,
        Direction,
        MetricComparisonInput,
        MetricLike,
        PolicyLike,
        RunRecord,
        bootstrap_cohort,
        comparison_fingerprint,
        demonstrate,
        eligible_cohort,
        reference_cohort,
        run_record,
        select_comparison,
    )
    from examples._inference_controls import lab_slider
    from examples._markdown import md

    @dataclass(frozen=True, slots=True)
    class CohortScenario:
        """Raw current and baseline run records before orientation and selection."""

        current: dict[str, RunRecord]
        baseline: dict[str, RunRecord]
        current_value: float
        current_count: int
        baseline_count: int

    decisions_page = "https://geoder101.github.io/perfcheck/explanation/decisions-and-limitations.html"
    eligibility_page = "https://geoder101.github.io/perfcheck/explanation/eligibility-and-comparability.html"
    comparison_page = "https://geoder101.github.io/perfcheck/explanation/uncertainty-and-comparison.html"
    inference_page = (
        "https://geoder101.github.io/perfcheck/explanation/inference-and-power.html"
    )
    multiplicity_page = (
        "https://geoder101.github.io/perfcheck/explanation/multiple-testing.html"
    )
    mechanics_page = (
        "https://geoder101.github.io/perfcheck/explanation/plain-python-mechanics.html"
    )


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    # Internal comparison trace

    ## Goal

    Follow the production `compare` decision flow top to bottom through a
    faithful educational mirror: orient cohorts, classify eligibility, select a
    method, resample with PCG64, take an advisory reference tail, and aggregate
    enabled outcomes. The trace is teaching material; the CLI is the only
    supported surface and decides the real PASS/FAIL verdicts.

    ## Inputs

    One enabled `latency` metric in milliseconds with a practical threshold of
    5. Baseline is ten constant runs at 10.0. Current cohorts are pinned
    constants on distinct, non-overlapping daily intervals: 5.0 x5 and 16.0 x5
    for the cohort-bootstrap PASS and FAIL cases, and a single 16.0 run for the
    advisory reference case. Every run shares one metric fingerprint and policy
    hash so the cohorts are comparable. Seed is 42 and one metric is enabled.

    ## Run

    A disabled metric is inconclusive. A missing or ineligible run is excluded
    at the eligibility gate. Fewer than five current runs is
    `insufficient_current_runs`. One current run routes to the advisory baseline
    reference tail; five or more routes to cohort bootstrap. The bootstrap draws
    interleaved PCG64 current-then-baseline means, selects a linear lower bound
    at effective alpha 0.05/m for `m` enabled metrics, and decides FAIL only
    when that strict bound exceeds the threshold — equality passes. The
    reference tail is advisory and stays INCONCLUSIVE. Enabled outcomes
    aggregate as FAIL over INCONCLUSIVE over PASS.

    ## Evidence

    The fixed receipt below prints every supported case — disabled, missing,
    ineligible, inconclusively comparable, advisory reference, and the
    cohort-bootstrap PASS and FAIL in both directions — with its inputs and
    outputs. The laboratory below recomputes the trace as the controls move.
    """)


@app.cell(hide_code=True)
def _() -> None:
    # Fixed receipt: every supported case's inputs and outputs via examples._comparison.
    _header = (
        "Goal: trace the internal comparison flow end to end\n"
        "Inputs: one latency metric (ms), threshold 5, pinned constant "
        "cohorts, seed 42, one enabled metric\n"
        "Run: orient, eligible_cohort, select_comparison, "
        "bootstrap/reference, aggregate_status\n"
        "Evidence: each supported case below with its inputs and outputs"
    )
    _ = sys.stdout.write(_header + "\n")
    _buffer = io.StringIO()
    with contextlib.redirect_stdout(_buffer):
        demonstrate()
    _receipt = _buffer.getvalue()
    _ = sys.stdout.write(_receipt)
    mo.output.replace(
        mo.accordion(
            {"Fixed internal comparison trace": mo.plain(_header + "\n" + _receipt)}
        )
    )


@app.cell(hide_code=True)
def _() -> None:
    md("""
    ## Comparison laboratory

    Move the controls to recompute the trace live. Direction flips orientation;
    the current value and the current and baseline run counts change the cohort
    size and effect; the enabled-metric count rescales the effective alpha and
    the resample floor; the seed fixes the PCG64 draws. The interactive receipt
    below recomputes from the same mirror the fixed trace above printed.
    """)


@app.cell(hide_code=True)
def _() -> tuple[
    mo.ui.slider,
    mo.ui.slider,
    mo.ui.slider,
    mo.ui.slider,
    mo.ui.slider,
    mo.ui.slider,
    mo.ui.switch,
]:
    direction = mo.ui.switch(value=False, label="Higher is worse (off: lower is worse)")
    threshold = lab_slider((0.0, 20.0, 0.25), 5.0, "Practical threshold (ms)")
    current_value = lab_slider((0.0, 30.0, 0.5), 5.0, "Current value (ms)")
    current_count = lab_slider((1, 10, 1), 5, "Current runs")
    baseline_count = lab_slider((1, 20, 1), 10, "Baseline runs")
    enabled = lab_slider((1, 20, 1), 1, "Enabled metrics m")
    seed = lab_slider((0, 20260850, 1), 42, "PCG64 seed")
    mo.output.replace(
        mo.vstack(
            [
                direction,
                threshold,
                current_value,
                current_count,
                baseline_count,
                enabled,
                seed,
            ]
        )
    )
    return (
        threshold,
        current_value,
        current_count,
        baseline_count,
        enabled,
        seed,
        direction,
    )


@app.cell(hide_code=True)
def _(
    baseline_count: mo.ui.slider,
    current_count: mo.ui.slider,
    current_value: mo.ui.slider,
) -> tuple[CohortScenario]:
    _current_value = float(current_value.value)
    _current_count = int(current_count.value)
    _baseline_count = int(baseline_count.value)
    _current = {
        f"current-{index}": run_record(
            f"current-{index}", _current_value, day=1 + index
        )
        for index in range(_current_count)
    }
    _baseline = {
        f"baseline-{index}": run_record(f"baseline-{index}", 10.0, day=100 + index)
        for index in range(_baseline_count)
    }
    cohort = CohortScenario(
        current=_current,
        baseline=_baseline,
        current_value=_current_value,
        current_count=_current_count,
        baseline_count=_baseline_count,
    )
    return (cohort,)


@app.cell(hide_code=True)
def _(
    cohort: CohortScenario,
    direction: mo.ui.switch,
    enabled: mo.ui.slider,
    seed: mo.ui.slider,
    threshold: mo.ui.slider,
) -> None:
    _direction = "higher_is_worse" if direction.value else "lower_is_worse"
    _policy = PolicyLike(
        metrics=tuple(
            MetricLike(
                f"metric-{index + 1}",
                "q",
                "ms",
                (
                    Direction.HIGHER_IS_WORSE
                    if direction.value
                    else Direction.LOWER_IS_WORSE
                ),
                "mean",
                float(threshold.value),
            )
            for index in range(int(enabled.value))
        )
    )
    _current_cohort = eligible_cohort(cohort.current, cohort=Cohort.CURRENT)
    _baseline_cohort = eligible_cohort(cohort.baseline, cohort=Cohort.BASELINE)
    _all_fingerprints = tuple(
        comparison_fingerprint(_policy, _metric) for _metric in _policy.metrics
    )
    _current_inputs = tuple(
        replace(ci, metric_fingerprints=tuple(_all_fingerprints))
        for ci in _current_cohort.comparison_inputs
    )
    _baseline_inputs = tuple(
        replace(ci, metric_fingerprints=tuple(_all_fingerprints))
        for ci in _baseline_cohort.comparison_inputs
    )
    _selection = select_comparison(_policy, _current_inputs, _baseline_inputs)
    _metric = _policy.metrics[0]
    _metric_input = MetricComparisonInput(
        metric_id=_metric.metric_id,
        direction=_metric.direction,
        requested_alpha=_policy.nominal_alpha,
        effective_alpha=_selection.alpha_effective,
        practical_threshold=_metric.practical_threshold,
        current=_current_cohort.run_values,
        baseline=_baseline_cohort.run_values,
        sample_size_warning=_selection.small_cohort_warning,
    )
    if _selection.method is None:
        _status = "INCONCLUSIVE"
        _method = None
        _evidence = None
        _bound = (
            f"reason={_selection.reason.value}"
            if _selection.reason is not None
            else "reason=None"
        )
    elif _selection.method == ComparisonMethod.BASELINE_REFERENCE:
        _evidence = reference_cohort(_metric_input)
        _status = "INCONCLUSIVE"
        _method = _selection.method
        _bound = (
            f"reference_quantile={_evidence.reference_quantile:.3f}; "
            f"reference_effect={_evidence.reference_effect:.3f}; "
            f"anomaly={_evidence.reference_anomaly}"
        )
    else:
        _method = _selection.method
        _options = BootstrapOptions(
            seed=int(seed.value), enabled_metric_count=int(enabled.value)
        )
        _evidence = bootstrap_cohort(_metric_input, _options)
        _status = (
            "FAIL"
            if _evidence.lower_decision_bound > _metric.practical_threshold
            else "PASS"
        )
        _bound = (
            f"observed_effect={_evidence.observed_effect:.3f}; "
            f"lower_decision_bound={_evidence.lower_decision_bound:.6f}; "
            f"strict {_evidence.lower_decision_bound:.6f} "
            f"> {_metric.practical_threshold:.3f} -> {_status}"
        )
    _interactive = (
        f"Interactive trace: direction={_direction}; "
        f"threshold={_metric.practical_threshold:g}; "
        f"current={cohort.current_value:g} x{cohort.current_count}; "
        f"baseline x{cohort.baseline_count}; enabled={int(enabled.value)}; "
        f"seed={int(seed.value)}; effective_alpha={_selection.alpha_effective:.5f}; "
        f"method={_selection.method}; {_bound}"
    )
    _ = sys.stdout.write(_interactive + "\n")
    _live_trace = (
        f"### Live trace — {_status}\n\n"
        f"{_interactive}\n\n"
        "Move any control to recompute. This is educational output; "
        "the CLI decides real perfcheck verdicts."
    )
    mo.output.replace(mo.md(_live_trace))


@app.cell(hide_code=True)
def _() -> None:
    md("""
    ## Line-level reference map

    Each mirror function maps to one production entry point in `src/perfcheck`.
    Production names can differ from the mirror (for example, `oriented` maps to
    `oriented_float64_values`); the file and line locate each one exactly.

    | Mirror function | Production file:line |
    | --- | --- |
    | `oriented` | `src/perfcheck/bootstrap_sampling.py:76` |
    | `bootstrap_cohort` | `src/perfcheck/bootstrap_sampling.py:25` |
    | `eligible_cohort` | `src/perfcheck/regression_cohorts.py:21` |
    | `select_comparison` | `src/perfcheck/policy.py:80` |
    | `reference_cohort` | `src/perfcheck/bootstrap_reference.py:15` |
    | `evaluate_flow` | `src/perfcheck/regression_metrics.py:25` |
    | `aggregate_status` | `src/perfcheck/regression_aggregation.py:13` |
    """)


@app.cell(hide_code=True)
def _() -> None:
    md(f"""
    ## Explanation cross-links

    Conceptual pages for each traced case:

    - Disabled metric excluded → [Eligibility and comparability]({eligibility_page}).
    - Missing / ineligible run withheld at the gate →
      [Eligibility and comparability]({eligibility_page}).
    - Inconclusively comparable cohorts →
      [Eligibility and comparability]({eligibility_page}).
    - Cohort bootstrap PASS/FAIL at the strict threshold →
      [Decisions and limitations]({decisions_page}).
    - Advisory baseline reference tail →
      [Uncertainty and comparison]({comparison_page}).
    - Effective alpha split across enabled metrics →
      [Multiple testing]({multiplicity_page}).
    - Orientation and linear quantile arithmetic →
      [Plain-Python mechanics]({mechanics_page}).
    - Effect size, uncertainty and the decision bound →
      [Inference and power]({inference_page}).
    """)


@app.cell(hide_code=True)
def _() -> None:
    md(f"""
    ## Theory references

    The whole flow rests on these chapters:

    - [Decisions and limitations]({decisions_page}) — the verdict contract, the
      strict equality-passes rule, and FAIL>INCONCLUSIVE>PASS aggregation.
    - [Eligibility and comparability]({eligibility_page}) — admission gates that
      record a reason and never impute a replacement value.
    - [Uncertainty and comparison]({comparison_page}) — orientation,
      comparable cohorts, the percentile-bootstrap bound, and the advisory tail.
    - [Inference and power]({inference_page}) — effect size, uncertainty, and the
      distinction between a teaching model and the product decision.
    - [Multiple testing]({multiplicity_page}) — why effective alpha divides by the
      enabled-metric count.
    - [Plain-Python mechanics]({mechanics_page}) — the orientation and quantile
      arithmetic the mirror reproduces.
    """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
    ## Takeaway

    This trace is teaching material only. The CLI is the only supported surface:
    it collects, summarizes, and compares real artifacts under one policy and
    decides the real PASS/FAIL verdicts. These educational mirrors follow the
    algorithm but change neither the product nor its policy.
    """)
    _ = sys.stdout.write(
        "Takeaway: teaching trace only; the CLI decides real perfcheck verdicts.\n"
    )


if __name__ == "__main__":
    _app_run_result = app.run()
