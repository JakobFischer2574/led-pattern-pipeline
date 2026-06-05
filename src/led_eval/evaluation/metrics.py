from __future__ import annotations

from collections.abc import Iterable


def accuracy(correct_values: Iterable[bool]) -> float:
    values = list(correct_values)
    if not values:
        return 0.0
    return sum(1 for value in values if value) / len(values)
