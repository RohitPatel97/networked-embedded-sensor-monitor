"""Command line entry points for serving, simulating, and validating telemetry."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import uvicorn

from .config import Settings
from .models import WireTelemetry
from .protocol import ProtocolError, parse_frame


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sensor-monitor")
    subcommands = parser.add_subparsers(dest="command", required=True)

    serve = subcommands.add_parser("serve", help="run the API and dashboard")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.add_argument("--reload", action="store_true")

    simulate = subcommands.add_parser(
        "simulate", help="write firmware-shaped JSONL telemetry to stdout"
    )
    simulate.add_argument("--count", type=int, default=10)
    simulate.add_argument("--interval", type=float, default=0.1)

    validate = subcommands.add_parser(
        "validate", help="validate a JSONL capture against the UART schema"
    )
    validate.add_argument("path", type=Path)
    return parser


def _simulate(count: int, interval: float) -> int:
    for sequence in range(count):
        reading = WireTelemetry(
            device_id="stm32-sensor-hub",
            sequence=sequence,
            uptime_ms=sequence * int(interval * 1_000),
            temperature_c=24.5,
            pressure_hpa=1013.25,
            accel_g=(0.0, 0.0, 1.0),
            battery_v=12.4,
        )
        print(json.dumps(reading.model_dump(), separators=(",", ":")), flush=True)
        if sequence + 1 < count:
            time.sleep(interval)
    return 0


def _validate(path: Path) -> int:
    accepted = 0
    rejected = 0
    with path.open("rb") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                parse_frame(line.rstrip(b"\r\n"))
                accepted += 1
            except ProtocolError as exc:
                rejected += 1
                print(f"line {line_number}: {exc}", file=sys.stderr)
    print(f"accepted={accepted} rejected={rejected}")
    return 1 if rejected else 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "simulate":
        return _simulate(args.count, args.interval)
    if args.command == "validate":
        return _validate(args.path)

    settings = Settings.from_env()
    uvicorn.run(
        "sensor_monitor.app:app",
        host=args.host or settings.host,
        port=args.port or settings.port,
        reload=args.reload,
    )
    return 0
