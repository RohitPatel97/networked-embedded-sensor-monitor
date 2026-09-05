"""Strict newline-delimited JSON framing used on the STM32 UART link."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime

from pydantic import ValidationError

from .models import TelemetryReading, WireTelemetry, utc_now


class ProtocolError(ValueError):
    """Base class for rejected UART frames."""


class FrameTooLargeError(ProtocolError):
    """Raised when a peer exceeds the bounded receive buffer."""


class FrameDecodeError(ProtocolError):
    """Raised when UTF-8, JSON, or schema validation fails."""


class NewlineJsonDecoder:
    """Incrementally split a byte stream into bounded, validated telemetry frames."""

    def __init__(self, max_frame_bytes: int = 2_048) -> None:
        if max_frame_bytes < 64:
            raise ValueError("max_frame_bytes is unreasonably small")
        self.max_frame_bytes = max_frame_bytes
        self._buffer = bytearray()
        self._discarding = False

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def feed(
        self, chunk: bytes, *, received_at: datetime | None = None
    ) -> Iterable[TelemetryReading]:
        """Strict convenience API: raise on any rejected frame in this chunk."""
        events = self.feed_events(chunk, received_at=received_at)
        errors = [event for event in events if isinstance(event, ProtocolError)]
        if errors:
            raise errors[0]
        return [event for event in events if isinstance(event, TelemetryReading)]

    def feed_events(
        self, chunk: bytes, *, received_at: datetime | None = None
    ) -> list[TelemetryReading | ProtocolError]:
        """Recover at each newline, preserving valid frames around a malformed one."""
        if not isinstance(chunk, bytes):
            raise TypeError("chunk must be bytes")
        events: list[TelemetryReading | ProtocolError] = []
        parts = chunk.split(b"\n")
        for index, part in enumerate(parts):
            terminated = index < len(parts) - 1
            if not self._discarding:
                if len(self._buffer) + len(part) > self.max_frame_bytes:
                    self._buffer.clear()
                    self._discarding = True
                    events.append(FrameTooLargeError("frame exceeded receive limit"))
                else:
                    self._buffer.extend(part)
            if terminated:
                if not self._discarding:
                    raw = bytes(self._buffer).rstrip(b"\r")
                    if raw:
                        try:
                            events.append(parse_frame(raw, received_at=received_at))
                        except ProtocolError as exc:
                            events.append(exc)
                self._buffer.clear()
                self._discarding = False
        return events


def parse_frame(raw: bytes, *, received_at: datetime | None = None) -> TelemetryReading:
    try:
        text = raw.decode("utf-8", errors="strict")
        wire = WireTelemetry.model_validate_json(text, strict=True)
    except (UnicodeDecodeError, ValidationError) as exc:
        raise FrameDecodeError(str(exc)) from exc
    return TelemetryReading(
        **wire.model_dump(), received_at=received_at or utc_now()
    )


def encode_frame(reading: WireTelemetry) -> bytes:
    """Produce the compact, deterministic representation used by fixtures/simulator."""
    return (
        json.dumps(reading.model_dump(), separators=(",", ":"), sort_keys=True).encode()
        + b"\n"
    )
