from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from led_eval.evaluation.result_writer import FRAME_COLUMNS, VIDEO_COLUMNS, write_csv, write_json
from led_eval.temporal.blink_detection import classify_video_pattern
from led_eval.temporal.error_code_matching import match_error_code_with_scores
from led_eval.temporal.smoothing import smooth_led_sequence

VIDEO_GROUP_COLUMNS = ["video_id", "file_name", "environment", "method", "true_error_code"]
FRAME_GROUP_COLUMNS = ["video_id", "method", "frame_index"]
CATEGORICAL_FRAME_COLUMNS = ["locator_status", "led_1", "led_2", "led_3", "led_4", "led_5"]
IDENTITY_VIDEO_COLUMNS = {"video_id", "file_name", "environment", "method", "true_error_code"}
NON_METRIC_VIDEO_COLUMNS = IDENTITY_VIDEO_COLUMNS | {"predicted_error_code", "correct"}


def deterministic_mode(values: list[Any]) -> Any:
    clean = [v for v in values if pd.notna(v)]
    if not clean:
        return None
    counts = Counter(str(v) for v in clean)
    # Tie-break: lexical order of the string representation for deterministic output.
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _coerce_mode_value(value: Any) -> Any:
    if value is None:
        return value
    text = str(value)
    try:
        as_float = float(text)
    except ValueError:
        return value
    if as_float.is_integer():
        return int(as_float)
    return as_float


def numeric_metric_columns(df: pd.DataFrame, exclude: set[str]) -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        if col in exclude or col == "repetition_index":
            continue
        if pd.api.types.is_bool_dtype(df[col]):
            continue
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.notna().any():
            cols.append(col)
    return cols


def aggregate_video_results(repetition_frames: list[tuple[int, Path]], run_dir: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for idx, path in repetition_frames:
        df = pd.read_csv(path)
        df.insert(0, "repetition_index", idx)
        frames.append(df)
    all_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    all_df.to_csv(run_dir / "repetition_video_results.csv", index=False)
    if all_df.empty:
        write_csv(run_dir / "video_results.csv", [], VIDEO_COLUMNS)
        return all_df

    metric_cols = numeric_metric_columns(all_df, NON_METRIC_VIDEO_COLUMNS)
    rows: list[dict[str, Any]] = []
    for keys, group in all_df.groupby(VIDEO_GROUP_COLUMNS, dropna=False, sort=False):
        row = dict(zip(VIDEO_GROUP_COLUMNS, keys))
        first = group.iloc[0].to_dict()
        for col in [c for c in VIDEO_COLUMNS if c not in row and c not in {"predicted_error_code", "correct"}]:
            if col not in metric_cols and col in group.columns:
                row[col] = first.get(col)
        for col in metric_cols:
            row[col] = round(float(pd.to_numeric(group[col], errors="coerce").median()), 3)
        predicted = deterministic_mode(group.get("predicted_error_code", pd.Series(dtype=object)).tolist())
        row["predicted_error_code"] = predicted
        row["correct"] = str(predicted) == str(row.get("true_error_code"))
        correct_series = group.get("correct", pd.Series(dtype=object)).map(lambda v: str(v).lower() == "true")
        row["correct_repetitions"] = int(correct_series.sum())
        row["total_repetitions"] = int(len(group))
        row["correct_rate"] = round(row["correct_repetitions"] / row["total_repetitions"], 6) if row["total_repetitions"] else 0.0
        counts = Counter(str(v) for v in group.get("predicted_error_code", pd.Series(dtype=object)).dropna().tolist())
        row["prediction_consistency"] = round(max(counts.values()) / len(group), 6) if counts else 0.0
        rows.append(row)
    columns = VIDEO_COLUMNS + ["correct_rate", "correct_repetitions", "total_repetitions", "prediction_consistency"]
    write_csv(run_dir / "video_results.csv", rows, columns)
    return all_df


def aggregate_frame_results(repetition_dirs: list[Path], run_dir: Path) -> pd.DataFrame:
    frames = []
    for idx, rep_dir in enumerate(repetition_dirs, start=1):
        for path in sorted((rep_dir / "frame_results").glob("*/*.csv")):
            df = pd.read_csv(path)
            df.insert(0, "repetition_index", idx)
            frames.append(df)
    all_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=FRAME_COLUMNS)
    if all_df.empty:
        return all_df
    numeric_cols = numeric_metric_columns(all_df, set(FRAME_GROUP_COLUMNS + CATEGORICAL_FRAME_COLUMNS))
    rows: list[dict[str, Any]] = []
    for keys, group in all_df.groupby(FRAME_GROUP_COLUMNS, dropna=False, sort=False):
        row = dict(zip(FRAME_GROUP_COLUMNS, keys))
        for col in numeric_cols:
            row[col] = round(float(pd.to_numeric(group[col], errors="coerce").median()), 4)
        for col in CATEGORICAL_FRAME_COLUMNS:
            if col in group.columns:
                row[col] = _coerce_mode_value(deterministic_mode(group[col].tolist()))
        rows.append(row)
    out = pd.DataFrame(rows)
    for (video_id, method), group in out.groupby(["video_id", "method"], sort=False):
        target = run_dir / "frame_results" / str(method) / f"{video_id}.csv"
        write_csv(target, group.to_dict("records"), FRAME_COLUMNS)
    return out


