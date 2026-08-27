from __future__ import annotations

import base64
import copy
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from led_eval.demo.camera import CapturedFrame, capture_camera_frames, capture_video_frames
from led_eval.demo.schemas import AnalysisRequest
from led_eval.detectors.base_detector import BaseDetector, DetectionResult
from led_eval.detectors.classic_cv_detector import ClassicCVDetector
from led_eval.detectors.yolo_detector import YOLODetector
from led_eval.temporal.blink_detection import classify_video_pattern
from led_eval.temporal.error_code_matching import match_error_code_with_scores
from led_eval.temporal.smoothing import smooth_led_sequence
from led_eval.utils.config_loader import load_yaml_config

LOGGER = logging.getLogger(__name__)


def _data_url(frame: np.ndarray) -> str:
    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
    return "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii") if ok else ""


def annotate_detection(frame: np.ndarray, result: DetectionResult, method: str) -> np.ndarray:
    """Render only metadata emitted by the real detector; no detection is repeated here."""
    canvas = frame.copy()
    if method == "classic":
        for metric in result.debug_info.get("metrics", []):
            x, y, w, h = (int(metric[k]) for k in ("x", "y", "width", "height"))
            state = int(metric.get("state", -1))
            color = (70, 210, 100) if state == 1 else ((100, 110, 125) if state == 0 else (30, 150, 240))
            cv2.rectangle(canvas, (x, y), (x + w, y + h), color, 3)
            cv2.putText(canvas, f"{metric.get('led_id')} {'ON' if state == 1 else 'OFF' if state == 0 else '?'}", (x, max(24, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, .58, color, 2, cv2.LINE_AA)
    else:
        for detection in result.debug_info.get("detections", []):
            x1, y1, x2, y2 = (int(float(detection[k])) for k in ("x1", "y1", "x2", "y2"))
            color = (70, 210, 100) if detection.get("class_name") == "led_on" else (100, 150, 240)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 3)
            label = f"{detection.get('class_name', '?')} {float(detection.get('confidence', 0)):.0%}"
            cv2.putText(canvas, label, (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, .58, color, 2, cv2.LINE_AA)
    cv2.putText(canvas, f"{method.upper()} | locator: {result.locator_status}", (20, 34), cv2.FONT_HERSHEY_SIMPLEX, .75, (245, 245, 245), 2, cv2.LINE_AA)
    return canvas


class DemoAnalysisService:
    STAGES = ["capturing", "extracting_frames", "detecting_leds", "temporal_analysis", "matching_error_code", "result"]

    def __init__(self, root: Path | None = None, detector_factory: Callable[[str], BaseDetector] | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[3]
        self.temporal_config = load_yaml_config(self.root / "configs/temporal_config.yaml")
        self.error_codes = load_yaml_config(self.root / "configs/error_codes.yaml")
        self.detector_factory = detector_factory or self._build_detector
        self.jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _build_detector(self, method: str) -> BaseDetector:
        if method == "classic":
            config = load_yaml_config(self.root / "configs/classic_cv_config.yaml")
            layout = load_yaml_config(self.root / "configs/led_layout.yaml").get("leds")
            if not isinstance(layout, dict):
                raise ValueError("LED layout is invalid.")
            return ClassicCVDetector(config, layout)
        if method == "yolo":
            return YOLODetector(load_yaml_config(self.root / "configs/yolo_config.yaml"))
        raise ValueError(f"Unknown method: {method}")

    def yolo_availability(self) -> tuple[bool, str | None]:
        try:
            config = load_yaml_config(self.root / "configs/yolo_config.yaml")
            path = Path(str(config.get("model_path", ""))).expanduser()
            if not path.is_absolute():
                path = self.root / path
            if not path.is_file():
                return False, f"Model not found: {path}"
            import importlib.util
            if importlib.util.find_spec("ultralytics") is None:
                return False, "ultralytics is not installed"
            return True, None
        except Exception as exc:
            return False, str(exc)

    def submit(self, request: AnalysisRequest) -> str:
        job_id = uuid.uuid4().hex
        self.jobs[job_id] = {"id": job_id, "status": "queued", "stage": "capturing", "progress": 0.0, "message": "Queued", "methods": [], "frames_captured": 0, "total_duration_seconds": None, "warnings": [], "error": None}
        threading.Thread(target=self._run_job, args=(job_id, request), daemon=True).start()
        return job_id

    def status(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self.jobs.get(job_id)
            return copy.deepcopy(value) if value else None

    def _update(self, job_id: str, **values: Any) -> None:
        with self._lock:
            self.jobs[job_id].update(values)

    def _run_job(self, job_id: str, request: AnalysisRequest) -> None:
        started = time.perf_counter()
        try:
            self._update(job_id, status="running", stage="capturing", progress=0.04, message="Capturing a single shared sequence")
            if request.source == "camera":
                frames = capture_camera_frames(request.camera_index, request.duration_seconds, request.analysis_fps, request.width, request.height)
            else:
                if not request.video_path:
                    raise ValueError("A video path is required for video mode.")
                frames = capture_video_frames(request.video_path, request.duration_seconds, request.analysis_fps)
            self._update(job_id, stage="extracting_frames", progress=.20, message=f"Selected {len(frames)} frames", frames_captured=len(frames))
            methods = ["classic", "yolo"] if request.method == "both" else [request.method]
            method_results = []
            for method_index, method in enumerate(methods):
                detector = self.detector_factory(method)
                results = []
                sequences = [[] for _ in range(5)]
                for index, captured in enumerate(frames):
                    detection = detector.detect(captured.image)
                    for led_index in range(5):
                        sequences[led_index].append(int(detection.led_state[led_index]) if led_index < len(detection.led_state) else -1)
                    confidence = [float(v) for v in detection.confidences]
                    known_confidence = [value for state, value in zip(detection.led_state, confidence) if state in {0, 1}]
                    results.append({"index": index + 1, "timestamp_ms": round(captured.timestamp_ms, 1), "led_state": [int(v) for v in detection.led_state], "confidences": confidence, "mean_confidence": sum(known_confidence) / len(known_confidence) if known_confidence else 0.0, "processing_time_ms": float(detection.processing_time_ms), "locator_status": detection.locator_status, "locator_confidence": float(detection.locator_confidence), "image_url": _data_url(captured.image), "detection_view_url": _data_url(annotate_detection(captured.image, detection, method))})
                    fraction = (method_index + (index + 1) / len(frames)) / len(methods)
                    self._update(job_id, stage="detecting_leds", progress=.22 + .55 * fraction, message=f"{method.title()}: frame {index + 1} of {len(frames)}")
                self._update(job_id, stage="temporal_analysis", progress=.80 + .05 * (method_index + 1) / len(methods), message="Smoothing detections and classifying temporal states")
                smoothed = [smooth_led_sequence(sequence, int(self.temporal_config.get("rolling_majority_window", 5)), int(self.temporal_config.get("max_short_outlier_run", 1))) for sequence in sequences]
                pattern = classify_video_pattern(smoothed, fps=request.analysis_fps)
                self._update(job_id, stage="matching_error_code", progress=.89 + .05 * (method_index + 1) / len(methods), message="Matching configured error-code patterns")
                predicted, score, second, margin, _ = match_error_code_with_scores(pattern, self.error_codes)
                threshold = float(self.temporal_config.get("min_match_score", 0.0))
                # A zero-score tie (for example five unknown LEDs) must never be
                # presented as a real error code, even when evaluation config
                # intentionally uses a permissive zero threshold.
                matched = predicted if score > max(0.0, threshold) and predicted != "unknown" else None
                description = self.error_codes.get(matched, {}).get("description") if matched else None
                latencies = [frame["processing_time_ms"] for frame in results]
                method_results.append({"method": method, "frames": results, "temporal_pattern": pattern, "predicted_error_code": matched, "error_description": description, "match_score": score, "second_best_score": second, "match_margin": margin, "mean_detector_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0})
            self._update(job_id, status="complete", stage="result", progress=1.0, message="Analysis complete", methods=method_results, total_duration_seconds=time.perf_counter() - started)
        except Exception as exc:
            LOGGER.exception("Demo analysis %s failed", job_id)
            self._update(job_id, status="failed", message="Analysis could not be completed", error=str(exc), total_duration_seconds=time.perf_counter() - started)

    def analyze_frames(self, frames: list[CapturedFrame], method: str = "classic", fps: float = 6.0) -> dict[str, Any]:
        """Synchronous test/integration entry point using the same job implementation."""
        original = globals()["capture_video_frames"]
        try:
            globals()["capture_video_frames"] = lambda *_args, **_kwargs: frames
            request = AnalysisRequest(method=method, source="video", video_path="mock", analysis_fps=fps)
            job_id = uuid.uuid4().hex
            self.jobs[job_id] = {"id": job_id, "status": "queued", "stage": "capturing", "progress": 0.0, "message": "", "methods": [], "frames_captured": 0, "total_duration_seconds": None, "warnings": [], "error": None}
            self._run_job(job_id, request)
            return self.status(job_id) or {}
        finally:
            globals()["capture_video_frames"] = original
