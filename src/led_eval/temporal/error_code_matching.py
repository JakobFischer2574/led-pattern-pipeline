from __future__ import annotations
import re
from typing import Any


def score_pattern(observed: dict[str, str], expected: dict[str, str]) -> float:
    keys = sorted(expected)
    if not keys:
        return 0.0
    matches = sum(1 for key in keys if observed.get(key, "unknown") == expected.get(key))
    return matches / len(keys)


def match_error_code(
    observed_pattern: dict[str, str],
    error_codes: dict[str, Any],
    min_match_score: float = 0.0,
) -> tuple[str, float]:
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

    best_score = max(best_score, 0.0)

    if best_score < min_match_score:
        return "unknown", best_score

    return best_code, best_score

def calculate_match_score(observed_pattern: dict[str, str], expected_pattern: dict[str, str]) -> float:
    compared = 0
    matches = 0

    for led_name, expected_state in expected_pattern.items():
        observed_state = observed_pattern.get(led_name)

        if observed_state is None:
            continue

        compared += 1

        if observed_state == expected_state:
            matches += 1

    return matches / compared if compared > 0 else 0.0


def _error_code_number(error_code: str) -> int:
    match = re.search(r"(\d+)$", error_code)
    return int(match.group(1)) if match else 999999


def match_error_code_with_scores(
    observed_pattern: dict[str, str],
    error_codes: dict[str, Any],
    true_error_code: str | None = None,
) -> tuple[str, float, float, float, float | None]:
    scores: list[tuple[str, float]] = []

    for error_code, config in error_codes.items():
        expected_pattern = config.get("expected_pattern", {})
        score = calculate_match_score(observed_pattern, expected_pattern)
        scores.append((error_code, score))

    if not scores:
        return "unknown", 0.0, 0.0, 0.0, None

    # Erst nach Score absteigend, dann bei Gleichstand nach Fehlercode-Nummer aufsteigend.
    scores.sort(key=lambda item: (-item[1], _error_code_number(item[0])))

    best_code, best_score = scores[0]
    second_best_score = scores[1][1] if len(scores) > 1 else 0.0
    match_margin = best_score - second_best_score

    true_error_code_score = None
    if true_error_code is not None:
        for error_code, score in scores:
            if error_code == true_error_code:
                true_error_code_score = score
                break

    return best_code, best_score, second_best_score, match_margin, true_error_code_score