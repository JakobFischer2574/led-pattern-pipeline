from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np


class CameraUnavailableError(RuntimeError):
    pass


@dataclass
class CapturedFrame:
    image: np.ndarray
    timestamp_ms: float


def open_camera(index: int, width: int = 1280, height: int = 720) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(index)
    if not capture.isOpened():
        capture.release()
        raise CameraUnavailableError(f"Camera {index} is not available.")
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return capture


def probe_camera(index: int) -> bool:
    try:
        capture = open_camera(index, 320, 240)
        ok, _ = capture.read()
        capture.release()
        return bool(ok)
    except CameraUnavailableError:
        return False


def capture_camera_frames(index: int, duration: float, fps: float, width: int, height: int) -> list[CapturedFrame]:
    capture = open_camera(index, width, height)
    frames: list[CapturedFrame] = []
    interval = 1.0 / fps
    started = time.monotonic()
    next_sample = started
    try:
        while time.monotonic() - started < duration:
            ok, frame = capture.read()
            if not ok:
                raise CameraUnavailableError("Camera disconnected while capturing.")
            now = time.monotonic()
            if now >= next_sample:
                frames.append(CapturedFrame(frame, (now - started) * 1000.0))
                next_sample += interval
    finally:
        capture.release()
    if not frames:
        raise CameraUnavailableError("Camera returned no frames.")
    return frames


def capture_video_frames(path: str | Path, duration: float, fps: float) -> list[CapturedFrame]:
    video_path = Path(path).expanduser()
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Video cannot be opened: {video_path}")
    source_fps = float(capture.get(cv2.CAP_PROP_FPS)) or 30.0
    step = max(1, round(source_fps / fps))
    maximum = max(1, round(duration * fps))
    frames: list[CapturedFrame] = []
    index = 0
    try:
        while len(frames) < maximum:
            ok, frame = capture.read()
            if not ok:
                break
            if index % step == 0:
                frames.append(CapturedFrame(frame, index / source_fps * 1000.0))
            index += 1
    finally:
        capture.release()
    if not frames:
        raise ValueError("Video contains no readable frames.")
    return frames


def mjpeg_stream(index: int, width: int = 960, height: int = 540) -> Iterator[bytes]:
    capture = open_camera(index, width, height)
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            encoded, data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if encoded:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data.tobytes() + b"\r\n"
    finally:
        capture.release()
