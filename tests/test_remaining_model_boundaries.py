import json
from typing import Final

import pytest
from pydantic import ValidationError

from perfcheck.collection_models import CollectionFailure, QueryProvenance
from perfcheck.errors import ArtifactSchemaCode
from perfcheck.models import (
    V1_ALGORITHM_MANIFEST,
    ComparisonCohorts,
    ComparisonMethod,
    ComparisonReport,
    ComparisonResult,
    RunArtifact,
    Status,
    SummaryArtifact,
)
from tests.artifact_schema_support import (
    POLICY_SHA256,
    VALID_RUN_JSON,
    valid_summary_json,
)

BASELINE_RESULT_JSON: Final = """
{
  "metric_id": "cpu-system",
  "direction": "higher_is_worse",
  "status": "inconclusive",
  "method": "baseline_reference",
  "reference_anomaly": false,
  "reason": "too few current runs"
}
"""
BOOTSTRAP_RESULT_JSON: Final = """
{
  "metric_id": "cpu-system",
  "direction": "higher_is_worse",
  "status": "pass",
  "method": "cohort_bootstrap",
  "effective_seed": 42,
  "requested_resamples": 1000,
  "effective_resamples": 1000,
  "observed_effect": 0.25,
  "lower_decision_bound": 0.1
}
"""


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


@pytest.mark.parametrize(
    "invalid_json",
    [
        pytest.param(
            BASELINE_RESULT_JSON.replace(
                '"reference_anomaly": false',
                '"reference_anomaly": false, "effective_seed": 42',
            ),
            id="baseline-with-seed",
        ),
        pytest.param(
            BASELINE_RESULT_JSON.replace(
                '"reference_anomaly": false',
                '"reference_anomaly": false, "requested_resamples": 1000',
            ),
            id="baseline-with-requested-resamples",
        ),
        pytest.param(
            BASELINE_RESULT_JSON.replace(
                '"reference_anomaly": false',
                '"reference_anomaly": false, "effective_resamples": 1000',
            ),
            id="baseline-with-effective-resamples",
        ),
        pytest.param(
            BASELINE_RESULT_JSON.replace(
                '"reference_anomaly": false',
                '"reference_anomaly": false, "lower_decision_bound": 0.1',
            ),
            id="baseline-with-bootstrap-bound",
        ),
        pytest.param(
            BASELINE_RESULT_JSON.replace(
                '"reference_anomaly": false', '"reference_anomaly": null'
            ),
            id="baseline-without-anomaly",
        ),
        pytest.param(
            BOOTSTRAP_RESULT_JSON.replace(
                '"effective_seed": 42', '"effective_seed": null'
            ),
            id="bootstrap-without-seed",
        ),
        pytest.param(
            BOOTSTRAP_RESULT_JSON.replace(
                '"requested_resamples": 1000', '"requested_resamples": null'
            ),
            id="bootstrap-without-requested-resamples",
        ),
        pytest.param(
            BOOTSTRAP_RESULT_JSON.replace(
                '"effective_resamples": 1000', '"effective_resamples": null'
            ),
            id="bootstrap-without-effective-resamples",
        ),
        pytest.param(
            BOOTSTRAP_RESULT_JSON.replace(
                '"method": "cohort_bootstrap"',
                '"method": "cohort_bootstrap", "reference_anomaly": false',
            ),
            id="bootstrap-with-reference-anomaly",
        ),
    ],
)
def test_comparison_result_rejects_method_option_mismatch(invalid_json: str) -> None:
    # Given: a complete result with one incompatible or missing method option.
    # When: the result crosses the ordinary JSON boundary.
    with pytest.raises(ValidationError) as caught:
        _ = ComparisonResult.model_validate_json(invalid_json)

    # Then: the method contract rejects it, rather than field-level parsing.
    assert_schema_code(caught.value, ArtifactSchemaCode.INVALID_COMPARISON_OPTIONS)


@pytest.mark.parametrize(
    ("result_json", "method", "status"),
    [
        (
            BASELINE_RESULT_JSON,
            ComparisonMethod.BASELINE_REFERENCE,
            Status.INCONCLUSIVE,
        ),
        (BOOTSTRAP_RESULT_JSON, ComparisonMethod.COHORT_BOOTSTRAP, Status.PASS),
    ],
)
def test_comparison_report_accepts_valid_contract(
    result_json: str,
    method: ComparisonMethod,
    status: Status,
) -> None:
    # Given: unique sources, one shared policy, and one valid metric result.
    current = summary_json("run-current", "a" * 64)
    baseline = summary_json("run-baseline", "e" * 64)
    payload = (
        f'{{"policy_sha256": "{POLICY_SHA256}", "suite_status": "{status}",'
        f'"cohorts": {{"current": [{current}], "baseline": [{baseline}]}},'
        f'"metric_results": [{result_json}]}}'
    )

    # When: the complete report crosses the ordinary JSON schema boundary.
    report = ComparisonReport.model_validate_json(payload)

    # Then: the report retains policy, source identities, and method diagnostics.
    assert report.policy_sha256 == POLICY_SHA256
    assert report.algorithm_manifest == V1_ALGORITHM_MANIFEST
    assert report.suite_status is status
    assert report.cohorts.current[0].source_run_id == "run-current"
    assert report.cohorts.baseline[0].source_run_id == "run-baseline"
    assert report.cohorts.baseline[0].source_content_sha256 == "e" * 64
    assert report.metric_results == (ComparisonResult.model_validate_json(result_json),)
    assert report.metric_results[0].method is method
