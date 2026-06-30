from __future__ import annotations

import statistics


def mean_latency_ms(values: list[float]) -> float:
    return float(statistics.fmean(values)) if values else 0.0

def median_latency_ms(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * p
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return float(ordered[low] * (1 - weight) + ordered[high] * weight)


def p95_latency_ms(values: list[float]) -> float:
    return percentile(values, 0.95)
