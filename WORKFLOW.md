# Project workflow

Repository: https://github.com/RohitPatel97/networked-embedded-sensor-monitor

## Completed in September 2026

- [x] Bound protocol decoding, device history, and subscriber queues.
- [x] Reject stale/duplicate data before health, alert, and subscriber updates.
- [x] Support uint32 sequence rollover with a regression test.
- [x] Document problem/solution test cases and hardware limitations.
- [x] Run 50 tests on Windows Python 3.12.14; 93.09% coverage; Ruff passed.

## Reproduce validation

```sh
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest --cov=sensor_monitor --cov-report=term-missing
sensor-monitor validate examples/telemetry.jsonl
```

## Next tasks

1. Design an explicit boot/session identifier and replay policy. Acceptance: duplicate, stale-session, reboot, and rollover tests show the correct state and alert behavior.
2. Exercise UART disconnect/reconnect with an STM32 and Raspberry Pi. Record board/image versions, capture files, commands, and results; keep simulated and physical results separate.
3. Run a long soak test and record memory, latency, drops, and reconnect behavior. Specify load and duration before interpreting results.

## Working agreement

For each change, capture the failing stimulus, expected behavior, implementation, regression test, command output, remaining limits, and commit. Run the relevant tests before committing; check the GitHub Actions run after pushing. Keep resume claims tied to source and observed evidence. This file is the durable record for the dedicated Codex project task.
