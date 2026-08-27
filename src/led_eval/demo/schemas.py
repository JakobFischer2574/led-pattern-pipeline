from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Method = Literal["classic", "yolo", "both"]


class AnalysisRequest(BaseModel):
    method: Method = "classic"
    source: Literal["camera", "video"] = "camera"
    camera_index: int = Field(default=0, ge=0, le=32)
    video_path: str | None = None
    duration_seconds: float = Field(default=3.0, ge=0.5, le=30.0)
    analysis_fps: float = Field(default=6.0, ge=0.2, le=30.0)
    width: int = Field(default=1280, ge=160, le=3840)
    height: int = Field(default=720, ge=120, le=2160)


class FrameResult(BaseModel):
    index: int
    timestamp_ms: float
    led_state: list[int]
    confidences: list[float]
    mean_confidence: float
    processing_time_ms: float
    locator_status: str
    locator_confidence: float
    image_url: str
    detection_view_url: str


class MethodResult(BaseModel):
    method: Literal["classic", "yolo"]
    frames: list[FrameResult]
    temporal_pattern: dict[str, str]
    predicted_error_code: str | None
    error_description: str | None
    match_score: float
    second_best_score: float
    match_margin: float
    mean_detector_latency_ms: float


class AnalysisStatus(BaseModel):
    id: str
    status: Literal["queued", "running", "complete", "failed"]
    stage: str
    progress: float
    message: str = ""
    methods: list[MethodResult] = Field(default_factory=list)
    frames_captured: int = 0
    total_duration_seconds: float | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
