"""Bounded probability experiments and offline evidence plots, without Marimo."""

import math
from dataclasses import dataclass
from html import escape
from statistics import NormalDist
from typing import Final

import numpy as np

MAX_REPETITIONS: Final = 2000
MAX_FLIPS: Final = 40


def coin_distribution(n: int) -> tuple[float, ...]:
    """Enumerate the exact Binomial(n, 1/2) probability masses."""
    if not 1 <= n <= MAX_FLIPS:
        message = "coin budget requires 1..40 flips"
        raise ValueError(message)
    return tuple(math.comb(n, k) / 2**n for k in range(n + 1))


def coin_experiment(n: int, repetitions: int) -> tuple[int, ...]:
    """Count heads in independently repeated fair-coin experiments, seed 601."""
    _ = coin_distribution(n)
    if not 1 <= repetitions <= MAX_REPETITIONS:
        message = "coin budget requires 1..2000 repetitions"
        raise ValueError(message)
    draws = np.random.default_rng(601).binomial(n, 0.5, repetitions)
    return tuple(int(np.count_nonzero(draws == k)) for k in range(n + 1))


@dataclass(frozen=True, slots=True)
class MeanExperiment:
    """Independent observations and sample means in milliseconds."""

    individuals: tuple[float, ...]
    means: tuple[float, ...]
    theoretical_se: float


def mean_experiment(n: int, repetitions: int) -> MeanExperiment:
    """Sample IID Normal(100ms, (8ms)**2), using a fresh fixed seed 602."""
    if n not in (4, 16, 64) or not 2 <= repetitions <= MAX_REPETITIONS:
        message = "means budget requires n=4/16/64 and 2..2000 repetitions"
        raise ValueError(message)
    draws = np.random.default_rng(602).normal(100, 8, (repetitions, n))
    return MeanExperiment(
        tuple(float(value) for value in draws[:, 0]),
        tuple(float(value) for value in np.mean(draws, axis=1)),
        8 / math.sqrt(n),
    )


def normal_region(bounds: tuple[float, float]) -> tuple[float, float, float]:
    """Return normal density at the upper bound, interval area, and upper CDF."""
    low, high = bounds
    if not -4 <= low <= high <= 4:
        message = "normal region requires ordered bounds inside [-4, 4]"
        raise ValueError(message)
    model = NormalDist()
    return model.pdf(high), model.cdf(high) - model.cdf(low), model.cdf(high)


@dataclass(frozen=True, slots=True)
class PlotSeries:
    """Labeled points; bars, lines, and dashed lines remain distinct in grayscale."""

    label: str
    points: tuple[tuple[float, float], ...]
    bars: bool = False
    dashed: bool = False
    area: bool = False


def histogram(values: tuple[float, ...]) -> tuple[tuple[float, float], ...]:
    """Bin milliseconds on a common 60..140ms grid, retaining overflow in edges."""
    counts = [0] * 40
    for value in values:
        index = min(39, max(0, math.floor((value - 60) / 2)))
        counts[index] += 1
    return tuple((61.0 + 2 * index, count / len(values)) for index, count in enumerate(counts))


def plot_svg(labels: tuple[str, str, str], series: tuple[PlotSeries, ...]) -> str:
    """Render a responsive, theme-inheriting SVG with numeric axes and text legend.

    Geometry uses one shared 640x300 viewBox, a 64-unit left margin, and a
    240-unit plotting baseline. No remote resources or plotting runtime is used.
    """
    title, x_label, y_label = (escape(label) for label in labels)
    points = tuple(point for item in series for point in item.points)
    x_min = min(point[0] for point in points)
    x_span = max(max(point[0] for point in points) - x_min, 1.0)
    y_max = max(max(point[1] for point in points), 0.001)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" '
        'width="100%" role="img" fill="currentColor">',
        f'<title>{title}</title>',
        f'<text x="64" y="20">{title}</text>',
        '<path d="M64 40V240H608" fill="none" stroke="currentColor"/>',
        f'<text x="64" y="38" font-size="12">{y_label}</text>',
        f'<text x="280" y="280" font-size="12">{x_label}</text>',
    ]
    for tick in range(5):
        fraction = tick / 4
        parts.extend((
            f'<text x="8" y="{244 - 192 * fraction:.1f}" font-size="12">'
            f'{y_max * fraction:.3g}</text>',
            f'<text x="{64 + 544 * fraction:.1f}" y="258" font-size="12">'
            f'{x_min + x_span * fraction:.3g}</text>',
        ))
    for item in series:
        coordinates = tuple((64 + 544 * (x - x_min) / x_span, 240 - 192 * y / y_max) for x, y in item.points)
        if item.bars:
            width = min(12.0, 400 / len(coordinates))
            parts.extend(f'<rect x="{x - width / 2:.2f}" y="{y:.2f}" width="{width:.2f}" height="{240 - y:.2f}" opacity="0.35"/>' for x, y in coordinates)
        else:
            path = " ".join(f"{x:.2f},{y:.2f}" for x, y in coordinates)
            dash = ' stroke-dasharray="6 4"' if item.dashed else ""
            parts.append(f'<polyline points="{path}" fill="none" stroke="currentColor" stroke-width="2"{dash}/>')
            if item.area:
                parts.append(f'<polygon points="{coordinates[0][0]:.2f},240 {path} {coordinates[-1][0]:.2f},240" opacity="0.18"/>')
    parts.append('</svg><p>Legend: ' + "; ".join(escape(item.label) for item in series) + '</p>')
    return "".join(parts)
