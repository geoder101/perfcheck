from typing import Final

import pytest
from pydantic import ValidationError

from perfcheck.models import (
    ARTIFACT_ADAPTER,
    V1_ALGORITHM_MANIFEST,
    ComparisonCohorts,
    RunArtifact,
    SuitePolicy,
    SummaryArtifact,
)

VALID_RUN_JSON: Final = """
{
  "artifact_type": "run",
  "schema_version": 1,
  "content_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "run_id": "run-1",
  "suite_id": "suite-1",
  "source_interval": {
    "start": "2026-01-01T00:00:00Z",
    "end": "2026-01-01T00:10:00Z"
  },
  "policy_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "policy_snapshot": {
    "schema_version": 1,
    "policy_id": "policy-1",
    "suite_id": "suite-1",
    "policy_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "metrics": [
      {
        "metric_id": "cpu-system",
        "query": "sum(rate(node_cpu_seconds_total{mode=\\\"system\\\"}[1m]))",
        "expected_label_names": ["job"],
        "unit": "percent",
        "direction": "higher_is_worse",
        "statistic": "mean",
        "practical_threshold": 1.5,
        "step_seconds": 15,
        "rate_window_seconds": 60,
        "eligibility": {
          "warmup_seconds": 0,
          "cooldown_seconds": 0,
          "min_analysis_window_seconds": 300,
          "min_points": 20,
          "min_coverage": 0.8,
          "max_gap_steps": 3
        }
      }
    ],
    "comparison_mode": "auto",
    "min_current_runs": 5,
    "min_baseline_runs": 10,
    "min_baseline_reference_runs": 10,
    "nominal_alpha": 0.05,
    "algorithm_manifest": {
      "summary": "linear-quantile-v1",
      "eligibility": "trim-coverage-gap-v1",
      "bootstrap": "pcg64-percentile-v1",
      "report": "canonical-json-markdown-v1"
    }
  },
  "metadata": {
    "test_name": "load-test",
    "git_sha": "abcdef",
    "environment": "ci",
    "scenario": "baseline",
    "target_topology": "single-node"
  },
  "metric_records": [
    {
      "metric_id": "cpu-system",
      "availability": "available",
      "provenance": {
        "endpoint_url": "https://metrics.example.test/prometheus",
        "request_path": "/api/v1/query_range",
        "query": "sum(rate(node_cpu_seconds_total{mode=\\\"system\\\"}[1m]))",
        "start": "2026-01-01T00:00:00Z",
        "end": "2026-01-01T00:10:00Z",
        "step_seconds": 15,
        "http_status": 200,
        "prometheus_status": "success"
      },
      "series": {
        "metric_id": "cpu-system",
        "labels": [{"name": "job", "value": "api"}],
        "samples": [
          {"timestamp": "2026-01-01T00:00:00Z", "value": 2.25},
          {"timestamp": "2026-01-01T00:00:15Z", "value": 2.5}
        ]
      }
    }
  ]
}
"""

SUMMARY_CONTENT_SHA256: Final = "c" * 64
SOURCE_CONTENT_SHA256: Final = "a" * 64
POLICY_SHA256: Final = "b" * 64
COMPATIBILITY_FINGERPRINT: Final = "d" * 64


def valid_summary_json(run: RunArtifact) -> str:
    return f"""
    {{
      "artifact_type": "summary",
      "schema_version": 1,
      "content_sha256": "{SUMMARY_CONTENT_SHA256}",
      "summary_id": "summary-1",
      "source_run_id": "run-1",
      "source_content_sha256": "{SOURCE_CONTENT_SHA256}",
      "source_interval": {{
        "start": "2026-01-01T00:00:00Z",
        "end": "2026-01-01T00:10:00Z"
      }},
      "policy_sha256": "{POLICY_SHA256}",
      "policy_snapshot": {run.policy_snapshot.model_dump_json()},
      "algorithm_manifest": {{
        "summary": "linear-quantile-v1",
        "eligibility": "trim-coverage-gap-v1",
        "bootstrap": "pcg64-percentile-v1",
        "report": "canonical-json-markdown-v1"
      }},
      "metric_records": [
        {{
          "metric_id": "cpu-system",
          "availability": "available",
          "summary": {{
            "statistic": "mean",
            "value": 2.375,
            "point_count": 21,
            "compatibility_fingerprint": "{COMPATIBILITY_FINGERPRINT}",
            "eligibility": {{
              "eligible": true,
              "reason": null,
              "analysis_start": "2026-01-01T00:00:00Z",
              "analysis_end": "2026-01-01T00:10:00Z",
              "retained_points": 21,
              "expected_points": 41,
              "coverage": 0.8
            }}
          }}
        }}
      ]
    }}
    """


