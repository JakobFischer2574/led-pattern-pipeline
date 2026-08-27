from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np

from led_eval.demo.camera import CameraUnavailableError, CapturedFrame, open_camera
from led_eval.demo.service import DemoAnalysisService
from led_eval.detectors.base_detector import BaseDetector, DetectionResult


class StubDetector(BaseDetector):
    def __init__(self) -> None:
        self.calls = 0

    def detect(self, frame: np.ndarray) -> DetectionResult:
        self.calls += 1
        state = [1, 1, 1, 0, 0]
        return DetectionResult(state, [.9] * 5, 4.2, debug_info={"metrics": []})


def test_service_invokes_classic_detector_and_matches_error_code() -> None:
    detector = StubDetector()
    service = DemoAnalysisService(Path(__file__).parents[1], detector_factory=lambda method: detector)
    frames = [CapturedFrame(np.zeros((60, 100, 3), dtype=np.uint8), index * 200) for index in range(6)]

    status = service.analyze_frames(frames, method="classic", fps=5)

    assert status["status"] == "complete"
    assert detector.calls == 6
    assert status["methods"][0]["predicted_error_code"] == "fehlercode_01"
    assert status["methods"][0]["temporal_pattern"]["led_1"] == "on"
    assert status["methods"][0]["frames"][0]["processing_time_ms"] == 4.2


def test_yolo_unavailable_is_explicit() -> None:
    service = DemoAnalysisService(Path(__file__).parents[1])
    with patch("importlib.util.find_spec", return_value=None):
        available, reason = service.yolo_availability()
    assert available is False
    assert reason


def test_invalid_camera_is_reported_without_hardware() -> None:
    capture = type("ClosedCapture", (), {"isOpened": lambda self: False, "release": lambda self: None})()
    with patch("led_eval.demo.camera.cv2.VideoCapture", return_value=capture):
        try:
            open_camera(31)
        except CameraUnavailableError as exc:
            assert "31" in str(exc)
        else:
            raise AssertionError("A closed camera must be rejected")
