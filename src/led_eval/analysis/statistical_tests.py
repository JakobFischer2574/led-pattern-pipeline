from __future__ import annotations

from typing import Any

import pandas as pd


def wilcoxon_latency_placeholder(video_results: pd.DataFrame) -> dict[str, Any]:
    return {
        "test": "wilcoxon",
        "status": "placeholder",
        "note": "Implement after paired classic/yolo latency samples are finalized.",
        "rows": int(len(video_results)),
    }


def mcnemar_accuracy_placeholder(video_results: pd.DataFrame) -> dict[str, Any]:
    return {
        "test": "mcnemar",
        "status": "placeholder",
        "note": "Implement after paired per-video correctness table is finalized.",
        "rows": int(len(video_results)),
    }
