from __future__ import annotations

import time

from fastapi.testclient import TestClient

from sensor_monitor.app import create_app
from sensor_monitor.config import Settings
from sensor_monitor.sources import SimulatorSource

from .test_hub import CaptureSource


def test_rest_websocket_and_fault_control(tmp_path) -> None:
    settings = Settings(
        simulator_rate_hz=100,
        log_dir=tmp_path,
        stale_after_seconds=0.5,
        offline_after_seconds=1.0,
    )
    source = SimulatorSource(rate_hz=100, seed=1)
    with TestClient(create_app(settings, source)) as client:
        deadline = time.monotonic() + 2
        devices = []
        while time.monotonic() < deadline and not devices:
            devices = client.get("/api/v1/devices").json()
            time.sleep(0.01)
        assert devices[0]["device_id"] == "stm32-sensor-hub"
        assert client.get("/healthz").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/api/v1/snapshot").status_code == 200
        assert client.get("/api/v1/stats").json()["frames_accepted"] > 0
        assert client.get("/api/v1/alerts").status_code == 200
        assert client.get("/api/v1/devices/stm32-sensor-hub").status_code == 200
        assert client.get("/api/v1/devices/stm32-sensor-hub/readings").json()
        assert client.get("/api/v1/devices/missing").status_code == 404

        response = client.post(
            "/api/v1/simulator/fault", json={"mode": "over_temperature"}
        )
        assert response.json() == {"mode": "over_temperature"}

        with client.websocket_connect("/ws/telemetry") as socket:
            assert socket.receive_json()["type"] == "snapshot"
            assert socket.receive_json()["type"] == "telemetry"


def test_readiness_fails_when_source_has_finished(tmp_path) -> None:
    with TestClient(create_app(Settings(log_dir=tmp_path), CaptureSource([]))) as client:
        response = client.get("/healthz")
        assert response.status_code == 503
        assert response.json()["acquisition_running"] is False
        assert client.post("/api/v1/simulator/fault", json={"mode": "normal"}).status_code == 409


def test_readiness_fails_when_source_crashes(tmp_path) -> None:
    class BrokenSource(CaptureSource):
        async def chunks(self, stop):
            raise OSError("injected source failure")
            yield b""  # pragma: no cover

    with TestClient(create_app(Settings(log_dir=tmp_path), BrokenSource([]))) as client:
        assert client.get("/healthz").status_code == 503
