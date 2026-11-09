import pytest
from pydantic import ValidationError

from perfcheck.models import RunArtifact
from tests.artifact_schema_support import VALID_RUN_JSON


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
        _ = RunArtifact.model_validate_json(invalid_json)
