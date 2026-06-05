from __future__ import annotations

from pathlib import Path

import pandas as pd


def accuracy_by_method(video_results: pd.DataFrame) -> pd.DataFrame:
    return video_results.groupby("method", as_index=False)["correct"].mean()


def accuracy_by_environment(video_results: pd.DataFrame) -> pd.DataFrame:
    return video_results.groupby(["method", "environment"], as_index=False)["correct"].mean()


def latency_by_method(video_results: pd.DataFrame) -> pd.DataFrame:
    return video_results.groupby("method", as_index=False)[["mean_latency_ms", "p95_latency_ms"]].mean()


def resource_by_method(video_results: pd.DataFrame) -> pd.DataFrame:
    return video_results.groupby("method", as_index=False)[["mean_cpu_percent", "peak_ram_mb"]].mean()


def write_analysis_tables(video_results_csv: str | Path, output_dir: str | Path) -> None:
    df = pd.read_csv(video_results_csv)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    accuracy_by_method(df).to_csv(out / "accuracy_by_method.csv", index=False)
    accuracy_by_environment(df).to_csv(out / "accuracy_by_environment.csv", index=False)
    latency_by_method(df).to_csv(out / "latency_by_method.csv", index=False)
    resource_by_method(df).to_csv(out / "resource_by_method.csv", index=False)
