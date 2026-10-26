"""Bounded probability experiments and offline evidence plots, without Marimo."""

import math
from dataclasses import dataclass
from html import escape
from statistics import NormalDist
from typing import Final

import numpy as np

MAX_REPETITIONS: Final = 2000
MAX_FLIPS: Final = 40
MIN_REPETITIONS: Final = 2
NORMAL_LIMIT: Final = 4


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
    generator = np.random.default_rng(601)
    counts = [0] * (n + 1)
    for _ in range(repetitions):
        counts[generator.binomial(n, 0.5)] += 1
    return tuple(counts)


@dataclass(frozen=True, slots=True)
class MeanExperiment:
    """Independent observations and sample means in milliseconds."""

    individuals: tuple[float, ...]
    means: tuple[float, ...]
    theoretical_se: float


def mean_experiment(n: int, repetitions: int) -> MeanExperiment:
    """Sample IID Normal(100ms, (8ms)**2), using a fresh fixed seed 602."""
    if n not in (4, 16, 64) or not MIN_REPETITIONS <= repetitions <= MAX_REPETITIONS:
        message = "means budget requires n=4/16/64 and 2..2000 repetitions"
        raise ValueError(message)
    generator = np.random.default_rng(602)
    draws = tuple(
        tuple(generator.normal(100, 8) for _ in range(n)) for _ in range(repetitions)
    )
    return MeanExperiment(
        tuple(row[0] for row in draws),
        tuple(math.fsum(row) / n for row in draws),
        8 / math.sqrt(n),
    )


def normal_region(bounds: tuple[float, float]) -> tuple[float, float, float]:
    """Return normal density at the upper bound, interval area, and upper CDF."""
    low, high = bounds
    if not -NORMAL_LIMIT <= low <= high <= NORMAL_LIMIT:
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
    return tuple(
        (61.0 + 2 * index, count / len(values)) for index, count in enumerate(counts)
    )


def plot_svg(labels: tuple[str, str, str], series: tuple[PlotSeries, ...]) -> str:
    """Keep chart text at 16px inside a bounded, keyboard-scrollable viewport."""
    title, x_label, y_label = (escape(label) for label in labels)
    if not series or any(not item.points for item in series):
        message = "plots require nonempty series with nonempty point collections"
        raise ValueError(message)
    points = tuple(point for item in series for point in item.points)
    if not all(math.isfinite(value) for point in points for value in point):
        message = "plot coordinates must be finite"
        raise ValueError(message)
    x_min = min(point[0] for point in points)
    x_span = max(max(point[0] for point in points) - x_min, 1.0)
    y_min = min(0.0, *(point[1] for point in points))
    y_max = max(0.001, *(point[1] for point in points))
    y_span = y_max - y_min
    if not math.isfinite(x_span) or not math.isfinite(y_span):
        message = "plot axis spans must be finite"
        raise ValueError(message)
    parts = [
        '<figure style="margin:0;max-width:100%;min-width:0;font-size:16px">',
        f"<figcaption><strong>{title}</strong></figcaption>",
        f"<p>Vertical axis: {y_label}. Horizontal axis: {x_label}.</p>",
        "<p>On narrow screens, swipe or focus the chart and use arrow keys.</p>",
        (
            f'<div role="region" aria-label="{title}; scroll horizontally" '
            'tabindex="0" style="max-width:100%;overflow-x:auto">'
        ),
        (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 300" '
            'width="640" height="300" role="img" fill="currentColor" font-size="16" '
            'style="width:640px;height:300px;max-width:none;display:block">'
        ),
        f"<title>{title}</title>",
        '<path d="M64 40V240H608" fill="none" stroke="currentColor"/>',
    ]
    for tick in range(5):
        fraction = tick / 4
        parts.extend(
            (
                (
                    f'<text x="8" y="{244 - 192 * fraction:.1f}">'
                    f"{y_min + y_span * fraction:.3g}</text>"
                ),
                (
                    f'<text x="{64 + 544 * fraction:.1f}" y="262" text-anchor="middle">'
                    f"{x_min + x_span * fraction:.3g}</text>"
                ),
            )
        )
    for item in series:
        coordinates = tuple(
            (64 + (x - x_min) / x_span * 544, 240 - (y - y_min) / y_span * 192)
            for x, y in item.points
        )
        if item.bars:
            width = min(12.0, 400 / len(coordinates))
            parts.extend(
                "".join(
                    (
                        f'<rect x="{x - width / 2:.2f}" y="{y:.2f}"',
                        f' width="{width:.2f}" height="{240 - y:.2f}" opacity="0.35"/>',
                    )
                )
                for x, y in coordinates
            )
        else:
            path = " ".join(f"{x:.2f},{y:.2f}" for x, y in coordinates)
            dash = ' stroke-dasharray="6 4"' if item.dashed else ""
            parts.append(
                "".join(
                    (
                        f'<polyline points="{path}" fill="none" stroke="currentColor"',
                        f' stroke-width="2"{dash}/>',
                    )
                )
            )
            if item.dashed or len(coordinates) == 1:
                parts.extend(
                    f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3"/>' for x, y in coordinates
                )
            if item.area:
                parts.append(
                    "".join(
                        (
                            f'<polygon points="{coordinates[0][0]:.2f},240 {path} ',
                            f'{coordinates[-1][0]:.2f},240" opacity="0.18"/>',
                        )
                    )
                )
    parts.append(
        "</svg></div><p>Legend: "
        + "; ".join(escape(item.label) for item in series)
        + "</p></figure>"
    )
    return "".join(parts)


