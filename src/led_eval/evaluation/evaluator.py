from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2

from led_eval.data.frame_extractor import extract_every_nth_frame
from led_eval.data.ground_truth_loader import load_ground_truth
from led_eval.detectors.base_detector import BaseDetector
from led_eval.detectors.classic_cv_detector import ClassicCVDetector
from led_eval.detectors.yolo_detector import YOLODetector
from led_eval.evaluation.latency import mean_latency_ms, p95_latency_ms, median_latency_ms
from led_eval.evaluation.resource_monitor import ResourceMonitor, now_seconds
from led_eval.evaluation.result_writer import FRAME_COLUMNS, VIDEO_COLUMNS, snapshot_configs, write_csv, write_json
from led_eval.temporal.blink_detection import classify_video_pattern
from led_eval.temporal.error_code_matching import match_error_code_with_scores
from led_eval.temporal.smoothing import smooth_led_sequence
from led_eval.utils.config_loader import load_yaml_config
from led_eval.utils.path_utils import ensure_dir


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


class PipelineEvaluator:
    def __init__(self, config: dict[str, Any], run_dir: Path, config_path: Path) -> None:
        self.config = config
        self.run_dir = run_dir
        self.config_path = config_path
        self.data_cfg = config.get("data", {})
        self.pipeline_cfg = config.get("pipeline", {})
        self.paths_cfg = config.get("paths", {})
        self.temporal_cfg = load_yaml_config(config.get("temporal_config", "configs/temporal_config.yaml"))
        self.error_codes = load_yaml_config(config.get("error_codes_config", "configs/error_codes.yaml"))

    def run(self, method: str = "both") -> dict[str, Any]:
        methods = ["classic", "yolo"] if method == "both" else [method]
        gt = load_ground_truth(self.data_cfg.get("ground_truth_csv", "data/raw/ground_truth_example.csv"))
        video_rows: list[dict[str, Any]] = []

        snapshot_configs(
            [
                self.config_path,
                self.config.get("classic_cv_config", "configs/classic_cv_config.yaml"),
                self.config.get("yolo_config", "configs/yolo_config.yaml"),
                self.config.get("led_layout", "configs/led_layout.yaml"),
                self.config.get("temporal_config", "configs/temporal_config.yaml"),
                self.config.get("error_codes_config", "configs/error_codes.yaml"),
            ],
            self.run_dir / "run_config_snapshot",
        )

        for current_method in methods:
            for _, row in gt.iterrows():
                try:
                    video_rows.append(self._process_video(row.to_dict(), current_method))
                except (FileNotFoundError, ImportError, ValueError, RuntimeError) as exc:
                    video_rows.append(self._error_video_row(row.to_dict(), current_method, exc))

        write_csv(self.run_dir / "video_results.csv", video_rows, VIDEO_COLUMNS)
        write_csv(
            self.run_dir / "latency_metrics.csv",
            [
                {
                        "video_id": row["video_id"],
                        "method": row["method"],
                        "mean_latency_ms": row["mean_latency_ms"],
                        "p95_latency_ms": row["p95_latency_ms"],
                        "processed_frame_count": row["processed_frame_count"],
                        "total_runtime_s": row["total_runtime_s"],
                        "runtime_per_processed_frame_ms": row["runtime_per_processed_frame_ms"],
                }
                for row in video_rows
            ],
        )
        write_csv(
            self.run_dir / "resource_metrics.csv",
            [
                {
                    "video_id": row["video_id"],
                    "method": row["method"],
                    "mean_cpu_percent": row["mean_cpu_percent"],
                    "median_cpu_percent": row["median_cpu_percent"],
                    "peak_ram_mb": row["peak_ram_mb"],
                    "ram_increase_mb": row["ram_increase_mb"],
                }
                for row in video_rows
            ],
        )
        ensure_dir(self.run_dir / "plots")
        write_json(
            self.run_dir / "summary.json",
            {
                "videos": len(gt),
                "methods": methods,
                "completed_rows": len(video_rows),
                "correct": sum(1 for row in video_rows if row.get("correct") is True),
            },
        )
        return {"video_results": video_rows}

    def _build_detector(self, method: str) -> BaseDetector:
        if method == "classic":
            cfg = load_yaml_config(self.config.get("classic_cv_config", "configs/classic_cv_config.yaml"))
            layout = load_yaml_config(self.config.get("led_layout", "configs/led_layout.yaml")).get("leds")
            if not isinstance(layout, dict):
                raise ValueError("Ungueltiges LED-Layout: 'leds' fehlt oder ist kein dict")
            return ClassicCVDetector(cfg, layout)
        if method == "yolo":
            return YOLODetector(load_yaml_config(self.config.get("yolo_config", "configs/yolo_config.yaml")))
        raise ValueError(f"Unbekannte Methode: {method}")

    def _process_video(self, gt_row: dict[str, Any], method: str) -> dict[str, Any]:
        start_s = now_seconds()
        video_dir = Path(str(self.data_cfg.get("video_dir", "data/raw/videos")))
        sampled_root = Path(str(self.data_cfg.get("sampled_frames_dir", "data/sampled_frames")))
        frame_step = int(self.pipeline_cfg.get("frame_step", 30))
        video_path = video_dir / str(gt_row["file_name"])
        frame_dir = sampled_root / Path(str(gt_row["file_name"])).stem
        extract_every_nth_frame(video_path, frame_dir, step=frame_step)

        detector = self._build_detector(method)
        monitor = ResourceMonitor()
        monitor.start()
        frame_rows: list[dict[str, Any]] = []
        led_sequences = [[] for _ in range(5)]

        for frame_index, frame_path in enumerate(sorted(p for p in frame_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)):
            frame = cv2.imread(str(frame_path))
            if frame is None:
                continue
            result = detector.detect(frame)
            monitor.sample()
            timestamp_ms = frame_index * frame_step
            for led_idx, state in enumerate(result.led_state[:5]):
                led_sequences[led_idx].append(int(state))
            frame_rows.append(self._frame_row(gt_row, method, frame_index, timestamp_ms, result))

        # frame_output = self.run_dir / "frame_results" / method / f"{Path(str(gt_row['file_name'])).stem}.csv"
        # write_csv(frame_output, frame_rows, FRAME_COLUMNS)

        smooth_window = int(self.temporal_cfg.get("rolling_majority_window", 5))
        max_outlier = int(self.temporal_cfg.get("max_short_outlier_run", 1))
        fps = float(self.temporal_cfg.get("sampled_fps", 1.0))
        smoothed = [smooth_led_sequence(seq, smooth_window, max_outlier) for seq in led_sequences]
        observed = classify_video_pattern(smoothed, fps=fps)
        predicted, best_score, second_best_score, match_margin, true_error_code_score = match_error_code_with_scores(
            observed,
            self.error_codes,
            true_error_code=str(gt_row["error_code"]),
        )
        # write_json(
        #     self.run_dir / "temporal_results" / f"{Path(str(gt_row['file_name'])).stem}_{method}.json",
        #     {
        #         "observed_pattern": observed,
        #         "predicted_error_code": predicted,
        #         "best_match_score": best_score,
        #         "second_best_match_score": second_best_score,
        #         "match_margin": match_margin,
        #         "true_error_code_score": true_error_code_score,
        #     },
        # )

        monitor.sample()
        total_runtime_s = now_seconds() - start_s
        processed_frame_count = len(frame_rows)
        runtime_per_processed_frame_ms = (
            (total_runtime_s * 1000) / processed_frame_count
            if processed_frame_count > 0
            else 0.0
        )

        latencies = [float(row["processing_time_ms"]) for row in frame_rows]
        resource = monitor.summary()
        return {
            # Grundlegende Video- und Szeneninformationen
            "video_id": gt_row["video_id"],
            "file_name": gt_row["file_name"],
            "environment": gt_row["environment"],
            "method": method,
            "lighting": gt_row.get("lighting", ""),
            "camera_position": gt_row.get("camera_position", ""),
            "distance_cm": gt_row.get("distance_cm", ""),
            "scenario": gt_row.get("scenario", ""),
            "source_file": gt_row.get("source_file", ""),

            # Vorhersage
            "true_error_code": gt_row["error_code"],
            "predicted_error_code": predicted,
            "correct": predicted == gt_row["error_code"],

            # Scores
            "best_match_score": round(best_score, 3),
            "second_best_match_score": round(second_best_score, 3),
            "match_margin": round(match_margin, 3),
            "true_error_code_score": round(true_error_code_score, 3) if true_error_code_score is not None else None,

            # Latenz- und Ressourcenmetriken
            "mean_latency_ms": round(mean_latency_ms(latencies), 3),
            "p95_latency_ms": round(p95_latency_ms(latencies), 3),
            "median_latency_ms": round(median_latency_ms(latencies), 3),
            "total_runtime_s": round(total_runtime_s, 3),
            "mean_cpu_percent": round(resource["mean_cpu_percent"], 3),
            "median_cpu_percent": round(resource["median_cpu_percent"], 3),
            "peak_cpu_percent": round(resource["peak_cpu_percent"], 3),
            "mean_ram_mb": round(resource["mean_ram_mb"], 3),
            "median_ram_mb": round(resource["median_ram_mb"], 3),
            "peak_ram_mb": round(resource["peak_ram_mb"], 3),
            "ram_increase_mb": round(resource["ram_increase_mb"], 3),
            "processed_frame_count": processed_frame_count,
            "runtime_per_processed_frame_ms": round(runtime_per_processed_frame_ms, 3),
        }

    @staticmethod
    def _frame_row(gt_row: dict[str, Any], method: str, frame_index: int, timestamp_ms: int, result: Any) -> dict[str, Any]:
        row = {
            "video_id": gt_row["video_id"],
            "method": method,
            "frame_index": frame_index,
            "timestamp_ms": timestamp_ms,
            "processing_time_ms": round(float(result.processing_time_ms), 3),
            "locator_status": result.locator_status,
        }
        for index in range(5):
            row[f"led_{index + 1}"] = result.led_state[index] if index < len(result.led_state) else -1
            row[f"conf_{index + 1}"] = round(float(result.confidences[index]), 4) if index < len(result.confidences) else 0.0
        return row

    @staticmethod
    def _error_video_row(gt_row: dict[str, Any], method: str, exc: Exception) -> dict[str, Any]:
        return {
            "video_id": gt_row.get("video_id"),
            "file_name": gt_row.get("file_name"),
            "environment": gt_row.get("environment"),
            "method": method,
            "lighting": gt_row.get("lighting", ""),
            "camera_position": gt_row.get("camera_position", ""),
            "distance_cm": gt_row.get("distance_cm", ""),
            "scenario": gt_row.get("scenario", ""),
            "source_file": gt_row.get("source_file", ""),

            "true_error_code": gt_row.get("error_code"),
            "predicted_error_code": f"error: {exc}",
            "correct": False,

            "best_match_score": 0.0,
            "second_best_match_score": 0.0,
            "match_margin": 0.0,
            "true_error_code_score": 0.0,
            "mean_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "median_latency_ms": 0.0,
            "total_runtime_s": 0.0,
            "mean_cpu_percent": 0.0,
            "median_cpu_percent": 0.0,
            "peak_cpu_percent": 0.0,
            "mean_ram_mb": 0.0,
            "median_ram_mb": 0.0,
            "peak_ram_mb": 0.0,
            "ram_increase_mb": 0.0,
            "processed_frame_count": 0,
            "runtime_per_processed_frame_ms": 0.0,

        }