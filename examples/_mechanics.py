"""Plain arithmetic shared by summary and mechanics lessons, not production APIs."""

import math
import random
from typing import Final

MAX_RESAMPLES: Final = 2000
MAX_COHORT_VALUES: Final = 64


def finite_values(values: tuple[float, ...]) -> tuple[float, ...]:
    """Require nonempty finite toy inputs before evaluating a formula."""
    if not values or not all(math.isfinite(value) for value in values):
        message = "expected nonempty finite toy values"
        raise ValueError(message)
    return values


def mean(values: tuple[float, ...]) -> float:
    """Compute the arithmetic mean with accurate summation."""
    checked = finite_values(values)
    return math.fsum(checked) / len(checked)


def linear_quantile(values: tuple[float, ...], q: float) -> float:
    """Interpolate sorted neighbors at h=(n-1)q, including endpoints."""
    ordered = sorted(finite_values(values))
    if not math.isfinite(q) or not 0.0 <= q <= 1.0:
        message = "quantile probability must be finite and in [0, 1]"
        raise ValueError(message)
    position = (len(ordered) - 1) * q
    left = math.floor(position)
    right = math.ceil(position)
    fraction = position - left
    return ordered[left] + fraction * (ordered[right] - ordered[left])


def sample_variance(values: tuple[float, ...]) -> float:
    """Use Bessel's n-1 denominator, not population variance's n."""
    center = mean(values)
    if len(values) <= 1:
        message = "sample variance requires at least two values"
        raise ValueError(message)
    return math.fsum((value - center) ** 2 for value in values) / (len(values) - 1)


def slope(seconds: tuple[float, ...], values: tuple[float, ...]) -> float:
    """Fit centered least squares in value units per elapsed second."""
    time_center = mean(seconds)
    value_center = mean(values)
    if len(seconds) != len(values):
        message = "slope requires equal-length times and values"
        raise ValueError(message)
    denominator = math.fsum((second - time_center) ** 2 for second in seconds)
    if denominator == 0.0:
        message = "slope requires distinct times"
        raise ValueError(message)
    numerator = math.fsum(
        (second - time_center) * (value - value_center)
        for second, value in zip(seconds, values, strict=True)
    )
    return numerator / denominator


def resample_means(
    values: tuple[float, ...], seed: int, count: int
) -> tuple[float, ...]:
    """Draw n values with replacement per replicate using educational RNG."""
    if count > MAX_RESAMPLES or len(values) > MAX_COHORT_VALUES:
        message = "resampling budget requires at most 2000 draws and 64 cohort values"
        raise ValueError(message)
    checked = finite_values(values)
    if count < 1 or seed < 0:
        message = "resampling requires positive count and nonnegative seed"
        raise ValueError(message)
    generator = random.Random(seed)  # noqa: S311 - educational, not cryptographic.
    return tuple(
        mean(tuple(generator.choice(checked) for _ in checked)) for _ in range(count)
    )


def orient(values: tuple[float, ...], *, lower_is_worse: bool) -> tuple[float, ...]:
    """Make larger oriented values worse for either metric direction."""
    checked = finite_values(values)
    return tuple(-value if lower_is_worse else value for value in checked)


def summary_labels(
    values: tuple[float, ...], seconds: tuple[float, ...]
) -> tuple[str, ...]:
    """Format the fixed lesson-07 arithmetic receipt, preserving its units."""
    return (
        f"mean={mean(values):.2f}",
        *(
            f"p{int(q * 100)}={linear_quantile(values, q):.2f}"
            for q in (0.5, 0.9, 0.95, 0.99)
        ),
        f"min={min(values):.2f}",
        f"max={max(values):.2f}",
        f"std_sample={math.sqrt(sample_variance(values)):.5f}",
        f"first={values[0]:.2f}",
        f"last={values[-1]:.2f}",
        f"delta={values[-1] - values[0]:.2f}",
        f"slope_per_second={slope(seconds, values):.5f}",
    )
