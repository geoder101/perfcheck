import json

import pytest
from pydantic import ValidationError

from perfcheck.collection_models import CollectionFailure, QueryProvenance
from perfcheck.errors import ArtifactSchemaCode
from perfcheck.models import (
    ComparisonCohorts,
    RunArtifact,
    SummaryArtifact,
)
from tests.artifact_schema_support import (
    VALID_RUN_JSON,
    valid_summary_json,
)


def assert_schema_code(error: ValidationError, code: ArtifactSchemaCode) -> None:
    errors = error.errors(include_context=False)
    assert len(errors) == 1
    assert errors[0]["type"] == "value_error"
    assert errors[0]["msg"] == f"Value error, {code}"


def summary_json(source_id: str, source_hash: str) -> str:
    run = RunArtifact.model_validate_json(VALID_RUN_JSON)
    return (
        valid_summary_json(run)
        .replace('"summary-1"', json.dumps(f"summary-{source_id}"))
        .replace('"run-1"', json.dumps(source_id))
        .replace(
            '"source_content_sha256": "' + "a" * 64 + '"',
            f'"source_content_sha256": "{source_hash}"',
        )
    )


@pytest.mark.parametrize(
    "credential", ["Bearer top-secret", "token=top-secret", "AUTHORIZATION: secret"]
)
def test_query_provenance_rejects_persisted_credentials(credential: str) -> None:
    # Given: otherwise valid query provenance with credential-bearing query text.
    payload = json.dumps(
        {
            "endpoint_url": "https://metrics.example.test/prometheus",
            "query": f"up # {credential}",
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-01T00:10:00Z",
            "step_seconds": 15,
        }
    )

    # When: persisted request JSON crosses the ordinary schema boundary.
    with pytest.raises(ValidationError) as caught:
        _ = QueryProvenance.model_validate_json(payload)

    # Then: the query credential guard, not an unrelated field, rejects it.
    assert_schema_code(caught.value, ArtifactSchemaCode.CREDENTIAL_QUERY)
    assert caught.value.errors()[0]["loc"] == ("query",)


@pytest.mark.parametrize(
    "credential", ["Bearer top-secret", "password=top-secret", "API_KEY=secret"]
)
def test_collection_failure_rejects_persisted_credentials(credential: str) -> None:
    # Given: a valid failure reason with credential-bearing diagnostic text.
    payload = json.dumps({"reason": "transport_error", "detail": credential})

    # When: persisted failure JSON crosses the ordinary schema boundary.
    with pytest.raises(ValidationError) as caught:
        _ = CollectionFailure.model_validate_json(payload)

    # Then: diagnostic credentials are rejected with the specific detail code.
    assert_schema_code(caught.value, ArtifactSchemaCode.CREDENTIAL_DETAIL)
    assert caught.value.errors()[0]["loc"] == ("detail",)


@pytest.mark.parametrize("current_count", [0, 1, 2])
def test_cohorts_reject_duplicate_content_with_distinct_source_ids(
    current_count: int,
) -> None:
    # Given: schema-valid summaries with distinct IDs but identical source content.
    summaries = [summary_json("run-1", "a" * 64), summary_json("run-2", "a" * 64)]
    parsed = [SummaryArtifact.model_validate_json(value) for value in summaries]
    assert parsed[0].source_run_id != parsed[1].source_run_id
    assert parsed[0].source_content_sha256 == parsed[1].source_content_sha256
    payload = (
        '{"current": ['
        + ",".join(summaries[:current_count])
        + '], "baseline": ['
        + ",".join(summaries[current_count:])
        + "]}"
    )

    # When: the duplicate appears within either cohort or across both cohorts.
    with pytest.raises(ValidationError) as caught:
        _ = ComparisonCohorts.model_validate_json(payload)

    # Then: duplicate content is rejected without being masked by duplicate IDs.
    assert_schema_code(caught.value, ArtifactSchemaCode.DUPLICATE_SOURCE_CONTENT)
