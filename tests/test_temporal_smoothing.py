from led_eval.temporal.smoothing import rolling_majority, smooth_short_outliers


def test_rolling_majority_smooths_single_spike() -> None:
    assert rolling_majority([1, 1, 0, 1, 1], window=3) == [1, 1, 1, 1, 1]


def test_smooth_short_outliers_replaces_short_run() -> None:
    assert smooth_short_outliers([0, 0, 1, 0, 0], max_run_length=1) == [0, 0, 0, 0, 0]
