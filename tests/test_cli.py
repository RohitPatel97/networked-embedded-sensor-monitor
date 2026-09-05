from __future__ import annotations

from sensor_monitor.cli import main


def test_validate_example_capture() -> None:
    assert main(["validate", "examples/telemetry.jsonl"]) == 0


def test_simulate_emits_requested_count(capsys) -> None:
    assert main(["simulate", "--count", "2", "--interval", "0"]) == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 2