def test_v1_artifacts_round_trip_through_discriminator() -> None:
    # Given: complete strict v1 raw and summary artifact JSON.
    run = RunArtifact.model_validate_json(VALID_RUN_JSON)
    summary = SummaryArtifact.model_validate_json(valid_summary_json(run))

    # When: each artifact is validated through the public discriminator and serialized.
    parsed_run = ARTIFACT_ADAPTER.validate_json(run.model_dump_json())
    parsed_summary = ARTIFACT_ADAPTER.validate_json(summary.model_dump_json())

    # Then: JSON round trips retain their validated immutable contract.
    assert parsed_run == run
    assert parsed_summary == summary
    assert run.policy_snapshot.algorithm_manifest == V1_ALGORITHM_MANIFEST


def test_schema_validation_rejects_unknown_major_version() -> None:
    # Given: a v1 run fixture relabelled as an unsupported schema version.
    invalid_json = VALID_RUN_JSON.replace(
        '"schema_version": 1', '"schema_version": 2', 1
    )

    # When: the artifact crosses the JSON boundary.
    # Then: validation reports the versioned schema failure.
    with pytest.raises(ValidationError, match="schema_version"):
        _ = RunArtifact.model_validate_json(invalid_json)


@pytest.mark.parametrize(
    ("invalid_json", "field_name"),
    [
        (VALID_RUN_JSON.replace('"value": 2.25', '"value": NaN'), "value"),
        (
            VALID_RUN_JSON.replace(
                "2026-01-01T00:00:00Z", "not-an-rfc3339-timestamp", 1
            ),
            "start",
        ),
        (
            VALID_RUN_JSON.replace(
                '"artifact_type": "run"',
                '"unexpected": true, "artifact_type": "run"',
                1,
            ),
            "unexpected",
        ),
        (
            VALID_RUN_JSON.replace('"statistic": "mean"', '"statistic": "median"'),
            "statistic",
        ),
        (VALID_RUN_JSON.replace('"unit": "percent"', '"unit": "watts"'), "unit"),
        (VALID_RUN_JSON.replace('"run_id": "run-1"', '"run_id": ""'), "run_id"),
        (
            VALID_RUN_JSON.replace(
                "https://metrics.example.test/prometheus",
                "https://bearer-token@metrics.example.test/prometheus",
            ),
            "endpoint_url",
        ),
    ],
)
def test_schema_validation_rejects_malformed_public_values(
    invalid_json: str, field_name: str
) -> None:
    # Given: a fixture with one malformed public boundary value.
    # When: it is parsed as a strict run artifact.
    # Then: validation identifies the affected contract field.
    with pytest.raises(ValidationError, match=field_name):
        _ = RunArtifact.model_validate_json(invalid_json)


def test_schema_validation_rejects_invalid_eligibility_limits() -> None:
    # Given: a validated policy snapshot with an impossible coverage requirement.
    run = RunArtifact.model_validate_json(VALID_RUN_JSON)
    invalid_json = run.policy_snapshot.model_dump_json().replace(
        '"min_coverage":0.8', '"min_coverage":1.1'
    )

    # When: the policy crosses the JSON boundary.
    # Then: the strict eligibility model rejects it.
    with pytest.raises(ValidationError, match="min_coverage"):
        _ = SuitePolicy.model_validate_json(invalid_json)


def test_comparison_cohorts_reject_duplicate_source_identifiers() -> None:
    # Given: two summary inputs representing the same source run.
    run = RunArtifact.model_validate_json(VALID_RUN_JSON)
    summary = SummaryArtifact.model_validate_json(valid_summary_json(run))

    # When: they are supplied to one comparison cohort boundary.
    # Then: duplicate source identity is rejected before a decision can run.
    with pytest.raises(ValidationError, match="duplicate"):
        _ = ComparisonCohorts(current=(summary, summary), baseline=())
