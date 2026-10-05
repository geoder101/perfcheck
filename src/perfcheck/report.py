"""Public compatibility facade for report construction and rendering."""

from perfcheck.report_assembly import build_report
from perfcheck.report_json import render_json_report
from perfcheck.report_markdown import render_markdown_report
from perfcheck.report_schemas import (
    Report,
    ReportCohort,
    ReportExclusion,
    ReportMetric,
    ReportOptions,
    ReportProvenance,
    ReportSample,
)

__all__ = (
    "Report",
    "ReportCohort",
    "ReportExclusion",
    "ReportMetric",
    "ReportOptions",
    "ReportProvenance",
    "ReportSample",
    "build_report",
    "render_json_report",
    "render_markdown_report",
)
