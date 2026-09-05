from __future__ import annotations

import asyncio

import pytest

from sensor_monitor.config import Settings
from sensor_monitor.models import FaultMode
from sensor_monitor.protocol import parse_frame
from sensor_monitor.sources import (
    ReplaySource,
    SerialSource,
    SimulatorSource,
    TelemetrySource,
    build_source,
)


def test_simulator_is_deterministic_and_fault_controllable() -> None:
    async def scenario() -> None:
        stop = asyncio.Event()
        source = SimulatorSource(rate_hz=1000, seed=4)
        source.set_fault(FaultMode.I2C_ERROR)
        stream = source.chunks(stop)
        first = parse_frame((await anext(stream)).rstrip())
        stop.set()
        await stream.aclose()
        assert first.sequence == 0
        assert first.i2c_errors == 1
        assert source.mode is FaultMode.I2C_ERROR

    asyncio.run(scenario())


def test_replay_source_emits_each_nonempty_line_once(tmp_path) -> None:
    async def scenario() -> None:
        capture = tmp_path / "capture.jsonl"
        capture.write_bytes(b'{"a":1}\n\n{"b":2}\n')
        source = ReplaySource(capture, rate_hz=1000, loop=False)
        chunks = [chunk async for chunk in source.chunks(asyncio.Event())]
        assert chunks == [b'{"a":1}\n', b'{"b":2}\n']

    asyncio.run(scenario())


def test_source_factory_selects_configured_adapter(tmp_path) -> None:
    assert isinstance(build_source(Settings()), SimulatorSource)
    assert isinstance(build_source(Settings(source="serial")), SerialSource)
    capture = tmp_path / "capture.jsonl"
    capture.write_text("", encoding="utf-8")
    assert isinstance(
        build_source(Settings(source="replay", replay_file=capture)), ReplaySource
    )


def test_base_source_requires_chunks_implementation() -> None:
    async def scenario() -> None:
        source = TelemetrySource()
        with pytest.raises(NotImplementedError):
            await anext(source.chunks(asyncio.Event()))
        assert await source.close() is None

    asyncio.run(scenario())
