"""Suite verdict aggregation for evaluated regression metrics."""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from perfcheck.model_types import Status

if TYPE_CHECKING:
    from perfcheck.regression_models import MetricOutcome


def aggregate_status(metrics: tuple[MetricOutcome, ...]) -> Status:
    """Reduce enabled metric outcomes to the contractual suite status."""
    status = Status.PASS
    for metric in metrics:
        if metric.enabled:
            match metric.status:
                case Status.FAIL:
                    return Status.FAIL
                case Status.INCONCLUSIVE:
                    status = Status.INCONCLUSIVE
                case Status.PASS:
                    pass
                case _:
                    assert_never(metric.status)
    return status
