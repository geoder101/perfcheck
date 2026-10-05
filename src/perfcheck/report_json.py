"""Canonical JSON report rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from perfcheck.storage import canonical_json_bytes

if TYPE_CHECKING:
    from perfcheck.report_schemas import Report


def render_json_report(report: Report) -> str:
    """Render the report using the normative canonical JSON encoding."""
    return canonical_json_bytes(report).decode()
