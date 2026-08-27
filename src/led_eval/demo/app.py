from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from led_eval.demo.camera import CameraUnavailableError, mjpeg_stream, probe_camera
from led_eval.demo.schemas import AnalysisRequest, AnalysisStatus
from led_eval.demo.service import DemoAnalysisService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
ROOT = Path(__file__).resolve().parents[3]
service = DemoAnalysisService(ROOT)


def create_app(analysis_service: DemoAnalysisService | None = None) -> FastAPI:
    active_service = analysis_service or service
    app = FastAPI(title="LED Pattern Recognition – Live Analysis", version="1.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/health")
    def health() -> dict:
        available, reason = active_service.yolo_availability()
        return {"status": "ok", "yolo_available": available, "yolo_reason": reason}

    @app.get("/api/cameras")
    def cameras(max_index: int = Query(default=3, ge=0, le=10)) -> dict:
        found = [{"index": index, "name": f"Camera {index}"} for index in range(max_index + 1) if probe_camera(index)]
        return {"cameras": found}

    @app.get("/api/config")
    def config() -> dict:
        yolo, reason = active_service.yolo_availability()
        return {"defaults": {"camera_index": 0, "duration_seconds": 3.0, "analysis_fps": 6.0, "width": 1280, "height": 720}, "methods": ["classic", "yolo", "both"], "yolo_available": yolo, "yolo_reason": reason, "temporal": active_service.temporal_config}

    @app.get("/api/camera/{index}/preview")
    def preview(index: int) -> StreamingResponse:
        try:
            stream = mjpeg_stream(index)
            return StreamingResponse(stream, media_type="multipart/x-mixed-replace; boundary=frame")
        except CameraUnavailableError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/analysis", status_code=202)
    def start_analysis(request: AnalysisRequest) -> dict:
        available, reason = active_service.yolo_availability()
        if request.method in {"yolo", "both"} and not available:
            raise HTTPException(status_code=409, detail=f"YOLO unavailable: {reason}")
        return {"id": active_service.submit(request)}

    @app.post("/api/videos", status_code=201)
    async def upload_video(request: Request) -> dict:
        """Store a browser-selected fallback video without multipart dependencies."""
        filename = Path(request.headers.get("x-filename", "fallback-video.mp4")).name
        suffix = Path(filename).suffix.lower()
        if suffix not in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
            raise HTTPException(status_code=400, detail="Unsupported video file extension")
        content = await request.body()
        if not content or len(content) > 500 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Video must be between 1 byte and 500 MB")
        upload_dir = ROOT / "outputs" / "demo_uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        destination = upload_dir / f"{Path(filename).stem}-{len(content)}{suffix}"
        destination.write_bytes(content)
        return {"path": str(destination)}

    @app.get("/api/analysis/{job_id}", response_model=AnalysisStatus)
    def analysis_status(job_id: str) -> dict:
        status = active_service.status(job_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return status

    frontend = ROOT / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()
