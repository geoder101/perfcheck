import pytest
from pydantic import ValidationError

from perfcheck.models import (
    ComparisonCohorts,
    ComparisonMethod,
    ComparisonReport,
    ComparisonResult,
    Direction,
    RunArtifact,
    Status,
    SummaryArtifact,
)
from test_artifact_schema import VALID_RUN_JSON, valid_summary_json


@pytest.mark.parametrize(
    ("invalid_json", "field_name"),
    [
        (
            VALID_RUN_JSON.replace("2026-01-01T00:00:00Z", "2026-01-01 00:00:00Z", 1),
            "start",
        ),
        (
            VALID_RUN_JSON.replace(
                '"environment": "ci"', '"environment": "Bearer top-secret"'
            ),
            "environment",
        ),
        (
            VALID_RUN_JSON.replace('"value": "api"', '"value": "Bearer top-secret"'),
            "value",
        ),
    ],
)
def test_run_artifact_rejects_verifier_reported_boundary_values(
    invalid_json: str, field_name: str
) -> None:
    # Given: a valid run JSON payload with one verifier-reported unsafe value.
    # When: the public JSON boundary validates the artifact.
    # Then: the affected field is rejected rather than persisted.
    with pytest.raises(ValidationError, match=field_name):
        RunArtifact.model_validate_json(invalid_json)


def valid_report_inputs() -> tuple[SummaryArtifact, ComparisonResult]:
    run = RunArtifact.model_validate_json(VALID_RUN_JSON)
    summary = SummaryArtifact.model_validate_json(valid_summary_json(run))
    result = ComparisonResult(
        metric_id="cpu-system",
        direction=Direction.HIGHER_IS_WORSE,
        status=Status.INCONCLUSIVE,
        method=ComparisonMethod.BASELINE_REFERENCE,
        reference_anomaly=False,
    )
    return summary, result


def test_comparison_report_rejects_cohort_policy_hash_mismatch() -> None:
    # Given: otherwise valid cohorts and a report policy hash that differs.
    summary, result = valid_report_inputs()

    # When: the report crosses its Pydantic boundary.
    # Then: the report rejects summaries from a different policy snapshot.
    with pytest.raises(ValidationError, match="policy hash"):
        ComparisonReport(
            policy_sha256="0" * 64,
            suite_status=Status.INCONCLUSIVE,
            cohorts=ComparisonCohorts(current=(summary,), baseline=()),
            metric_results=(result,),
        )


def test_comparison_report_rejects_duplicate_metric_result_ids() -> None:
    # Given: otherwise valid report data with one repeated metric outcome.
    summary, result = valid_report_inputs()

    # When: the report crosses its Pydantic boundary.
    # Then: duplicate metric result identifiers are rejected.
    with pytest.raises(ValidationError, match="duplicate report metric"):
        ComparisonReport(
            policy_sha256=summary.policy_sha256,
            suite_status=Status.INCONCLUSIVE,
            cohorts=ComparisonCohorts(current=(summary,), baseline=()),
            metric_results=(result, result),
        )
