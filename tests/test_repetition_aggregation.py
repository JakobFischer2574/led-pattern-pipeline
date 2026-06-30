from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from led_eval.utils.cli_args import positive_int
from led_eval.evaluation.aggregation import aggregate_repetitions, deterministic_mode
from led_eval.evaluation.result_writer import write_csv


def _write_repetition(root: Path, idx: int, predicted: str, correct: bool, latency: float, led1: int) -> Path:
    rep = root / "repetitions" / f"run_{idx:03d}"
    write_csv(rep / "video_results.csv", [{
        "video_id": "v1", "file_name": "video.mp4", "environment": "lab", "method": "classic",
        "lighting": "", "camera_position": "", "distance_cm": "", "scenario": "", "source_file": "",
        "true_error_code": "E1", "predicted_error_code": predicted, "correct": correct,
        "best_match_score": 0.5 + idx, "second_best_match_score": 0.1, "match_margin": 0.4,
        "true_error_code_score": 0.5, "mean_latency_ms": latency, "p95_latency_ms": latency + 1,
        "median_latency_ms": latency, "total_runtime_s": idx, "mean_cpu_percent": idx,
        "median_cpu_percent": idx, "peak_cpu_percent": idx, "mean_ram_mb": idx,
        "median_ram_mb": idx, "peak_ram_mb": idx, "ram_increase_mb": idx,
        "processed_frame_count": 10 + idx, "runtime_per_processed_frame_ms": latency,
    }])
    write_csv(rep / "frame_results" / "classic" / "video.csv", [{
        "video_id": "v1", "method": "classic", "frame_index": 0, "timestamp_ms": 0,
        "led_1": led1, "led_2": 0, "led_3": 0, "led_4": 0, "led_5": 0,
        "conf_1": 0.1 * idx, "conf_2": 0.2, "conf_3": 0.3, "conf_4": 0.4, "conf_5": 0.5,
        "processing_time_ms": latency, "locator_status": "ok" if idx != 2 else "miss",
    }])
    return rep


def test_positive_int_accepts_one_for_compatibility():
    assert positive_int("1") == 1


@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_positive_int_rejects_invalid_values(value: str):
    with pytest.raises(argparse_error()):
        positive_int(value)


def argparse_error():
    import argparse
    return argparse.ArgumentTypeError


def test_aggregate_repetitions_median_modes_and_outputs(tmp_path: Path):
    reps = [
        _write_repetition(tmp_path, 1, "E1", True, 10.0, 1),
        _write_repetition(tmp_path, 2, "E2", False, 30.0, 0),
        _write_repetition(tmp_path, 3, "E1", True, 20.0, 1),
    ]
    aggregate_repetitions(tmp_path, reps, ["configs/local.yaml"], {"sampled_fps": 1}, {"E1": {"expected_pattern": {"led_1": "on"}}})

    video = pd.read_csv(tmp_path / "video_results.csv")
    assert video.loc[0, "mean_latency_ms"] == 20.0
    assert video.loc[0, "predicted_error_code"] == "E1"
    assert bool(video.loc[0, "correct"])
    assert video.loc[0, "correct_repetitions"] == 2
    assert video.loc[0, "total_repetitions"] == 3
    assert video.loc[0, "correct_rate"] == pytest.approx(2 / 3)
    assert (tmp_path / "repetition_video_results.csv").exists()
    assert (tmp_path / "repetitions" / "run_001" / "video_results.csv").exists()
    assert (tmp_path / "frame_results" / "classic" / "v1.csv").exists()
    assert (tmp_path / "temporal_results" / "v1_classic.json").exists()
    meta = json.loads((tmp_path / "aggregate_metadata.json").read_text())
    assert meta["repetitions"] == 3


def test_deterministic_mode_tie_breaks_lexicographically():
    assert deterministic_mode(["E2", "E1"]) == "E1"
