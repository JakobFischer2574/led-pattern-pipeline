from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from led_eval.utils.path_utils import ensure_dir


FRAME_COLUMNS = [
    "video_id", "method", "frame_index", "timestamp_ms",
    "led_1", "led_2", "led_3", "led_4", "led_5",
    "conf_1", "conf_2", "conf_3", "conf_4", "conf_5",
    "processing_time_ms", "locator_status",
]

VIDEO_COLUMNS = [
    "video_id",
    "file_name",
    "environment",
    "method",
    "lighting",
    "camera_position",
    "distance_cm",
    "scenario",
    "source_file",

    "true_error_code",
    "predicted_error_code",
    "correct",

    "best_match_score",
    "second_best_match_score",
    "match_margin",
    "true_error_code_score",

    "mean_latency_ms",
    "p95_latency_ms",
    "median_latency_ms",
    "total_runtime_s",
    "mean_cpu_percent",
    "median_cpu_percent",
    "peak_cpu_percent",
    "mean_ram_mb",
    "median_ram_mb",
    "peak_ram_mb",
    "ram_increase_mb",
    "processed_frame_count",
    "runtime_per_processed_frame_ms",

]


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: str | Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(target, index=False)


def snapshot_configs(config_paths: list[str | Path], target_dir: str | Path) -> None:
    out = ensure_dir(target_dir)
    for cfg in config_paths:
        path = Path(cfg)
        if path.exists():
            shutil.copy2(path, out / path.name)