def write_aggregate_temporal(frame_df: pd.DataFrame, video_df: pd.DataFrame, run_dir: Path, temporal_cfg: dict[str, Any], error_codes: dict[str, Any]) -> None:
    if frame_df.empty:
        return
    smooth_window = int(temporal_cfg.get("rolling_majority_window", 5))
    max_outlier = int(temporal_cfg.get("max_short_outlier_run", 1))
    fps = float(temporal_cfg.get("sampled_fps", 1.0))
    for (video_id, method), group in frame_df.groupby(["video_id", "method"], sort=False):
        group = group.sort_values("frame_index")
        sequences = [[int(v) for v in group[f"led_{i}"].tolist() if pd.notna(v)] for i in range(1, 6)]
        smoothed = [smooth_led_sequence(seq, smooth_window, max_outlier) for seq in sequences]
        observed = classify_video_pattern(smoothed, fps=fps)
        matches = video_df[(video_df["video_id"].astype(str) == str(video_id)) & (video_df["method"].astype(str) == str(method))]
        true_code = str(matches.iloc[0]["true_error_code"]) if not matches.empty else None
        predicted, best, second, margin, true_score = match_error_code_with_scores(observed, error_codes, true_code)
        write_json(run_dir / "temporal_results" / f"{video_id}_{method}.json", {
            "observed_pattern": observed,
            "predicted_error_code": predicted,
            "best_match_score": round(best, 3),
            "second_best_match_score": round(second, 3),
            "match_margin": round(margin, 3),
            "true_error_code_score": round(true_score, 3) if true_score is not None else None,
            "source": "aggregated_frame_results",
        })


def aggregate_repetitions(run_dir: Path, repetition_dirs: list[Path], config_paths: list[str | Path], temporal_cfg: dict[str, Any], error_codes: dict[str, Any]) -> dict[str, Any]:
    video_inputs = [(idx, rep / "video_results.csv") for idx, rep in enumerate(repetition_dirs, start=1)]
    video_df = aggregate_video_results(video_inputs, run_dir)
    frame_df = aggregate_frame_results(repetition_dirs, run_dir)
    if not frame_df.empty and not video_df.empty:
        write_aggregate_temporal(frame_df, video_df, run_dir, temporal_cfg, error_codes)
    latency_columns = [
        "video_id", "method", "mean_latency_ms", "p95_latency_ms", "processed_frame_count",
        "total_runtime_s", "runtime_per_processed_frame_ms",
    ]
    resource_columns = [
        "video_id", "method", "mean_cpu_percent", "median_cpu_percent", "peak_cpu_percent",
        "mean_ram_mb", "median_ram_mb", "peak_ram_mb", "ram_increase_mb",
    ]
    write_csv(run_dir / "latency_metrics.csv", video_df.to_dict("records"), [c for c in latency_columns if c in video_df.columns])
    write_csv(run_dir / "resource_metrics.csv", video_df.to_dict("records"), [c for c in resource_columns if c in video_df.columns])
    meta = {
        "repetitions": len(repetition_dirs),
        "aggregated_at": datetime.now(timezone.utc).isoformat(),
        "config_files": [str(p) for p in config_paths],
        "aggregation_rules": {
            "video_group_columns": VIDEO_GROUP_COLUMNS,
            "numeric_metrics": "median per completed repetition result",
            "predicted_error_code": "mode; ties broken lexicographically by string value",
            "correct": "recomputed from aggregated predicted_error_code and true_error_code",
            "frame_group_columns": FRAME_GROUP_COLUMNS,
            "frame_numeric_metrics": "median",
            "frame_categorical_values": "mode; ties broken lexicographically by string value",
            "temporal_results": "recomputed from aggregated frame LED sequences",
        },
        "repetition_dirs": [str(p) for p in repetition_dirs],
    }
    write_json(run_dir / "aggregate_metadata.json", meta)
    write_json(run_dir / "summary.json", {"repetitions": len(repetition_dirs), "completed_rows": int(len(video_df)), "correct": int(sum(video_df.get("correct", []))) if not video_df.empty else 0})
    return meta
