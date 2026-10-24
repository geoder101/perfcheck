from typing import Final

import pytest
from pydantic import JsonValue, TypeAdapter, ValidationError

from perfcheck.cli_services import summarize_raw
from perfcheck.errors import ArtifactSchemaCode
from perfcheck.policy_models import SuitePolicy
from perfcheck.run_models import RunArtifact
from perfcheck.summary_models import SummaryArtifact
from tests.cli_support import cli_policy, cli_run
from tests.schema_boundary_support import mutated_json

_RECORD: Final = ("metric_records", 0)
_SERIES: Final = (*_RECORD, "series")
_PROVENANCE: Final = (*_RECORD, "provenance")
_SUMMARY: Final = (*_RECORD, "summary")
type Mutation = tuple[tuple[str | int, ...], JsonValue, ArtifactSchemaCode]


def _assert_reason(error: ValidationError, code: ArtifactSchemaCode) -> None:
    errors = [item for item in error.errors() if item["type"] == "value_error"]
    assert len(errors) == 1
    assert errors[0]["type"] == "value_error"
    assert errors[0]["msg"] == f"Value error, {code}"


@pytest.mark.parametrize(
    "mutation",
    [
        (
            (*_SERIES, "labels"),
            [{"name": "job", "value": "a"}] * 2,
            ArtifactSchemaCode.DUPLICATE_LABEL,
        ),
        (
            (*_SERIES, "labels"),
            [{"name": "z", "value": "a"}, {"name": "a", "value": "a"}],
            ArtifactSchemaCode.LABEL_ORDER,
        ),
        (
            (*_SERIES, "labels"),
            [{"name": "job", "value": "a"}],
            ArtifactSchemaCode.LABEL_SET_MISMATCH,
        ),
        ((*_SERIES, "metric_id"), "other", ArtifactSchemaCode.SERIES_METRIC_MISMATCH),
        (
            (*_SERIES, "samples", 1, "timestamp"),
            "2026-01-01T01:00:00Z",
            ArtifactSchemaCode.INVALID_SAMPLE_ORDER,
        ),
        (
            (*_PROVENANCE, "query"),
            "other_query",
            ArtifactSchemaCode.QUERY_PROVENANCE_MISMATCH,
        ),
        (
            (*_PROVENANCE, "step_seconds"),
            30,
            ArtifactSchemaCode.QUERY_PROVENANCE_MISMATCH,
        ),
        (
            (*_PROVENANCE, "start"),
            "2026-01-01T01:00:01Z",
            ArtifactSchemaCode.PROVENANCE_INTERVAL_MISMATCH,
        ),
        (
            (*_PROVENANCE, "end"),
            "2026-01-01T01:10:01Z",
            ArtifactSchemaCode.PROVENANCE_INTERVAL_MISMATCH,
        ),
        ((*_RECORD, "metric_id"), "other", ArtifactSchemaCode.METRIC_SET_MISMATCH),
        (
            (*_RECORD, "availability"),
            "unavailable",
            ArtifactSchemaCode.INVALID_COLLECTION_RECORD,
        ),
        ((*_RECORD, "series"), None, ArtifactSchemaCode.INVALID_COLLECTION_RECORD),
        (("suite_id",), "other", ArtifactSchemaCode.SUITE_MISMATCH),
        (("policy_sha256",), "1" * 64, ArtifactSchemaCode.POLICY_HASH_MISMATCH),
    ],
)
def test_run_parser_rejects_one_invariant_mutation(mutation: Mutation) -> None:
    # Given: an independently valid run with one boundary field changed.
    raw = cli_run(cli_policy(), 1, 10.0)
    assert RunArtifact.model_validate_json(raw.model_dump_json()) == raw
    path, value, reason = mutation
    payload = mutated_json(raw, path, value)

    # When: the ordinary JSON parser receives the mutation.
    with pytest.raises(ValidationError) as caught:
        _ = RunArtifact.model_validate_json(payload)

    # Then: the intended invariant, not an incidental parse error, rejects it.
    _assert_reason(caught.value, reason)