def coin_plot(n: int, k: int, repetitions: int) -> str:
    """Compare simulated frequencies, exact mass, and the selected discrete region."""
    mass = coin_distribution(n)
    if not 0 <= k <= n:
        message = "observed heads must be inside 0..n"
        raise ValueError(message)
    counts = coin_experiment(n, repetitions)
    return plot_svg(
        ("Fair coin: simulated vs exact", "Heads (count)", "Probability / frequency"),
        (
            PlotSeries(
                "bars: simulated frequency",
                tuple((float(i), c / repetitions) for i, c in enumerate(counts)),
                bars=True,
            ),
            PlotSeries(
                "solid: theoretical mass",
                tuple((float(i), p) for i, p in enumerate(mass)),
            ),
            PlotSeries(
                "dashed: selected upper-tail region",
                tuple((float(i), mass[i]) for i in range(k, n + 1)),
                dashed=True,
            ),
        ),
    )


def normal_plots(bounds: tuple[float, float]) -> tuple[str, str]:
    """Plot density with shaded selected area separately from cumulative mass."""
    _ = normal_region(bounds)
    low, high = bounds
    model = NormalDist()
    grid = tuple(-4 + i / 50 for i in range(401))
    region = sorted({low, high, *(x for x in grid if low <= x <= high)})
    density = plot_svg(
        (
            "Continuous density: interval area",
            "z (standard deviations)",
            "Density (per z unit)",
        ),
        (
            PlotSeries("solid: normal density", tuple((x, model.pdf(x)) for x in grid)),
            PlotSeries(
                "shading: interval area",
                tuple((x, model.pdf(x)) for x in region),
                area=True,
            ),
        ),
    )
    cdf = plot_svg(
        ("Cumulative probability", "z (standard deviations)", "F(z) (probability)"),
        (PlotSeries("solid: normal CDF", tuple((x, model.cdf(x)) for x in grid)),),
    )
    return density, cdf


def means_plot(experiment: MeanExperiment) -> str:
    """Compare individual observations and means on the same millisecond bins."""
    return plot_svg(
        (
            "Individuals vs sample means",
            "Latency (ms; overflow in edge bins)",
            "Frequency (2 ms bins)",
        ),
        (
            PlotSeries(
                "bars: individuals", histogram(experiment.individuals), bars=True
            ),
            PlotSeries(
                "dashed: sample means", histogram(experiment.means), dashed=True
            ),
        ),
    )
