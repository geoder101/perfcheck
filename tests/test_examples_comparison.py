"""Focused receipts for the faithful comparison mirror in examples._comparison."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

import pytest
from examples import _comparison
from examples._support import run_local_command

from tests.examples_check import run_standalone_notebook

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_THRESHOLD: Final = 5.0
_REPO_ROOT: Final = Path(__file__).resolve().parents[1]
_LESSON_11: Final = _REPO_ROOT / "examples/11-comparison-internal-trace.py"


@runtime_checkable
class Comparison(Protocol):
    """The transparent comparison-core functions the tests exercise."""

    def oriented(
        self, values: tuple[float, ...], *, higher_is_worse: bool
    ) -> _comparison.FloatVector: ...
    def eligible_cohort(
        self,
        records: Mapping[str, _comparison.RunRecord | None],
        *,
        cohort: _comparison.Cohort,
    ) -> _comparison.EligibleCohort: ...
    def select_comparison(
        self,
        policy: _comparison.PolicyLike,
        current: Sequence[_comparison.ComparisonInput],
        baseline: Sequence[_comparison.ComparisonInput],
    ) -> _comparison.ComparisonSelection: ...
    def bootstrap_cohort(
        self,
        metric_input: _comparison.MetricComparisonInput,
        options: _comparison.BootstrapOptions,
    ) -> _comparison.CohortBootstrapResult: ...
    def reference_cohort(
        self, metric_input: _comparison.MetricComparisonInput
    ) -> _comparison.BaselineReferenceResult: ...
    def evaluate_flow(
        self,
        policy: _comparison.PolicyLike,
        metric: _comparison.MetricLike,
        current_records: Mapping[str, _comparison.RunRecord | None],
        baseline_records: Mapping[str, _comparison.RunRecord | None],
        *,
        seed: int,
    ) -> _comparison.MetricOutcome: ...
    def aggregate_status(
        self, outcomes: tuple[_comparison.MetricOutcome, ...]
    ) -> _comparison.Status: ...


@pytest.fixture
def comparison() -> Comparison:
    """Provide the imported comparison mirror module under its Protocol."""
    assert isinstance(_comparison, Comparison)
    return _comparison


def _policy(direction: _comparison.Direction) -> _comparison.PolicyLike:
    # Given: one enabled metric whose direction and threshold pin the receipts.
    metric = _comparison.MetricLike("latency", "q", "ms", direction, "mean", _THRESHOLD)
    return _comparison.PolicyLike(metrics=(metric,))


def _fingerprint(policy: _comparison.PolicyLike, metric: _comparison.MetricLike) -> str:
    return _comparison.comparison_fingerprint(policy, metric)


def _repeat(value: float, count: int) -> tuple[tuple[str, float], ...]:
    return tuple((f"c{i}", value) for i in range(count))


_BASELINE: Final = tuple((f"baseline-{i}", 10.0) for i in range(10))


def _runs(
    pairs: tuple[tuple[str, float], ...], *, start_day: int, fingerprint: str
) -> dict[str, _comparison.RunRecord]:
    # Build a cohort of distinct runs on non-overlapping daily intervals.
    return {
        run_id: _comparison.run_record(
            run_id, value, day=start_day + index, metric_fingerprint=fingerprint
        )
        for index, (run_id, value) in enumerate(pairs)
    }


def _baseline_cohort(fingerprint: str) -> dict[str, _comparison.RunRecord]:
    return _runs(_BASELINE, start_day=100, fingerprint=fingerprint)


def test_comparison_module_exposes_the_protocol() -> None:
    # Given: the imported comparison mirror.
    # When: it is inspected against the teaching Protocol.
    # Then: every flow function is present.
    assert isinstance(_comparison, Comparison)


@pytest.mark.parametrize("higher_is_worse", [True, False])
def test_cohort_receipt_passes_at_the_exact_threshold_when_constant(
    comparison: Comparison, higher_is_worse: bool
) -> None:
    # Given: constant cohorts separated by exactly the threshold in one direction.
    # higher-is-worse current is 15.0 x5 vs baseline 10.0 x10;
    # lower-is-worse current is 5.0 x5 vs baseline 10.0 x10.
    direction = (
        _comparison.Direction.HIGHER_IS_WORSE
        if higher_is_worse
        else _comparison.Direction.LOWER_IS_WORSE
    )
    policy = _policy(direction)
    metric = policy.metrics[0]
    fingerprint = _fingerprint(policy, metric)
    current_value = 15.0 if higher_is_worse else 5.0
    current = _runs(_repeat(current_value, 5), start_day=1, fingerprint=fingerprint)

    # When: the cohort bootstrap evaluates the enabled metric.
    outcome = comparison.evaluate_flow(
        policy, metric, current, _baseline_cohort(fingerprint), seed=42
    )

    # Then: oriented effect is +5.0, the lower bound is +5.0, and the strict rule
    # 5.0 > 5 is False, so the exact boundary passes reproducibly.
    assert outcome.enabled is True
    assert outcome.status == _comparison.Status.PASS
    assert outcome.method == _comparison.ComparisonMethod.COHORT_BOOTSTRAP
    assert outcome.evidence is not None
    assert isinstance(outcome.evidence, _comparison.CohortBootstrapResult)
    assert outcome.evidence.observed_effect == 5.0
    assert outcome.evidence.lower_decision_bound == 5.0


@pytest.mark.parametrize("higher_is_worse", [True, False])
def test_cohort_receipt_fails_above_threshold_when_constant(
    comparison: Comparison, higher_is_worse: bool
) -> None:
    # Given: constant cohorts whose oriented separation is 6.0 above the threshold.
    # higher-is-worse current is 16.0 x5; lower-is-worse current is 4.0 x5;
    # both vs baseline 10.0 x10.
    direction = (
        _comparison.Direction.HIGHER_IS_WORSE
        if higher_is_worse
        else _comparison.Direction.LOWER_IS_WORSE
    )
    policy = _policy(direction)
    metric = policy.metrics[0]
    fingerprint = _fingerprint(policy, metric)
    current_value = 16.0 if higher_is_worse else 4.0
    current = _runs(_repeat(current_value, 5), start_day=1, fingerprint=fingerprint)

    # When: the cohort bootstrap evaluates the enabled metric.
    outcome = comparison.evaluate_flow(
        policy, metric, current, _baseline_cohort(fingerprint), seed=42
    )

    # Then: oriented effect is +6.0, the lower bound is +6.0, and 6.0 > 5 fails.
    assert outcome.status == _comparison.Status.FAIL
    assert outcome.evidence is not None
    assert isinstance(outcome.evidence, _comparison.CohortBootstrapResult)
    assert outcome.evidence.observed_effect == 6.0
    assert outcome.evidence.lower_decision_bound == 6.0


def test_reference_receipt_is_advisory_when_single_current_run(
    comparison: Comparison,
) -> None:
    # Given: one current run at 16.0, baseline ten runs at 10.0, higher-is-worse,
    # threshold 5, one enabled metric.
    policy = _policy(_comparison.Direction.HIGHER_IS_WORSE)
    metric = policy.metrics[0]
    fingerprint = _fingerprint(policy, metric)
    current = _runs((("c0", 16.0),), start_day=1, fingerprint=fingerprint)

    # When: the flow routes to the advisory baseline reference tail.
    outcome = comparison.evaluate_flow(
        policy, metric, current, _baseline_cohort(fingerprint), seed=42
    )

    # Then: the reference tail is 10.0, the effect is 6.0, the anomaly is True, and
    # reference mode stays INCONCLUSIVE (advisory, not a CI verdict).
    assert outcome.enabled is True
    assert outcome.status == _comparison.Status.INCONCLUSIVE
    assert outcome.method == _comparison.ComparisonMethod.BASELINE_REFERENCE
    assert outcome.evidence is not None
    assert isinstance(outcome.evidence, _comparison.BaselineReferenceResult)
    assert outcome.evidence.reference_quantile == 10.0
    assert outcome.evidence.reference_effect == 6.0
    assert outcome.evidence.reference_anomaly is True


def test_disabled_outcome_when_metric_disabled(
    comparison: Comparison,
) -> None:
    # Given: a disabled metric and otherwise valid cohorts.
    policy = _policy(_comparison.Direction.LOWER_IS_WORSE)
    metric = replace(policy.metrics[0], enabled=False)
    current = _runs(_repeat(5.0, 5), start_day=1, fingerprint="")
    baseline = _baseline_cohort("")

    # When: the flow evaluates the disabled metric.
    outcome = comparison.evaluate_flow(policy, metric, current, baseline, seed=42)

    # Then: it is inconclusive, disabled, with the disabled reason and no evidence.
    assert outcome.enabled is False
    assert outcome.status == _comparison.Status.INCONCLUSIVE
    assert outcome.method is None
    assert outcome.evidence is None
    assert outcome.reason == _comparison.MetricReason.METRIC_DISABLED.value
    assert outcome.exclusions == ()


def test_inconclusive_when_current_runs_are_insufficient(
    comparison: Comparison,
) -> None:
    # Given: three current runs and ten baseline runs under the five-run minimum.
    policy = _policy(_comparison.Direction.LOWER_IS_WORSE)
    metric = policy.metrics[0]
    fingerprint = _fingerprint(policy, metric)
    current = _runs(_repeat(5.0, 3), start_day=1, fingerprint=fingerprint)

    # When: the flow selects a method.
    outcome = comparison.evaluate_flow(
        policy, metric, current, _baseline_cohort(fingerprint), seed=42
    )

    # Then: the cohort is incomparable and the reason is the current-run minimum.
    assert outcome.enabled is True
    assert outcome.status == _comparison.Status.INCONCLUSIVE
    assert (
        outcome.reason
        == _comparison.ComparabilityReason.INSUFFICIENT_CURRENT_RUNS.value
    )


@pytest.mark.parametrize("category", ["missing", "ineligible"])
def test_eligible_cohort_classifies_exclusions_when_given_a_run(
    comparison: Comparison, category: str
) -> None:
    # Given: a baseline cohort with one kept run and one withheld run.
    fingerprint = "c" * 64
    kept = {
        "b0": _comparison.run_record(
            "b0", 10.0, day=100, metric_fingerprint=fingerprint
        )
    }
    if category == "missing":
        withheld: dict[str, _comparison.RunRecord | None] = {
            "b0": kept["b0"],
            "b-missing": None,
        }
        expected_reason = _comparison.MetricReason.METRIC_MISSING
    else:
        withheld = {
            "b0": kept["b0"],
            "b-ineligible": _comparison.run_record(
                "b-ineligible", None, day=101, metric_fingerprint=fingerprint
            ),
        }
        expected_reason = _comparison.MetricReason.METRIC_INELIGIBLE

    # When: the cohort is classified.
    result = comparison.eligible_cohort(withheld, cohort=_comparison.Cohort.BASELINE)

    # Then: the kept run survives and the withheld run carries its exclusion reason.
    assert result.run_values == (_comparison.RunValue("b0", 10.0),)
    run_name = "b-missing" if category == "missing" else "b-ineligible"
    assert result.exclusions == (
        _comparison.MetricExclusion(
            _comparison.Cohort.BASELINE, run_name, expected_reason
        ),
    )


def test_aggregate_status_prefails_over_inconclusive_and_pass(
    comparison: Comparison,
) -> None:
    # Given: enabled outcomes spanning all three statuses.
    policy = _policy(_comparison.Direction.LOWER_IS_WORSE)
    metric = policy.metrics[0]
    fingerprint = _fingerprint(policy, metric)
    fail_outcome = comparison.evaluate_flow(
        policy,
        metric,
        _runs(_repeat(4.0, 5), start_day=1, fingerprint=fingerprint),
        _baseline_cohort(fingerprint),
        seed=42,
    )
    pass_outcome = comparison.evaluate_flow(
        policy,
        metric,
        _runs(_repeat(5.0, 5), start_day=1, fingerprint=fingerprint),
        _baseline_cohort(fingerprint),
        seed=42,
    )
    disabled = replace(metric, enabled=False)
    disabled_outcome = comparison.evaluate_flow(policy, disabled, {}, {}, seed=42)

    # When: the enabled outcomes are aggregated.
    status = comparison.aggregate_status((pass_outcome, disabled_outcome, fail_outcome))

    # Then: FAIL wins outright over INCONCLUSIVE and PASS.
    assert status == _comparison.Status.FAIL


def test_two_runs_produce_identical_receipts_when_seeded(
    comparison: Comparison,
) -> None:
    # Given: constant higher-is-worse cohorts and a fixed seed.
    policy = _policy(_comparison.Direction.HIGHER_IS_WORSE)
    metric = policy.metrics[0]
    fingerprint = _fingerprint(policy, metric)
    current = _runs(_repeat(15.0, 5), start_day=1, fingerprint=fingerprint)

    # When: the flow runs twice with the same inputs.
    first = comparison.evaluate_flow(
        policy, metric, current, _baseline_cohort(fingerprint), seed=42
    )
    second = comparison.evaluate_flow(
        policy, metric, current, _baseline_cohort(fingerprint), seed=42
    )

    # Then: the receipts are byte-for-byte identical (deterministic mirror).
    assert first == second


def test_oriented_leaves_higher_is_worse_and_negates_lower_is_worse(
    comparison: Comparison,
) -> None:
    # Given: a single value in each direction.
    # When: orientation is applied.
    higher = comparison.oriented((15.0,), higher_is_worse=True)
    lower = comparison.oriented((5.0,), higher_is_worse=False)
    # Then: positive effect means worsening in both directions.
    assert list(higher) == [15.0]
    assert list(lower) == [-5.0]


@pytest.mark.parametrize("values", [(), (float("nan"),), (float("inf"),)])
def test_oriented_rejects_nonempty_when_given_invalid(
    comparison: Comparison, values: tuple[float, ...]
) -> None:
    # Given: an empty or nonfinite value tuple.
    # When: orientation is applied.
    # Then: the boundary rejects it rather than producing a silent result.
    with pytest.raises(ValueError, match="oriented requires"):
        _ = comparison.oriented(values, higher_is_worse=True)


def test_oriented_rejects_nonfinite_when_given_invalid(
    comparison: Comparison,
) -> None:
    # Given: a tuple containing a nonfinite value.
    # When: orientation is applied.
    # Then: the finite boundary rejects it.
    with pytest.raises(ValueError, match="finite"):
        _ = comparison.oriented((float("nan"), 1.0), higher_is_worse=True)


@pytest.mark.parametrize("seed", [-1])
def test_bootstrap_rejects_negative_seed_when_given_invalid(
    comparison: Comparison, seed: int
) -> None:
    # Given: a negative seed and valid constant cohorts that route to cohort bootstrap.
    policy = _policy(_comparison.Direction.LOWER_IS_WORSE)
    metric = policy.metrics[0]
    fingerprint = _fingerprint(policy, metric)
    current = _runs(_repeat(5.0, 5), start_day=1, fingerprint=fingerprint)
    current_cohort = comparison.eligible_cohort(
        current, cohort=_comparison.Cohort.CURRENT
    )
    baseline_cohort = comparison.eligible_cohort(
        _baseline_cohort(fingerprint), cohort=_comparison.Cohort.BASELINE
    )
    selection = comparison.select_comparison(
        policy, current_cohort.comparison_inputs, baseline_cohort.comparison_inputs
    )
    assert selection.method == _comparison.ComparisonMethod.COHORT_BOOTSTRAP
    metric_input = _comparison.MetricComparisonInput(
        metric_id=metric.metric_id,
        direction=metric.direction,
        requested_alpha=policy.nominal_alpha,
        effective_alpha=selection.alpha_effective,
        practical_threshold=metric.practical_threshold,
        current=current_cohort.run_values,
        baseline=baseline_cohort.run_values,
    )

    # When: a seeded bootstrap runs with a negative seed.
    # Then: the seed boundary rejects it.
    with pytest.raises(ValueError, match="nonnegative"):
        _ = comparison.bootstrap_cohort(
            metric_input, _comparison.BootstrapOptions(seed=seed)
        )


def test_run_record_rejects_invalid_day_or_value_when_given_invalid() -> None:
    # Given: an out-of-range day and a nonfinite value.
    # When: a raw record is built.
    # Then: each invalid input is rejected with a clear message.
    with pytest.raises(ValueError, match="year"):
        _ = _comparison.run_record("b0", 10.0, day=999)
    with pytest.raises(ValueError, match="finite"):
        _ = _comparison.run_record("b1", float("nan"), day=1)


def test_comparison_demo_when_executed_as_a_script() -> None:
    # Given: the comparison mirror executed as a standalone script.
    # When: it runs each branch and prints inputs and outputs.
    first = run_local_command(
        (sys.executable, str(_REPO_ROOT / "examples" / "_comparison.py")),
        cwd=Path(__file__).resolve().parents[1],
        timeout_seconds=15.0,
    )
    second = run_local_command(
        (sys.executable, str(_REPO_ROOT / "examples" / "_comparison.py")),
        cwd=Path(__file__).resolve().parents[1],
        timeout_seconds=15.0,
    )

    # Then: both runs exit zero with identical, receipt-rich output.
    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    assert first.stdout == second.stdout
    for receipt in (
        "reason=metric_disabled",
        "METRIC_MISSING",
        "METRIC_INELIGIBLE",
        "insufficient_current_runs",
        "reference_quantile=10.0",
        "reference_effect=6.0",
        "reference_anomaly=True",
        "observed_effect=5.0",
        "lower_decision_bound=5.0",
        "status=pass",
        "observed_effect=6.0",
        "status=fail",
        "aggregate PASS+FAIL -> fail",
    ):
        assert receipt in first.stdout


def test_internal_comparison_lesson_output_when_executed(
    comparison: Comparison,
) -> None:
    # Given: the canonical lesson 11 path.
    # When: two clean temporary workspaces execute the lesson end to end.
    first = run_standalone_notebook(_LESSON_11)
    second = run_standalone_notebook(_LESSON_11)

    # Then: both runs exit zero with identical, receipt-rich output.
    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    assert first.stdout == second.stdout

    # The fixed narrative sections appear in teaching order.
    sections = ("Goal:", "Inputs:", "Run:", "Evidence:", "Takeaway:")
    positions = tuple(first.stdout.index(section) for section in sections)
    assert positions == tuple(sorted(positions))

    # Every supported case prints its inputs and outputs.
    for receipt in (
        "reason=metric_disabled",
        "METRIC_MISSING",
        "METRIC_INELIGIBLE",
        "insufficient_current_runs",
        "reference_quantile=10.0",
        "reference_effect=6.0",
        "reference_anomaly=True",
        "observed_effect=5.0",
        "lower_decision_bound=5.0",
        "status=pass",
        "observed_effect=6.0",
        "status=fail",
        "aggregate PASS+FAIL -> fail",
    ):
        assert receipt in first.stdout

    # The interactive laboratory recomputes the trace with the default controls.
    _interactive_expected = (
        "Interactive trace: direction=lower_is_worse; threshold=5; "
        "current=5 x5; baseline x10; enabled=1; seed=42; "
        "effective_alpha=0.05000; method=cohort_bootstrap; "
        "observed_effect=5.000; lower_decision_bound=5.000000; "
        "strict 5.000000 > 5.000 -> PASS"
    )
    assert _interactive_expected in first.stdout

    # The varied-cohort lower bound matches the mirror's own computation.
    _varied_policy = _policy(_comparison.Direction.LOWER_IS_WORSE)
    _metric = _varied_policy.metrics[0]
    _fp = _fingerprint(_varied_policy, _metric)
    _current = _runs(_repeat(4.0, 5), start_day=1, fingerprint=_fp)
    _outcome = comparison.evaluate_flow(
        _varied_policy, _metric, _current, _baseline_cohort(_fp), seed=42
    )
    assert _outcome.status == _comparison.Status.FAIL
    assert isinstance(_outcome.evidence, _comparison.CohortBootstrapResult)
    _bound = f"lower_decision_bound={_outcome.evidence.lower_decision_bound}"
    assert _bound in first.stdout

    # The line-level reference map pairs each mirror function with its
    # production file:line, and the explanation cross-links use blob/main URLs.
    _source = _LESSON_11.read_text(encoding="utf-8")
    for _func, _location in (
        ("oriented", "src/perfcheck/bootstrap_sampling.py:76"),
        ("bootstrap_cohort", "src/perfcheck/bootstrap_sampling.py:25"),
        ("eligible_cohort", "src/perfcheck/regression_cohorts.py:21"),
        ("select_comparison", "src/perfcheck/policy.py:80"),
        ("reference_cohort", "src/perfcheck/bootstrap_reference.py:15"),
        ("evaluate_flow", "src/perfcheck/regression_metrics.py:25"),
        ("aggregate_status", "src/perfcheck/regression_aggregation.py:13"),
    ):
        assert f"`{_func}`" in _source
        assert _location in _source
    # The explanation cross-links are published-docs URLs to the built .html pages.
    assert "https://geoder101.github.io/perfcheck/" in _source
    assert "explanation/" in _source
    assert ".html" in _source
