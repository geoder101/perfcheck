"""Markdown report rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from perfcheck.report_schemas import Report, ReportCohort, ReportMetric


def render_markdown_report(report: Report) -> str:
    """Render the report as escaped, LF-only review Markdown."""
    rows = [
        "# Perfcheck report",
        "",
        f"Suite status: {_escape(report.suite_status)}",
        "",
        (
            "| Metric | Statistic | Status | Current | Baseline | Effect | CI | "
            "Threshold | Warning | Fingerprint | Reason |"
        ),
        "| --- | --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- | --- |",
    ]
    rows.extend(_markdown_metric(metric) for metric in report.metrics)
    rows.extend(
        (
            "",
            "## Exclusions",
            "",
            "| Metric | Cohort | Run | Reason |",
            "| --- | --- | --- | --- |",
        )
    )
    rows.extend(
        "| "
        + " | ".join(
            (
                _escape(metric.metric_id),
                _escape(exclusion.cohort),
                _escape(exclusion.source_run_id),
                _escape(exclusion.reason),
            )
        )
        + " |"
        for metric in report.metrics
        for exclusion in metric.exclusions
    )
    rows.extend(("", "## Provenance", "", "| Field | Value |", "| --- | --- |"))
    rows.extend(
        (
            f"| Policy ID | {_escape(report.provenance.policy_id)} |",
            f"| Suite ID | {_escape(report.provenance.suite_id)} |",
            f"| Policy SHA-256 | {_escape(report.provenance.policy_sha256)} |",
            (
                "| Algorithm manifest | "
                f"{_escape(report.provenance.algorithm_manifest.report)} |"
            ),
        )
    )
    return "\n".join(rows) + "\n"


def _markdown_metric(metric: ReportMetric) -> str:
    ci = (
        "-"
        if metric.diagnostic_lower_bound is None
        else (
            f"{_number(metric.diagnostic_lower_bound)} "
            f"to {_number(metric.diagnostic_upper_bound)}"
        )
    )
    return (
        "| "
        + " | ".join(
            (
                _escape(metric.metric_id),
                _escape(metric.statistic),
                _escape(metric.status),
                _cohort_values(metric.current),
                _cohort_values(metric.baseline),
                _number(metric.effect),
                ci,
                _number(metric.practical_threshold),
                _escape(str(metric.sample_size_warning)),
                _escape(metric.comparison_fingerprint),
                _escape(metric.reason or "-"),
            )
        )
        + " |"
    )


def _number(value: float | None) -> str:
    return "-" if value is None else f"{value:+.6f}"


def _cohort_values(cohort: ReportCohort) -> str:
    values = ", ".join(_number(sample.value) for sample in cohort.values)
    return f"{cohort.count}: [{values}]"


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("`", "\\`")
        .replace("\r\n", "<br>")
        .replace("\n", "<br>")
        .replace("\r", "<br>")
    )
