from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from led_eval.demo.app import create_app
from led_eval.demo.service import DemoAnalysisService


def test_health_endpoint_reports_backend_and_yolo_state() -> None:
    service = DemoAnalysisService(Path(__file__).parents[1])
    service.yolo_availability = lambda: (False, "test model missing")  # type: ignore[method-assign]
    client = TestClient(create_app(service))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "yolo_available": False, "yolo_reason": "test model missing"}


def test_api_rejects_unavailable_yolo_before_starting_job() -> None:
    service = DemoAnalysisService(Path(__file__).parents[1])
    service.yolo_availability = lambda: (False, "model missing")  # type: ignore[method-assign]
    client = TestClient(create_app(service))

    response = client.post("/api/analysis", json={"method": "yolo", "source": "camera"})

    assert response.status_code == 409
    assert "model missing" in response.json()["detail"]
