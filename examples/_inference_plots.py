"""Inline, theme-inheriting geometry for inference laboratory figures."""

from dataclasses import dataclass
from html import escape
from typing import TYPE_CHECKING

import numpy as np

from examples._inference_chart_frame import (
    LegendEntry,
    PlotSpec,
    chart_frame,
    chart_key,
    point_glyph,
)

__all__ = ("PlotSpec", "Series", "histogram", "interval_plot", "line_plot")

if TYPE_CHECKING:
    from examples._inference import CoverageResult, FloatVector


@dataclass(frozen=True, slots=True)
class Series:
    """A named curve; legends also identify its dash and region pattern."""

    label: str
    points: tuple[tuple[float, float], ...]
    shade: bool = False


def line_plot(
    spec: PlotSpec, series: tuple[Series, ...], marker: tuple[float, str] | None = None
) -> str:
    """Render actual coordinates, including visible point-only and coincident series."""
    points = tuple(point for curve in series for point in curve.points)
    xmin = min(x for x, _ in points)
    xmax = max(x for x, _ in points)
    if marker is not None:
        xmin = min(xmin, marker[0])
        xmax = max(xmax, marker[0])
    single_x = xmin == xmax
    if single_x:
        xmin, xmax = xmin - 0.5, xmax + 0.5
    ymax = max(0.01, *(y for _, y in points)) * 1.08
    span = xmax - xmin

    def px(x: float) -> float:
        return 120 + 560 * (x - xmin) / span

    def py(y: float) -> float:
        return 250 - 200 * y / ymax

    parts = [
        '<g fill="currentColor" font-family="sans-serif" font-size="16">',
        '<path d="M120 40 V250 H680" fill="none" stroke="currentColor"/>',
    ]
    x_ticks = (0.5,) if single_x else (0.0, 0.25, 0.5, 0.75, 1.0)
    parts.extend(
        f'<text x="{px(x):.2f}" y="282" text-anchor="middle">{x:.3g}</text>'
        for x in (xmin + span * fraction for fraction in x_ticks)
    )
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = ymax * fraction
        parts.append(f'<text x="112" y="{py(y):.2f}" text-anchor="end">{y:.3g}</text>')
    entries: list[LegendEntry] = []
    for index, curve in enumerate(series):
        pattern = ("none", "7 4", "2 3", "10 3 2 3")[index % 4]
        coordinates = " ".join(f"{px(x):.2f},{py(y):.2f}" for x, y in curve.points)
        degenerate = len(set(curve.points)) == 1
        entries.append(LegendEntry(curve.label, index, degenerate, curve.shade))
        parts.append(f'<g data-series="{escape(curve.label, quote=True)}">')
        if curve.shade:
            fill = ("hatch", "dots")[index % 2]
            area = (
                f'<polygon points="{px(curve.points[0][0]):.2f},250 {coordinates} '
                f'{px(curve.points[-1][0]):.2f},250" '
                f'fill="url(#{chart_key(spec)}-{fill})"/>'
            )
            parts.append(area)
        if degenerate:
            x, y = curve.points[0]
            parts.append(point_glyph(index, (px(x), py(y))))
        else:
            curve_line = (
                f'<polyline points="{coordinates}" fill="none" '
                f'stroke="currentColor" stroke-width="2" '
                f'stroke-dasharray="{pattern}"/>'
            )
            parts.append(curve_line)
        parts.append("</g>")
    if marker is not None:
        reference = (
            f'<path d="M{px(marker[0]):.2f} 40 V250" fill="none" '
            'stroke="currentColor" stroke-dasharray="4 4"/>'
        )
        parts.append(reference)
        entries.append(
            LegendEntry(f"{marker[1]} = {marker[0]:.4g} (vertical dashed)", 1)
        )
    return chart_frame(spec, "".join((*parts, "</g>")), tuple(entries))


def histogram(
    values: tuple[float, ...], spec: PlotSpec, marker: tuple[float, str]
) -> str:
    """Show actual bootstrap draw counts, not an invented normal approximation."""
    counts, raw_edges = np.histogram(values, bins=32)
    edges: FloatVector = np.asarray(raw_edges, dtype=np.float64)
    boundaries = tuple(float(edge) for edge in edges)
    points = tuple(
        point
        for left, right, count in zip(
            boundaries[:-1], boundaries[1:], counts, strict=True
        )
        for point in ((float(left), float(count)), (float(right), float(count)))
    )
    return line_plot(
        spec,
        (Series("Bootstrap draw counts (solid, hatched)", points, shade=True),),
        marker,
    )


def interval_plot(result: CoverageResult) -> str:
    """Show up to forty intervals with solid containment and dashed misses."""
    shown = result.intervals[:40]
    low = min(row.lower for row in shown)
    high = max(row.upper for row in shown)
    span = max(high - low, 0.01)
    parts = [
        '<g fill="currentColor" font-family="sans-serif" font-size="16">',
        '<path d="M120 16 V256 H680" fill="none" stroke="currentColor"/>',
    ]
    for index, row in enumerate(shown):
        y = 20 + index * 6
        pattern = "none" if row.contains else "3 3"
        x1 = 120 + 560 * (row.lower - low) / span
        x2 = 120 + 560 * (row.upper - low) / span
        interval = (
            f'<line x1="{x1:.2f}" x2="{x2:.2f}" y1="{y}" y2="{y}" '
            f'stroke="currentColor" stroke-width="2" stroke-dasharray="{pattern}"/>'
        )
        parts.append(interval)
        if index % 10 == 0:
            parts.append(f'<text x="112" y="{y}" text-anchor="end">{index + 1}</text>')
    true_x = 120 + 560 * (100 - low) / span
    reference = (
        f'<path d="M{true_x:.2f} 16 V256" stroke="currentColor" '
        'stroke-dasharray="8 4"/>'
    )
    parts.append(reference)
    for fraction in (0.0, 0.5, 1.0):
        value = low + span * fraction
        x = 120 + 560 * fraction
        parts.append(f'<text x="{x}" y="285" text-anchor="middle">{value:.3g}</text>')
    return chart_frame(
        PlotSpec(
            "First 40 known-sigma intervals",
            "Population mean (ms)",
            "Repetition (index)",
        ),
        "".join((*parts, "</g>")),
        (
            LegendEntry("Contains true mean (solid)", 0),
            LegendEntry("Misses true mean (short dashed)", 1),
            LegendEntry("True mean 100 ms (vertical long dashed)", 3),
        ),
    )