@pytest.mark.parametrize(
    "mutation",
    [
        ((*_SUMMARY, "value"), None, ArtifactSchemaCode.SUMMARY_VALUE_MISMATCH),
        ((*_SUMMARY, "statistic"), "max", ArtifactSchemaCode.STATISTIC_MISMATCH),
        (
            (*_SUMMARY, "eligibility", "eligible"),
            False,
            ArtifactSchemaCode.ELIGIBILITY_REASON_MISMATCH,
        ),
        (
            (*_SUMMARY, "eligibility", "reason"),
            "insufficient_points",
            ArtifactSchemaCode.ELIGIBILITY_REASON_MISMATCH,
        ),
        (
            (*_SUMMARY, "eligibility", "analysis_end"),
            "2026-01-01T00:59:59Z",
            ArtifactSchemaCode.INVALID_INTERVAL,
        ),
        (
            (*_RECORD, "availability"),
            "unavailable",
            ArtifactSchemaCode.INVALID_SUMMARY_RECORD,
        ),
        ((*_RECORD, "summary"), None, ArtifactSchemaCode.INVALID_SUMMARY_RECORD),
        ((*_RECORD, "metric_id"), "other", ArtifactSchemaCode.METRIC_SET_MISMATCH),
        (("policy_sha256",), "1" * 64, ArtifactSchemaCode.POLICY_HASH_MISMATCH),
    ],
)
def test_summary_parser_rejects_one_invariant_mutation(mutation: Mutation) -> None:
    # Given: a real summary of eligible raw evidence, mutated only at ingress.
    policy = cli_policy()
    summary = summarize_raw(cli_run(policy, 1, 10.0), policy)
    assert SummaryArtifact.model_validate_json(summary.model_dump_json()) == summary
    path, value, reason = mutation

    # When: summary parsing checks the changed field.
    with pytest.raises(ValidationError) as caught:
        _ = SummaryArtifact.model_validate_json(mutated_json(summary, path, value))

    # Then: its exact semantic contradiction is reported.
    _assert_reason(caught.value, reason)


@pytest.mark.parametrize("summary_kind", [False, True])
def test_artifact_parser_rejects_duplicate_records(summary_kind: bool) -> None:
    # Given: a valid artifact with its single record repeated in JSON.
    policy = cli_policy()
    raw = cli_run(policy, 1, 10.0)
    artifact = summarize_raw(raw, policy) if summary_kind else raw
    record = artifact.metric_records[0]
    value = TypeAdapter[JsonValue](JsonValue).validate_json(record.model_dump_json())

    # When: the duplicated metric record reaches its normal artifact parser.
    with pytest.raises(ValidationError) as caught:
        _ = type(artifact).model_validate_json(
            mutated_json(artifact, ("metric_records",), [value, value])
        )

    # Then: the metric uniqueness invariant rejects the duplicate.
    _assert_reason(caught.value, ArtifactSchemaCode.DUPLICATE_METRIC_RECORD)


@pytest.mark.parametrize(
    "mutation",
    [
        (
            ("metrics", 0, "expected_label_names"),
            ["job", "job"],
            ArtifactSchemaCode.DUPLICATE_LABEL_NAME,
        ),
        (
            ("metrics", 0, "expected_label_names"),
            ["z", "a"],
            ArtifactSchemaCode.LABEL_NAME_ORDER,
        ),
        (("metrics", 0, "enabled"), False, ArtifactSchemaCode.MISSING_ENABLED_METRIC),
    ],
)
def test_policy_parser_rejects_one_invariant_mutation(mutation: Mutation) -> None:
    # Given: a valid policy and one noncanonical label or enabled-set mutation.
    policy = cli_policy()
    path, value, reason = mutation

    # When: the policy is parsed normally, without bypassing model validation.
    with pytest.raises(ValidationError) as caught:
        _ = SuitePolicy.model_validate_json(mutated_json(policy, path, value))

    # Then: the intended policy invariant is the semantic failure.
    _assert_reason(caught.value, reason)


def test_policy_parser_rejects_duplicate_metric_ids() -> None:
    # Given: a valid policy whose complete metric is repeated once.
    policy = cli_policy()
    metric = TypeAdapter[JsonValue](JsonValue).validate_json(
        policy.metrics[0].model_dump_json()
    )

    # When: duplicate metric IDs enter the normal parser.
    with pytest.raises(ValidationError) as caught:
        _ = SuitePolicy.model_validate_json(
            mutated_json(policy, ("metrics",), [metric, metric])
        )

    # Then: uniqueness, not a malformed metric, causes rejection.
    _assert_reason(caught.value, ArtifactSchemaCode.DUPLICATE_METRIC_ID)
