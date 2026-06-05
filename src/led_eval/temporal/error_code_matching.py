from __future__ import annotations

from typing import Any


def score_pattern(observed: dict[str, str], expected: dict[str, str]) -> float:
    keys = sorted(expected)
    if not keys:
        return 0.0
    matches = sum(1 for key in keys if observed.get(key, "unknown") == expected.get(key))
    return matches / len(keys)


def match_error_code(observed_pattern: dict[str, str], error_codes: dict[str, Any]) -> tuple[str, float]:
    best_code = "unknown"
    best_score = -1.0
    for code, data in error_codes.items():
        expected = data.get("expected_pattern", {}) if isinstance(data, dict) else {}
        if not isinstance(expected, dict):
            continue
        score = score_pattern(observed_pattern, {str(k): str(v) for k, v in expected.items()})
        if score > best_score:
            best_code = str(code)
            best_score = score
    return best_code, max(best_score, 0.0)
