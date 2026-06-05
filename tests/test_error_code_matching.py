from led_eval.temporal.error_code_matching import match_error_code


def test_match_error_code_returns_best_match() -> None:
    codes = {
        "a": {"expected_pattern": {"led_1": "on", "led_2": "off"}},
        "b": {"expected_pattern": {"led_1": "off", "led_2": "off"}},
    }

    code, score = match_error_code({"led_1": "on", "led_2": "off"}, codes)

    assert code == "a"
    assert score == 1.0
