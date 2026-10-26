"""Responsive presentation of capstone evidence without changing CLI receipts."""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING, Final

import marimo as mo

from examples._capstone_evidence import CapstoneReport
from examples._support import parse_summary_evidence

if TYPE_CHECKING:
    from examples._capstone import CapstoneReceipt

_BOUNDS: Final = "width: 100%; max-width: 100%; min-width: 0;"
_WRAP: Final = "white-space: pre-wrap; overflow-wrap: anywhere;"


def render_capstone_evidence(receipt: CapstoneReceipt) -> mo.Html:
    """Keep a wrapped decision summary above complete, focusable report regions."""
    report = CapstoneReport.model_validate_json(receipt.report_json)
    metric = report.metrics[0]
    eligible = all(
        parse_summary_evidence(payload)["eligible"]
        for payload in receipt.summary_artifacts
    )
    summary = "\n".join(
        (
            f"Selected scenario: {receipt.scenario.value}",
            f"Suite status: {report.suite_status}",
            f"Compare exit status: {receipt.comparison_status}",
            f"Eligible summaries: {eligible}",
            f"Baseline runs: {metric.baseline.count}",
            f"Current runs: {metric.current.count}",
            f"Method: {metric.method}",
            f"Oriented effect: {metric.effect} {metric.unit}",
            f"Decision lower bound: {metric.decision_lower_bound}",
            f"Practical threshold: {metric.practical_threshold} {metric.unit}",
            f"Reference anomaly: {metric.reference_anomaly}",
            f"Overwrite exit status: {receipt.overwrite_status}",
        )
    )
    json_report = escape(receipt.report_json.decode())
    markdown_report = mo.md(receipt.report_markdown).text
    return mo.Html(
        f"""
        <style>
          .capstone-evidence table {{
            display: table;
            overflow: visible;
            width: max-content;
            max-width: none;
          }}
        </style>
        <div class="capstone-evidence" style="{_BOUNDS} contain: inline-size;">
          <section aria-label="Capstone decision summary"
                   style="{_BOUNDS} overflow-wrap: anywhere;">
            <h3>Decision summary</h3>
            <p style="{_WRAP}">{escape(summary)}</p>
            <p>Full reports follow. On narrow screens, focus the Markdown report
               and use the arrow keys to scroll horizontally when needed.</p>
          </section>
          <h3>Full JSON report</h3>
          <div role="region" aria-label="Full JSON report" tabindex="0"
               style="{_BOUNDS} overflow-x: auto;">
            <pre style="{_BOUNDS} {_WRAP}"><code>{json_report}</code></pre>
          </div>
          <h3>Full Markdown report</h3>
          <div role="region" aria-label="Full Markdown report" tabindex="0"
               style="{_BOUNDS} overflow-x: auto;">
            {markdown_report}
          </div>
        </div>
        """
    )
