from datetime import UTC, datetime, timedelta

from perfcheck.model_types import (
    ComparisonMethod,
    ComparisonMode,
    Direction,
    MetricUnit,
    Statistic,
)
from perfcheck.policy import (
    ComparabilityReason,
    ComparisonInput,
    comparison_fingerprint,
    select_comparison,
)
from perfcheck.policy_models import EligibilityPolicy, MetricPolicy, SuitePolicy


def policy(*, comparison_mode: ComparisonMode = ComparisonMode.AUTO) -> SuitePolicy:
    return SuitePolicy(
        policy_id="policy-1",
        suite_id="suite-1",
        policy_sha256="a" * 64,
        metrics=(
            MetricPolicy(
                metric_id="latency",
                query=(
                    "histogram_quantile(0.99, "
                    "rate(request_duration_seconds_bucket[1m]))"
                ),
                expected_label_names=("service",),
                unit=MetricUnit.MILLISECONDS,
                direction=Direction.HIGHER_IS_WORSE,
                statistic=Statistic.P99,
                practical_threshold=5.0,
                step_seconds=15,
                rate_window_seconds=60,
                eligibility=EligibilityPolicy(warmup_seconds=30, cooldown_seconds=30),
            ),
        ),
        comparison_mode=comparison_mode,
    )


def comparison_input(
    policy_value: SuitePolicy,
    *,
    source_run_id: str,
    source_content_sha256: str,
    start: datetime,
    end: datetime,
) -> ComparisonInput:
    return ComparisonInput(
        source_run_id=source_run_id,
        source_content_sha256=source_content_sha256,
        interval_start=start,
        interval_end=end,
        policy_sha256=policy_value.policy_sha256,
        metric_fingerprints=(
            comparison_fingerprint(policy_value, policy_value.metrics[0]),
        ),
    )


def test_comparison_fingerprint_changes_when_only_step_changes() -> None:
    # Given: two policies differing only in the metric query step.
    original = policy()
    changed_metric = original.metrics[0].model_copy(update={"step_seconds": 30})
    changed = original.model_copy(update={"metrics": (changed_metric,)})

    # When: their canonical metric fingerprints are calculated.
    original_fingerprint = comparison_fingerprint(original, original.metrics[0])
    changed_fingerprint = comparison_fingerprint(changed, changed.metrics[0])

    # Then: the comparator preserves the distinction and cannot bootstrap them.
    assert original_fingerprint != changed_fingerprint


def test_select_comparison_returns_step_mismatch_before_method_selection() -> None:
    # Given: one current and ten baseline runs with a step-only fingerprint mismatch.
    original = policy()
    changed_metric = original.metrics[0].model_copy(update={"step_seconds": 30})
    changed = original.model_copy(update={"metrics": (changed_metric,)})
    start = datetime(2026, 1, 1, tzinfo=UTC)
    current = comparison_input(
        original,
        source_run_id="current-1",
        source_content_sha256="1" * 64,
        start=start,
        end=start + timedelta(minutes=10),
    )
    baseline = tuple(
        comparison_input(
            changed,
            source_run_id=f"baseline-{index}",
            source_content_sha256=f"{index:x}" * 64,
            start=start + timedelta(hours=index),
            end=start + timedelta(hours=index, minutes=10),
        )
        for index in range(1, 11)
    )

    # When: the policy layer evaluates the cohorts.
    selection = select_comparison(original, (current,), baseline)

    # Then: it returns the exact mismatch and does not select bootstrap.
    assert selection.reason is ComparabilityReason.METRIC_FINGERPRINT_MISMATCH
    assert selection.method is None


