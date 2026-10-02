"""Exact scalar statistic calculations for validated per-run samples."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

import numpy as np

from perfcheck.model_types import Statistic

if TYPE_CHECKING:
    from perfcheck.collection_models import FloatSample

type QuantileStatistic = Literal[
    Statistic.P50, Statistic.P90, Statistic.P95, Statistic.P99
]
type OrderedStatistic = Literal[Statistic.FIRST, Statistic.LAST, Statistic.DELTA]


def calculate_statistic(
    statistic: Statistic, samples: tuple[FloatSample, ...]
) -> float:
    """Return the selected scalar statistic for eligible samples."""
    values = tuple(sample.value for sample in samples)
    match statistic:
        case Statistic.MEAN:
            value = math.fsum(values) / len(values)
        case Statistic.P50 | Statistic.P90 | Statistic.P95 | Statistic.P99:
            value = _quantile_value(statistic, values)
        case Statistic.MIN | Statistic.MAX:
            value = _extremum_value(statistic is Statistic.MIN, values)
        case Statistic.STD:
            value = _sample_standard_deviation(values)
        case Statistic.FIRST | Statistic.LAST | Statistic.DELTA:
            value = _ordered_value(statistic, values)
        case Statistic.SLOPE:
            value = _slope(samples)
    return value


def _quantile_value(statistic: QuantileStatistic, values: tuple[float, ...]) -> float:
    match statistic:
        case Statistic.P50:
            quantile = 0.5
        case Statistic.P90:
            quantile = 0.9
        case Statistic.P95:
            quantile = 0.95
        case Statistic.P99:
            quantile = 0.99
    return float(np.quantile(values, quantile, method="linear"))


def _extremum_value(minimum: bool, values: tuple[float, ...]) -> float:
    return float(np.min(values) if minimum else np.max(values))


def _ordered_value(statistic: OrderedStatistic, values: tuple[float, ...]) -> float:
    match statistic:
        case Statistic.FIRST:
            value = values[0]
        case Statistic.LAST:
            value = values[-1]
        case Statistic.DELTA:
            value = values[-1] - values[0]
    return value


def _sample_standard_deviation(values: tuple[float, ...]) -> float:
    mean = math.fsum(values) / len(values)
    squared_deviations = math.fsum((value - mean) ** 2 for value in values)
    return math.sqrt(squared_deviations / (len(values) - 1))


def _slope(samples: tuple[FloatSample, ...]) -> float:
    origin = samples[0].timestamp
    seconds = tuple((sample.timestamp - origin).total_seconds() for sample in samples)
    values = tuple(sample.value for sample in samples)
    mean_seconds = math.fsum(seconds) / len(seconds)
    mean_values = math.fsum(values) / len(values)
    numerator = math.fsum(
        (second - mean_seconds) * (value - mean_values)
        for second, value in zip(seconds, values, strict=True)
    )
    denominator = math.fsum((second - mean_seconds) ** 2 for second in seconds)
    return numerator / denominator
