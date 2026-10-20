"""Validated narrow evidence excerpts for executable lessons."""

from __future__ import annotations

from typing import ClassVar, TypedDict

from pydantic import BaseModel, ConfigDict, Field, JsonValue

__all__ = (
    "RawEvidence",
    "ReportEvidence",
    "SummaryEvidence",
    "parse_raw_evidence",
    "parse_report_evidence",
    "parse_summary_evidence",
)


class RawEvidence(TypedDict):
    """Displayed raw-run fields validated at the JSON boundary."""

    run_id: str
    schema_version: int
    metric_record_count: int


class SummaryEvidence(TypedDict):
    """Displayed summary fields validated at the JSON boundary."""

    summary_id: str
    source_run_id: str
    metric_record_count: int
    eligible: bool


class ReportEvidence(TypedDict):
    """Displayed comparison report fields validated at the JSON boundary."""

    suite_status: str
    metric_id: str
    method: str
    metric_status: str


class _RawPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    run_id: str
    schema_version: int
    metric_records: tuple[JsonValue, ...]


class _EligibilityPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    eligible: bool


class _MetricSummaryPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    eligibility: _EligibilityPayload


class _SummaryMetricPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    summary: _MetricSummaryPayload


class _SummaryPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    summary_id: str
    source_run_id: str
    metric_records: tuple[_SummaryMetricPayload, ...] = Field(min_length=1)


class _ReportMetricPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    metric_id: str
    method: str
    status: str


class _ReportPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    suite_status: str
    metrics: tuple[_ReportMetricPayload, ...] = Field(min_length=1)


def parse_raw_evidence(payload: bytes) -> RawEvidence:
    """Parse only the raw artifact fields displayed by the collect lesson."""
    raw = _RawPayload.model_validate_json(payload)
    return {
        "run_id": raw.run_id,
        "schema_version": raw.schema_version,
        "metric_record_count": len(raw.metric_records),
    }


def parse_summary_evidence(payload: bytes) -> SummaryEvidence:
    """Parse only the summary artifact fields displayed by the lesson."""
    summary = _SummaryPayload.model_validate_json(payload)
    first_record = summary.metric_records[0]
    return {
        "summary_id": summary.summary_id,
        "source_run_id": summary.source_run_id,
        "metric_record_count": len(summary.metric_records),
        "eligible": first_record.summary.eligibility.eligible,
    }


def parse_report_evidence(payload: bytes) -> ReportEvidence:
    """Parse only the comparison report fields displayed by the lesson."""
    report = _ReportPayload.model_validate_json(payload)
    first_metric = report.metrics[0]
    return {
        "suite_status": report.suite_status,
        "metric_id": first_metric.metric_id,
        "method": first_metric.method,
        "metric_status": first_metric.status,
    }
