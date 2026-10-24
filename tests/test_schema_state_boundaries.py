import pytest
from pydantic import JsonValue, TypeAdapter, ValidationError

from perfcheck.cli_services import summarize_raw
from perfcheck.collection_models import CollectionFailure, MetricCollectionRecord
from perfcheck.errors import ArtifactSchemaCode
from perfcheck.model_types import CollectionFailureReason, MetricAvailability
from perfcheck.storage import policy_content_sha256
from perfcheck.summary_models import MetricSummary, SummaryMetricRecord
from tests.cli_support import cli_policy, cli_run
from tests.schema_boundary_support import mutated_json


@pytest.mark.parametrize("summary_kind", [False, True])
@pytest.mark.parametrize("available", [False, True])
def test_record_parser_rejects_failure_presence_contradiction(
    summary_kind: bool, available: bool
) -> None:
    # Given: a valid available or unavailable record before changing failure presence.
    policy = cli_policy()
    raw = cli_run(policy, 1, 10.0)
    failure = CollectionFailure(
        reason=CollectionFailureReason.TIMEOUT, detail="timed out"
    )
    availability = (
        MetricAvailability.AVAILABLE if available else MetricAvailability.UNAVAILABLE
    )
    if summary_kind:
        summary = summarize_raw(raw, policy).metric_records[0].summary
        record = SummaryMetricRecord(
            metric_id=raw.metric_records[0].metric_id,
            availability=availability,
            summary=summary if available else None,
            failure=None if available else failure,
        )
        reason = ArtifactSchemaCode.INVALID_SUMMARY_RECORD
    else:
        original = raw.metric_records[0]
        record = MetricCollectionRecord(
            metric_id=original.metric_id,
            availability=availability,
            provenance=original.provenance,
            series=original.series if available else None,
            failure=None if available else failure,
        )
        reason = ArtifactSchemaCode.INVALID_COLLECTION_RECORD
    value = (
        TypeAdapter[JsonValue](JsonValue).validate_json(failure.model_dump_json())
        if available
        else None
    )

    # When: failure is added to an available record or removed from an unavailable one.
    with pytest.raises(ValidationError) as caught:
        _ = type(record).model_validate_json(mutated_json(record, ("failure",), value))

    # Then: the exact availability/failure contradiction causes rejection.
    assert [(item["type"], item["msg"]) for item in caught.value.errors()] == [
        ("value_error", f"Value error, {reason}")
    ]


def test_ineligible_summary_rejects_a_present_value() -> None:
    # Given: a genuinely ineligible summary from a fully trimmed window.
    policy = cli_policy()
    metric = policy.metrics[0]
    trimmed = metric.eligibility.model_copy(update={"warmup_seconds": 601})
    policy = policy.model_copy(
        update={"metrics": (metric.model_copy(update={"eligibility": trimmed}),)}
    )
    policy = policy.model_copy(update={"policy_sha256": policy_content_sha256(policy)})
    summary = summarize_raw(cli_run(policy, 1, 10.0), policy).metric_records[0].summary
    assert summary is not None
    assert summary.value is None
    assert summary.eligibility.eligible is False

    # When: a scalar is injected into this ineligible summary at the parser boundary.
    with pytest.raises(ValidationError) as caught:
        _ = MetricSummary.model_validate_json(mutated_json(summary, ("value",), 10.0))

    # Then: the inverse eligibility/value contradiction is rejected specifically.
    assert (
        caught.value.errors()[0]["msg"]
        == f"Value error, {ArtifactSchemaCode.SUMMARY_VALUE_MISMATCH}"
    )
