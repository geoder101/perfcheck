"""Typed domain errors for perfcheck boundaries."""

from dataclasses import dataclass
from enum import StrEnum


class PerfcheckError(ValueError):
    """Base error for failures that cross a perfcheck boundary."""


class ArtifactSchemaCode(StrEnum):
    """Stable typed validation failure messages for public schemas."""

    NON_UTC_TIMESTAMP = "timestamp must use UTC"
    INVALID_TIMESTAMP_FORMAT = "timestamp must use RFC-3339 UTC syntax"
    INVALID_INTERVAL = "interval end must follow start"
    CREDENTIAL_LABEL = "sensitive label names are not permitted"
    CREDENTIAL_LABEL_VALUE = "sensitive label values are not permitted"
    CREDENTIAL_METADATA = "run metadata must not contain credentials"
    DUPLICATE_LABEL = "series labels must be unique"
    LABEL_ORDER = "series labels must be sorted"
    INVALID_SAMPLE_ORDER = "sample timestamps must strictly increase"
    INVALID_ENDPOINT_URL = "endpoint URL must be credential-free HTTP(S)"
    CREDENTIAL_QUERY = "query must not contain credential-bearing data"
    CREDENTIAL_DETAIL = "failure detail must not contain credentials"
    INVALID_COLLECTION_RECORD = "availability must agree with series or failure"
    DUPLICATE_LABEL_NAME = "expected label names must be unique"
    LABEL_NAME_ORDER = "expected label names must be sorted"
    DUPLICATE_METRIC_ID = "policy metric identifiers must be unique"
    MISSING_ENABLED_METRIC = "policy requires one enabled metric"
    POLICY_HASH_MISMATCH = "policy hash must match policy snapshot"
    SUITE_MISMATCH = "suite ID must match policy snapshot"
    DUPLICATE_METRIC_RECORD = "metric records must be unique"
    METRIC_SET_MISMATCH = "metric records must match policy metrics"
    PROVENANCE_INTERVAL_MISMATCH = "query provenance interval must match source"
    SERIES_METRIC_MISMATCH = "series metric ID must match record"
    LABEL_SET_MISMATCH = "series labels must match policy exactly"
    QUERY_PROVENANCE_MISMATCH = "query provenance must match policy metric"
    ELIGIBILITY_REASON_MISMATCH = "eligibility and reason must agree"
    SUMMARY_VALUE_MISMATCH = "eligibility and summary value must agree"
    INVALID_SUMMARY_RECORD = "availability must agree with summary or failure"
    MANIFEST_MISMATCH = "summary manifest must match policy snapshot"
    STATISTIC_MISMATCH = "summary statistic must match policy metric"
    DUPLICATE_SOURCE_RUN = "duplicate source run identifiers are invalid"
    DUPLICATE_SOURCE_CONTENT = "duplicate source content hashes are invalid"
    INVALID_COMPARISON_OPTIONS = "comparison options must agree with method"
    DUPLICATE_REPORT_METRIC = "duplicate report metric identifiers are invalid"


@dataclass(frozen=True, slots=True)
class ArtifactSchemaError(PerfcheckError):
    """An artifact violates its declared public schema."""

    code: ArtifactSchemaCode

    def __str__(self) -> str:
        """Render the schema context for command-line diagnostics."""
        return self.code


@dataclass(frozen=True, slots=True)
class ArtifactIntegrityError(PerfcheckError):
    """A persisted artifact does not match its declared immutable identity."""

    artifact_id: str
    detail: str

    def __str__(self) -> str:
        """Render the immutable identity that failed verification."""
        return f"artifact integrity failure for {self.artifact_id}: {self.detail}"


@dataclass(frozen=True, slots=True)
class PolicyMismatchError(PerfcheckError):
    """Validated artifacts cannot be compared under one policy contract."""

    expected_policy_sha256: str
    actual_policy_sha256: str

    def __str__(self) -> str:
        """Render both policy hashes for compatibility diagnostics."""
        return (
            "policy mismatch: expected "
            f"{self.expected_policy_sha256}, received {self.actual_policy_sha256}"
        )
