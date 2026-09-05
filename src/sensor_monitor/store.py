"""Bounded, concurrency-safe in-memory telemetry and alert store."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import datetime

from .config import Settings
from .models import Alert, DeviceHealth, DeviceState, TelemetryReading, utc_now


class DeviceCapacityError(ValueError):
    """The configured device-count memory limit has been reached."""


class TelemetryStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._readings: dict[str, deque[TelemetryReading]] = defaultdict(
            lambda: deque(maxlen=settings.history_size)
        )
        self._alerts: deque[Alert] = deque(maxlen=settings.alert_history_size)
        self._lock = asyncio.Lock()

    async def add_reading(self, reading: TelemetryReading) -> bool:
        """Store fresh samples only, using uint32 serial-number arithmetic.

        Duplicate, backward, and ambiguous half-range jumps do not refresh health,
        replace history, or change the accepted sequence baseline.
        """
        async with self._lock:
            if (
                reading.device_id not in self._readings
                and len(self._readings) >= self.settings.max_devices
            ):
                raise DeviceCapacityError("device limit reached")
            history = self._readings[reading.device_id]
            if history:
                delta = (reading.sequence - history[-1].sequence) & 0xFFFFFFFF
                if not 0 < delta < 0x80000000:
                    return False
            history.append(reading)
            return True

    async def add_alerts(self, alerts: list[Alert]) -> None:
        async with self._lock:
            self._alerts.extend(alerts)

    async def readings(self, device_id: str, limit: int) -> list[TelemetryReading]:
        async with self._lock:
            history = self._readings.get(device_id)
            if not history:
                return []
            return list(history)[-limit:]

    async def alerts(self, limit: int) -> list[Alert]:
        async with self._lock:
            return list(self._alerts)[-limit:][::-1]

    async def device_ids(self) -> list[str]:
        async with self._lock:
            return sorted(self._readings)

    async def health(
        self, device_id: str, *, now: datetime | None = None
    ) -> DeviceHealth | None:
        async with self._lock:
            history = self._readings.get(device_id)
            if not history:
                return None
            latest = history[-1]
        return self._health_from(latest, now=now or utc_now())

    async def all_health(self, *, now: datetime | None = None) -> list[DeviceHealth]:
        async with self._lock:
            latest = [history[-1] for history in self._readings.values() if history]
        instant = now or utc_now()
        return sorted(
            (self._health_from(reading, now=instant) for reading in latest),
            key=lambda health: health.device_id,
        )

    def _health_from(self, reading: TelemetryReading, *, now: datetime) -> DeviceHealth:
        age = max(0.0, (now - reading.received_at).total_seconds())
        if age >= self.settings.offline_after_seconds:
            state, detail = DeviceState.OFFLINE, "telemetry timeout exceeded"
        elif age >= self.settings.stale_after_seconds:
            state, detail = DeviceState.STALE, "telemetry is stale"
        elif (
            reading.watchdog_resets
            or reading.i2c_errors
            or reading.queue_drops
            or reading.temperature_c >= self.settings.warning_temperature_c
            or (
                reading.battery_v is not None
                and reading.battery_v < self.settings.low_battery_v
            )
        ):
            state, detail = DeviceState.DEGRADED, "device reports a fault condition"
        else:
            state, detail = DeviceState.ONLINE, "telemetry is current"
        return DeviceHealth(
            device_id=reading.device_id,
            state=state,
            last_seen=reading.received_at,
            age_seconds=round(age, 3),
            last_sequence=reading.sequence,
            i2c_errors=reading.i2c_errors,
            queue_drops=reading.queue_drops,
            watchdog_resets=reading.watchdog_resets,
            detail=detail,
        )
