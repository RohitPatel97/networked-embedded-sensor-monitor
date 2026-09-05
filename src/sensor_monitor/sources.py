"""UART, deterministic simulator, and JSONL replay telemetry sources."""

from __future__ import annotations

import asyncio
import logging
import math
import random
from collections.abc import AsyncIterator
from pathlib import Path

from .config import Settings
from .models import FaultMode, WireTelemetry
from .protocol import encode_frame

LOGGER = logging.getLogger(__name__)


class TelemetrySource:
    name = "unknown"
    reconnects = 0

    async def chunks(self, stop: asyncio.Event) -> AsyncIterator[bytes]:
        """Yield one or more chunks from an underlying byte stream."""
        raise NotImplementedError
        yield b""  # pragma: no cover - keeps the base contract an async iterator

    async def close(self) -> None:
        """Release external resources; sources without resources need no override."""
        return None


class SimulatorSource(TelemetrySource):
    name = "simulator"

    def __init__(self, rate_hz: float = 10.0, seed: int = 7) -> None:
        self.rate_hz = rate_hz
        self._random = random.Random(seed)
        self._sequence = 0
        self._mode = FaultMode.NORMAL

    @property
    def mode(self) -> FaultMode:
        return self._mode

    def set_fault(self, mode: FaultMode) -> None:
        self._mode = mode

    async def chunks(self, stop: asyncio.Event) -> AsyncIterator[bytes]:
        interval = 1.0 / self.rate_hz
        start = asyncio.get_running_loop().time()
        while not stop.is_set():
            if self._mode == FaultMode.DISCONNECTED:
                await asyncio.sleep(interval)
                continue
            elapsed = asyncio.get_running_loop().time() - start
            jitter = self._random.uniform(-0.08, 0.08)
            temperature = 24.0 + 2.0 * math.sin(elapsed / 7.0) + jitter
            if self._mode == FaultMode.OVER_TEMPERATURE:
                temperature = 86.0 + jitter
            reading = WireTelemetry(
                device_id="stm32-sensor-hub",
                sequence=self._sequence,
                uptime_ms=int(elapsed * 1_000),
                temperature_c=round(temperature, 3),
                pressure_hpa=round(1013.25 + 1.8 * math.sin(elapsed / 11.0), 3),
                accel_g=(
                    round(0.02 * math.sin(elapsed), 4),
                    round(0.02 * math.cos(elapsed), 4),
                    round(1.0 + self._random.uniform(-0.006, 0.006), 4),
                ),
                battery_v=12.4,
                i2c_errors=1 if self._mode == FaultMode.I2C_ERROR else 0,
                queue_drops=5 if self._mode == FaultMode.QUEUE_PRESSURE else 0,
                watchdog_resets=0,
            )
            self._sequence = (self._sequence + 1) & 0xFFFFFFFF
            yield encode_frame(reading)
            await asyncio.sleep(interval)


class ReplaySource(TelemetrySource):
    name = "replay"

    def __init__(self, path: Path, rate_hz: float = 10.0, loop: bool = True) -> None:
        self.path = path
        self.rate_hz = rate_hz
        self.loop = loop

    async def chunks(self, stop: asyncio.Event) -> AsyncIterator[bytes]:
        interval = 1.0 / self.rate_hz
        while not stop.is_set():
            lines = await asyncio.to_thread(self.path.read_bytes)
            emitted = False
            for line in lines.splitlines():
                if stop.is_set():
                    return
                if line.strip():
                    emitted = True
                    yield line + b"\n"
                    await asyncio.sleep(interval)
            if not self.loop or not emitted:
                return


class SerialSource(TelemetrySource):
    name = "serial"

    def __init__(self, port: str, baud_rate: int, reconnect_delay: float = 1.0) -> None:
        self.port = port
        self.baud_rate = baud_rate
        self.reconnect_delay = reconnect_delay
        self._serial: object | None = None
        self.reconnects = 0

    async def chunks(self, stop: asyncio.Event) -> AsyncIterator[bytes]:
        try:
            import serial
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise RuntimeError("serial source requires pyserial") from exc

        while not stop.is_set():
            try:
                self._serial = await asyncio.to_thread(
                    serial.Serial,
                    self.port,
                    self.baud_rate,
                    timeout=0.5,
                    exclusive=True,
                )
                while not stop.is_set():
                    chunk = await asyncio.to_thread(self._serial.read_until, b"\n", 2_049)
                    if chunk:
                        yield chunk
            except (serial.SerialException, OSError):
                self.reconnects += 1
                LOGGER.warning(
                    "serial source unavailable; retrying in %.1f s",
                    self.reconnect_delay,
                    extra={"port": self.port, "attempt": self.reconnects},
                )
                await self.close()
                await asyncio.sleep(self.reconnect_delay)
            finally:
                await self.close()

    async def close(self) -> None:
        serial_port, self._serial = self._serial, None
        if serial_port is not None:
            await asyncio.to_thread(serial_port.close)


def build_source(settings: Settings) -> TelemetrySource:
    if settings.source == "simulator":
        return SimulatorSource(settings.simulator_rate_hz, settings.simulator_seed)
    if settings.source == "serial":
        return SerialSource(settings.serial_port, settings.baud_rate)
    assert settings.replay_file is not None
    return ReplaySource(
        settings.replay_file, settings.simulator_rate_hz, settings.replay_loop
    )
