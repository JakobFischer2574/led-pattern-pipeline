from __future__ import annotations

from collections import Counter


def rolling_majority(values: list[int], window: int = 5) -> list[int]:
    if window <= 1 or len(values) <= 1:
        return list(values)
    half = window // 2
    smoothed: list[int] = []
    for index in range(len(values)):
        start = max(0, index - half)
        end = min(len(values), index + half + 1)
        candidates = [v for v in values[start:end] if v in {0, 1}]
        if not candidates:
            smoothed.append(-1)
            continue
        smoothed.append(Counter(candidates).most_common(1)[0][0])
    return smoothed


def smooth_short_outliers(values: list[int], max_run_length: int = 1) -> list[int]:
    if len(values) < 3 or max_run_length < 1:
        return list(values)
    result = list(values)
    index = 1
    while index < len(result) - 1:
        run_start = index
        run_value = result[index]
        while index < len(result) - 1 and result[index] == run_value:
            index += 1
        run_end = index
        run_length = run_end - run_start
        left = result[run_start - 1]
        right = result[run_end] if run_end < len(result) else None
        if run_length <= max_run_length and left == right and run_value != left:
            for pos in range(run_start, run_end):
                result[pos] = left
    return result


def smooth_led_sequence(values: list[int], window: int = 5, max_outlier_run: int = 1) -> list[int]:
    return smooth_short_outliers(rolling_majority(values, window=window), max_run_length=max_outlier_run)
