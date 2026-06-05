from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from led_eval.data.ground_truth_loader import load_ground_truth, validate_ground_truth


def validate_inputs(config: dict[str, Any]) -> dict[str, Any]:
    data_cfg = config.get("data", {})
    gt_path = Path(str(data_cfg.get("ground_truth_csv", "data/raw/ground_truth_example.csv")))
    video_dir = Path(str(data_cfg.get("video_dir", "data/raw/videos")))

    gt_validation = validate_ground_truth(gt_path)
    report: dict[str, Any] = {
        "ground_truth": asdict(gt_validation),
        "video_dir": str(video_dir),
        "missing_videos": [],
        "existing_videos": [],
        "ok": gt_validation.ok,
    }

    if not gt_validation.ok:
        return report

    df = load_ground_truth(gt_path)
    for file_name in df["file_name"].astype(str):
        path = video_dir / file_name
        key = "existing_videos" if path.exists() else "missing_videos"
        report[key].append(str(path))

    report["ok"] = gt_validation.ok and not report["missing_videos"]
    return report
