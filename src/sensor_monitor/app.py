"""FastAPI application factory and REST/WebSocket transport layer."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import Settings
from .hub import TelemetryHub
from .logging_setup import configure_logging
from .models import (
    Alert,
    DeviceHealth,
    FaultRequest,
    ServiceStats,
    Snapshot,
    TelemetryReading,
)
from .sources import SimulatorSource, TelemetrySource, build_source

LOGGER = logging.getLogger(__name__)
WEB_DIR = Path(__file__).parent / "web"


def create_app(
    settings: Settings | None = None, source: TelemetrySource | None = None
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    configure_logging(resolved_settings)
    resolved_source = source or build_source(resolved_settings)
    hub = TelemetryHub(resolved_settings, resolved_source)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        task = asyncio.create_task(hub.run(), name="telemetry-acquisition")
        application.state.acquisition_task = task
        try:
            yield
        finally:
            await hub.stop()
            if task.done():
                if not task.cancelled() and task.exception() is not None:
                    LOGGER.error("acquisition task had stopped before shutdown")
            else:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(
        title="Networked Embedded Sensor Monitor",
        summary="STM32 telemetry gateway with REST, WebSocket, alerts, and health state",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.source = resolved_source
    app.state.hub = hub
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def dashboard() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        task = getattr(app.state, "acquisition_task", None)
        running = task is not None and not task.done() and not hub.stopped
        return JSONResponse(
            status_code=200 if running else 503,
            content={
                "status": "ok" if running else "unavailable",
                "version": __version__,
                "source": resolved_source.name,
                "frames_accepted": hub.stats().frames_accepted,
                "acquisition_running": running,
            },
        )

    @app.get("/api/v1/devices", response_model=list[DeviceHealth])
    async def devices() -> list[DeviceHealth]:
        return await hub.store.all_health()

    @app.get("/api/v1/devices/{device_id}", response_model=DeviceHealth)
    async def device(device_id: str) -> DeviceHealth:
        health = await hub.store.health(device_id)
        if health is None:
            raise HTTPException(status_code=404, detail="device not found")
        return health

    @app.get(
        "/api/v1/devices/{device_id}/readings",
        response_model=list[TelemetryReading],
    )
    async def readings(
        device_id: str, limit: int = Query(default=100, ge=1, le=600)
    ) -> list[TelemetryReading]:
        if device_id not in await hub.store.device_ids():
            raise HTTPException(status_code=404, detail="device not found")
        return await hub.store.readings(device_id, limit)

    @app.get("/api/v1/alerts", response_model=list[Alert])
    async def alerts(
        limit: int = Query(default=50, ge=1, le=200)
    ) -> list[Alert]:
        return await hub.store.alerts(limit)

    @app.get("/api/v1/stats", response_model=ServiceStats)
    async def stats() -> ServiceStats:
        return hub.stats()

    @app.get("/api/v1/snapshot", response_model=Snapshot)
    async def snapshot() -> Snapshot:
        return await hub.snapshot()

    @app.post("/api/v1/simulator/fault")
    async def simulator_fault(request: FaultRequest) -> dict[str, str]:
        if not isinstance(resolved_source, SimulatorSource):
            raise HTTPException(
                status_code=409, detail="fault control is only available in simulator mode"
            )
        resolved_source.set_fault(request.mode)
        LOGGER.info("simulator fault mode changed to %s", request.mode)
        return {"mode": request.mode.value}

    @app.websocket("/ws/telemetry")
    async def telemetry_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json((await hub.snapshot()).model_dump(mode="json"))
        try:
            async with hub.subscribe() as queue:
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=5.0)
                    except TimeoutError:
                        event = {
                            "type": "heartbeat",
                            "stats": hub.stats().model_dump(mode="json"),
                            "devices": [
                                device.model_dump(mode="json")
                                for device in await hub.store.all_health()
                            ],
                        }
                    await websocket.send_json(event)
        except WebSocketDisconnect:
            return

    return app


app = create_app()