def test_select_comparison_auto_uses_reference_for_exactly_one_current_run() -> None:
    # Given: one current and the required ten non-overlapping baseline runs.
    configured_policy = policy()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    current = comparison_input(
        configured_policy,
        source_run_id="current-1",
        source_content_sha256="f" * 64,
        start=start,
        end=start + timedelta(minutes=10),
    )
    baseline = tuple(
        comparison_input(
            configured_policy,
            source_run_id=f"baseline-{index}",
            source_content_sha256=f"{index:x}" * 64,
            start=start + timedelta(hours=index),
            end=start + timedelta(hours=index, minutes=10),
        )
        for index in range(1, 11)
    )

    # When: automatic mode selects the comparison strategy.
    selection = select_comparison(configured_policy, (current,), baseline)

    # Then: it selects only the advisory baseline-reference method.
    assert selection.method is ComparisonMethod.BASELINE_REFERENCE
    assert selection.reason is None
    assert selection.alpha_effective == 0.05


def test_select_comparison_auto_requires_cohort_minima_for_multiple_current_runs() -> (
    None
):
    # Given: two current runs and an otherwise valid baseline cohort.
    configured_policy = policy()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    current = tuple(
        comparison_input(
            configured_policy,
            source_run_id=f"current-{index}",
            source_content_sha256=f"{index + 10:x}" * 64,
            start=start + timedelta(hours=index),
            end=start + timedelta(hours=index, minutes=10),
        )
        for index in range(1, 3)
    )
    baseline = tuple(
        comparison_input(
            configured_policy,
            source_run_id=f"baseline-{index}",
            source_content_sha256=f"{index + 20:x}" * 64,
            start=start + timedelta(hours=index + 3),
            end=start + timedelta(hours=index + 3, minutes=10),
        )
        for index in range(1, 11)
    )

    # When: auto mode considers a non-singleton current cohort.
    selection = select_comparison(configured_policy, current, baseline)

    # Then: it refuses bootstrap until the policy's minimum current cohort is met.
    assert selection.reason is ComparabilityReason.INSUFFICIENT_CURRENT_RUNS
    assert selection.method is None


def test_select_comparison_rejects_invalid_explicit_reference_mode() -> None:
    # Given: an explicit reference policy with two qualifying current runs.
    configured_policy = policy(comparison_mode=ComparisonMode.BASELINE_REFERENCE)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    current = tuple(
        comparison_input(
            configured_policy,
            source_run_id=f"current-{index}",
            source_content_sha256=f"{index + 10:x}" * 64,
            start=start + timedelta(hours=index),
            end=start + timedelta(hours=index, minutes=10),
        )
        for index in range(1, 3)
    )
    baseline = tuple(
        comparison_input(
            configured_policy,
            source_run_id=f"baseline-{index}",
            source_content_sha256=f"{index + 20:x}" * 64,
            start=start + timedelta(hours=index + 3),
            end=start + timedelta(hours=index + 3, minutes=10),
        )
        for index in range(1, 11)
    )

    # When: preflight selects the explicit comparison mode.
    selection = select_comparison(configured_policy, current, baseline)

    # Then: the invalid explicit request has its own stable reason.
    assert (
        selection.reason
        is ComparabilityReason.BASELINE_REFERENCE_REQUIRES_ONE_CURRENT_RUN
    )
    assert selection.method is None


def test_select_comparison_rejects_overlapping_windows_with_stable_key() -> None:
    # Given: otherwise valid cohorts that share an observed time window.
    configured_policy = policy(comparison_mode=ComparisonMode.BASELINE_REFERENCE)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    current = comparison_input(
        configured_policy,
        source_run_id="current-1",
        source_content_sha256="1" * 64,
        start=start,
        end=start + timedelta(minutes=10),
    )
    baseline = comparison_input(
        configured_policy,
        source_run_id="baseline-1",
        source_content_sha256="2" * 64,
        start=start + timedelta(minutes=5),
        end=start + timedelta(minutes=15),
    )

    # When: the cohorts are checked before a method can run.
    selection = select_comparison(configured_policy, (current,), (baseline,))

    # Then: the overlap is an explicit inconclusive reason.
    assert selection.reason is ComparabilityReason.OVERLAPPING_SOURCE_INTERVAL
    assert selection.method is None
