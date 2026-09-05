"""Wire and API models for telemetry, health, alerts, and service statistics."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WireTelemetry(StrictModel):
    schema_version: Literal[1] = 1
    device_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    sequence: int = Field(ge=0, le=4_294_967_295)
    uptime_ms: int = Field(ge=0)
    temperature_c: float = Field(ge=-50.0, le=150.0)
    pressure_hpa: float = Field(ge=300.0, le=1_200.0)
    accel_g: tuple[float, float, float]
    battery_v: float | None = Field(default=None, ge=0.0, le=30.0)
    i2c_errors: int = Field(default=0, ge=0)
    queue_drops: int = Field(default=0, ge=0)
    watchdog_resets: int = Field(default=0, ge=0)

    @field_validator("schema_version", mode="before")
    @classmethod
    def schema_is_integer(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be an integer, not a boolean or string")
        return value

    @field_validator("accel_g")
    @classmethod
    def acceleration_is_in_sensor_range(
        cls, value: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        if any(not isfinite(axis) or abs(axis) > 16.0 for axis in value):
            raise ValueError("accelerometer axes must be within +/-16 g")
        return value


class TelemetryReading(WireTelemetry):
    received_at: datetime = Field(default_factory=utc_now)


class DeviceState(StrEnum):
    ONLINE = "online"
    DEGRADED = "degraded"
    STALE = "stale"
    OFFLINE = "offline"


class DeviceHealth(StrictModel):
    device_id: str
    state: DeviceState
    last_seen: datetime
    age_seconds: float = Field(ge=0.0)
    last_sequence: int
    i2c_errors: int
    queue_drops: int
    watchdog_resets: int
    detail: str


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Alert(StrictModel):
    id: str
    device_id: str
    code: str
    severity: AlertSeverity
    message: str
    active: bool
    observed_value: float | int | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ServiceStats(StrictModel):
    started_at: datetime
    frames_received: int = 0
    frames_accepted: int = 0
    parse_errors: int = 0
    sequence_anomalies: int = 0
    device_rejections: int = 0
    websocket_clients: int = 0
    websocket_drops: int = 0
    source_reconnects: int = 0


class Snapshot(StrictModel):
    type: Literal["snapshot"] = "snapshot"
    devices: list[DeviceHealth]
    alerts: list[Alert]
    stats: ServiceStats


class FaultMode(StrEnum):
    NORMAL = "normal"
    DISCONNECTED = "disconnected"
    I2C_ERROR = "i2c_error"
    OVER_TEMPERATURE = "over_temperature"
    QUEUE_PRESSURE = "queue_pressure"


class FaultRequest(StrictModel):
    mode: FaultMode


JsonScalar = Annotated[str | int | float | bool | None, Field()]
