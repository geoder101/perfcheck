from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal, assert_never

import pytest

from perfcheck.model_types import ComparisonMethod, ComparisonMode
from perfcheck.policy import (
    ComparabilityReason,
    ComparisonInput,
    comparison_fingerprint,
    select_comparison,
)
from tests.comparison_boundary_support import boundary_metric, boundary_policy

if TYPE_CHECKING:
    from perfcheck.policy_models import SuitePolicy


def inputs(policy: SuitePolicy, indices: range) -> tuple[ComparisonInput, ...]:
    return tuple(
        ComparisonInput(
            source_run_id=f"run-{index}",
            source_content_sha256=f"{index:064x}",
            interval_start=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index),
            interval_end=datetime(2026, 1, 1, tzinfo=UTC)
            + timedelta(hours=index, minutes=10),
            policy_sha256=policy.policy_sha256,
            metric_fingerprints=tuple(
                comparison_fingerprint(policy, metric) for metric in policy.metrics
            ),
        )
        for index in indices
    )


@pytest.mark.parametrize(
    ("field", "reason", "within_current"),
    [
        ("policy_sha256", ComparabilityReason.POLICY_SHA256_MISMATCH, False),
        ("source_run_id", ComparabilityReason.DUPLICATE_SOURCE_RUN_ID, False),
        ("source_run_id", ComparabilityReason.DUPLICATE_SOURCE_RUN_ID, True),
        (
            "source_content_sha256",
            ComparabilityReason.DUPLICATE_SOURCE_CONTENT_SHA256,
            False,
        ),
        (
            "source_content_sha256",
            ComparabilityReason.DUPLICATE_SOURCE_CONTENT_SHA256,
            True,
        ),
    ],
)
def test_identity_rejection_is_independent_of_other_mismatches(
    field: Literal["policy_sha256", "source_run_id", "source_content_sha256"],
    reason: ComparabilityReason,
    *,
    within_current: bool,
) -> None:
    # Given: otherwise comparable evidence with exactly one invalid identity field.
    policy = boundary_policy((boundary_metric("latency"),))
    current = inputs(policy, range(1, 4))
    baseline = inputs(policy, range(10, 14))
    donor = current[1] if within_current else baseline[0]
    match field:
        case "policy_sha256":
            altered = replace(current[0], policy_sha256="f" * 64)
        case "source_run_id":
            altered = replace(current[0], source_run_id=donor.source_run_id)
        case "source_content_sha256":
            altered = replace(
                current[0], source_content_sha256=donor.source_content_sha256
            )
        case _:
            assert_never(field)

    # When: the public selection ingress checks the isolated invalid field.
    result = select_comparison(policy, (altered, *current[1:]), baseline)

    # Then: identity errors precede method selection without a false size warning.
    assert result.reason is reason
    assert result.method is None
    assert result.alpha_effective == 0.05
    assert result.small_cohort_warning is False


@pytest.mark.parametrize("microseconds", [0, 1])
def test_inclusive_interval_boundary_distinguishes_touching_from_separation(
    microseconds: int,
) -> None:
    # Given: the last current endpoint and first baseline start differ by 0 or 1 us.
    policy = boundary_policy((boundary_metric("latency"),))
    current = inputs(policy, range(1, 4))
    baseline = inputs(policy, range(10, 14))
    first = replace(
        baseline[0],
        interval_start=current[-1].interval_end + timedelta(microseconds=microseconds),
    )

    # When: the inclusive source intervals are checked.
    result = select_comparison(policy, current, (first, *baseline[1:]))

    # Then: only actual separation permits bootstrap, not endpoint equality.
    assert result.reason is (
        None if microseconds else ComparabilityReason.OVERLAPPING_SOURCE_INTERVAL
    )
    assert result.method is (
        ComparisonMethod.COHORT_BOOTSTRAP if microseconds else None
    )
    assert result.small_cohort_warning is bool(microseconds)


@pytest.mark.parametrize("within_current", [False, True])
def test_overlap_is_detected_inside_a_reverse_ordered_cohort(
    *, within_current: bool
) -> None:
    # Given: distinct identities with an overlap wholly inside one reversed cohort.
    policy = boundary_policy((boundary_metric("latency"),))
    current = inputs(policy, range(1, 4))
    baseline = inputs(policy, range(10, 14))
    target = current if within_current else baseline
    changed = replace(target[0], interval_end=target[1].interval_end)
    overlapping = tuple(reversed((changed, *target[1:])))

    # When: selection receives runs in nonchronological order.
    result = select_comparison(
        policy,
        overlapping if within_current else current,
        baseline if within_current else overlapping,
    )

    # Then: sorting must still reveal the within-cohort overlap.
    assert result.reason is ComparabilityReason.OVERLAPPING_SOURCE_INTERVAL
    assert result.method is None


@pytest.mark.parametrize(
    ("mode", "counts", "reason", "method"),
    [
        (
            ComparisonMode.COHORT_BOOTSTRAP,
            (2, 4),
            ComparabilityReason.INSUFFICIENT_CURRENT_RUNS,
            None,
        ),
        (
            ComparisonMode.COHORT_BOOTSTRAP,
            (3, 3),
            ComparabilityReason.INSUFFICIENT_BASELINE_RUNS,
            None,
        ),
        (
            ComparisonMode.COHORT_BOOTSTRAP,
            (3, 4),
            None,
            ComparisonMethod.COHORT_BOOTSTRAP,
        ),
        (
            ComparisonMode.BASELINE_REFERENCE,
            (1, 5),
            ComparabilityReason.INSUFFICIENT_BASELINE_RUNS,
            None,
        ),
        (
            ComparisonMode.BASELINE_REFERENCE,
            (1, 6),
            None,
            ComparisonMethod.BASELINE_REFERENCE,
        ),
        (
            ComparisonMode.BASELINE_REFERENCE,
            (0, 6),
            ComparabilityReason.BASELINE_REFERENCE_REQUIRES_ONE_CURRENT_RUN,
            None,
        ),
        (
            ComparisonMode.AUTO,
            (1, 5),
            ComparabilityReason.INSUFFICIENT_BASELINE_RUNS,
            None,
        ),
    ],
)
def test_custom_minima_are_applied_at_the_selected_method_boundary(
    mode: ComparisonMode,
    counts: tuple[int, int],
    reason: ComparabilityReason | None,
    method: ComparisonMethod | None,
) -> None:
    # Given: valid policy minima deliberately different from the defaults.
    policy = boundary_policy((boundary_metric("latency"),), mode)
    current = inputs(policy, range(1, counts[0] + 1))
    baseline = inputs(policy, range(10, counts[1] + 10))

    # When: explicit or auto selection applies the relevant minimum.
    result = select_comparison(policy, current, baseline)

    # Then: meeting the exact minimum succeeds; one fewer keeps the exact reason.
    assert result.reason is reason
    assert result.method is method
    assert result.small_cohort_warning is (method is not None)
