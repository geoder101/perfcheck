"""Schema-only artifact fixtures with placeholder hashes, not verified evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from perfcheck.models import RunArtifact

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
