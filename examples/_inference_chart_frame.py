"""Readable HTML labels and patterned SVG keys for inference figures."""

from dataclasses import dataclass
from hashlib import sha256
from html import escape


@dataclass(frozen=True, slots=True)
class PlotSpec:
    """Accessible chart labels with the units of both axes."""

    title: str
    x_label: str
    y_label: str


@dataclass(frozen=True, slots=True)
class LegendEntry:
    """A curve's visual key, shared by its plot geometry and HTML legend."""

    label: str
    index: int
    point: bool = False
    shaded: bool = False


def chart_key(spec: PlotSpec) -> str:
    """Scope SVG fill references to this named figure without random identifiers."""
    return "inference-" + sha256(spec.title.encode()).hexdigest()[:12]


def point_glyph(index: int, position: tuple[float, float]) -> str:
    """Nested circle/square and short cutoff segment keep coincident series visible."""
    x, y = position
    shapes = (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="currentColor"/>',
        (
            f'<rect x="{x - 8:.2f}" y="{y - 8:.2f}" width="16" height="16" '
            'fill="none" stroke="currentColor" stroke-width="2"/>'
        ),
        (
            f'<line x1="{x - 14:.2f}" x2="{x + 14:.2f}" y1="{y:.2f}" '
            f'y2="{y:.2f}" stroke="currentColor" stroke-width="3" '
            'stroke-dasharray="3 2"/>'
        ),
    )
    return shapes[index % len(shapes)]


def chart_frame(spec: PlotSpec, body: str, entries: tuple[LegendEntry, ...]) -> str:
    """Keep labels in HTML and scale only tick text with the chart container."""
    key = chart_key(spec)
    definitions = (
        f'<defs><pattern id="{key}-hatch" width="8" height="8" '
        'patternUnits="userSpaceOnUse"><path d="M-2 2 L2 -2 M0 8 L8 0 M6 10 L10 6" '
        'stroke="currentColor" stroke-width="1.5"/></pattern>'
        f'<pattern id="{key}-dots" width="8" height="8" '
        'patternUnits="userSpaceOnUse"><circle cx="4" cy="4" r="1.5" '
        'fill="currentColor"/></pattern></defs>'
    )
    legend: list[str] = []
    for entry in entries:
        dash = ("none", "7 4", "2 3", "10 3 2 3")[entry.index % 4]
        fill = ("hatch", "dots")[entry.index % 2]
        texture = (
            (
                f'<rect x="1" y="1" width="36" height="18" '
                f'fill="url(#{key}-{fill})" stroke="currentColor"/>'
            )
            if entry.shaded
            else ""
        )
        sample = (
            point_glyph(entry.index, (19.0, 10.0))
            if entry.point
            else (
                '<path d="M1 10 H37" stroke="currentColor" stroke-width="2" '
                f'stroke-dasharray="{dash}"/>'
            )
        )
        item = (
            '<li style="display:flex;align-items:center;gap:.6rem;margin:.35rem 0">'
            '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20" '
            'viewBox="0 0 40 20" aria-hidden="true" style="flex:none">'
        )
        legend.append(
            item
            + texture
            + sample
            + "</svg><span>"
            + escape(entry.label)
            + "</span></li>"
        )
    opening = (
        '<figure class="inference-figure" style="margin:0;width:100%;'
        'container-type:inline-size;container-name:inference-plot">'
        "<style>@container inference-plot (max-width:650px) "
        "{.inference-plot text{font-size:22px}}"
        "@container inference-plot (max-width:440px) "
        "{.inference-plot text{font-size:32px}}</style>"
        f'<figcaption style="font-weight:600">{escape(spec.title)}</figcaption>'
        f'<div data-axis="y">Vertical axis: {escape(spec.y_label)}</div>'
        '<svg xmlns="http://www.w3.org/2000/svg" class="inference-plot" '
        'viewBox="0 0 720 300" role="img" style="width:100%;height:auto" '
        f'aria-label="{escape(spec.title, quote=True)}">'
        f"<title>{escape(spec.title)}</title>"
    )
    closing = (
        f'</svg><div data-axis="x">Horizontal axis: {escape(spec.x_label)}</div>'
        '<ul style="list-style:none;margin:.5rem 0;padding:0">'
    )
    return opening + definitions + body + closing + "".join(legend) + "</ul></figure>"
