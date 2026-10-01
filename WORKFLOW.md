# Project workflow

Repository: https://github.com/RohitPatel97/networked-embedded-sensor-monitor

## Completed in September 2026

- [x] Bound protocol decoding, device history, and subscriber queues.
- [x] Reject stale/duplicate data before health, alert, and subscriber updates.
- [x] Support uint32 sequence rollover with a regression test.
- [x] Document problem/solution test cases and hardware limitations.
- [x] Run 50 tests on Windows Python 3.12.14; 93.09% coverage; Ruff passed.

## October 1, 2026 - bounded capture validation and replay

### Problem and expected behavior

The CLI accepted schema-valid records larger than the live decoder's 2048-byte limit, so a successful offline check did not establish that a capture would pass framing during ingestion. Replay loaded the entire capture and split at lone carriage returns as well as LF. Expected behavior: bounded reads, the same LF framing and byte limit as live input, one rejection per oversized record, correct physical error line numbers, and recovery for following valid records.

### Solution and regression evidence

- Share `capture.iter_capture_records` between validation and replay. Read at most 2050 bytes at a time, drain oversized physical lines, and retain only a 2049-byte prefix for rejection. File inputs may omit their final LF.
- Run CLI records through `NewlineJsonDecoder`; preserve its CRLF size accounting and whitespace rejection.
- Keep replay file operations on worker threads and finish an in-flight read before closing after cancellation.
- Cover exact frame limits, CRLF, EOF, oversized blank records, malformed UTF-8, physical line numbers, bounded reads, lone CR, replay loops, empty captures, and cancellation cleanup.
- Confirm through the hub that an oversized hot record cannot enter history, raise an alert, or reach subscribers, while the next valid record is accepted.
- Before implementation, the focused CLI/source suite produced **8 failed, 12 passed**. Failures reproduced oversized acceptance, missing oversized-blank rejection, unbounded replay loading, and lone-CR splitting.

### Observed result and publication

Local verification on Windows, Python 3.12.14:

```text
python -m pytest --cov=sensor_monitor --cov-report=term-missing
69 passed, 1 warning; combined line/branch coverage: 94.16%

python -m ruff check .
All checks passed!

sensor-monitor validate examples/telemetry.jsonl
accepted=3 rejected=0

git diff --check
No whitespace errors.
```

The commands used the repository's `.venv/Scripts` executables. The warning is an upstream Starlette/httpx test-client deprecation. The cancellation regression was added after its cleanup fix and passed; no failing-before result is claimed for that case.

Published implementation: [`105c46e19ca0183e5786c791e2ac4383a8fa69d1`](https://github.com/RohitPatel97/networked-embedded-sensor-monitor/commit/105c46e19ca0183e5786c791e2ac4383a8fa69d1), pushed to `main`.

Observed [GitHub Actions run 36883808043](https://github.com/RohitPatel97/networked-embedded-sensor-monitor/actions/runs/36883808043): **success** for Python 3.11, 3.12, and 3.13 (lint, tests, sample validation) and the production container build. CI emitted upstream action-runtime deprecation annotations; all jobs passed. This publication record is a subsequent documentation-only commit; the linked implementation commit identifies the tested source.

### Remaining limits

- These are host tests with generated capture files and mocked file I/O. They do not establish physical UART/Pi behavior or a hardware soak result.
- History and sequence baselines remain in memory. Looping replay keeps original sequences and does not reset freshness checks; use one-pass replay or the simulator as described in the README.
- Boot/session semantics and the separate FreeRTOS schema bridge are still pending.
- Serial reconnects still preserve partial decoder state; transport-boundary framing reset needs a separate change and regression test.
- Bounded capture buffering does not establish a measured process RSS or latency ceiling. Cancellation waits for the active file operation to finish; it cannot abort a stalled OS read.

## Reproduce validation

```sh
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest --cov=sensor_monitor --cov-report=term-missing
sensor-monitor validate examples/telemetry.jsonl
```

## Next tasks

1. Design an explicit boot/session identifier and replay policy, then define the FreeRTOS schema bridge. Acceptance: documented field/unit mappings and host tests for incompatible messages, duplicates, stale sessions, reboot, rollover, and gateway restart.
2. Reset framing across serial reconnects, then exercise UART disconnect/reconnect with an STM32 and Raspberry Pi. Acceptance: a host regression preserves the first complete post-reconnect frame without clearing sequence baselines; record board/image versions, capture files, commands, and physical results separately.
3. Run a long soak test and record memory, latency, drops, and reconnect behavior. Specify load and duration before interpreting results.

## Working agreement

For each change, capture the failing stimulus, expected behavior, implementation, regression test, command output, remaining limits, and commit. Run the relevant tests before committing; check the GitHub Actions run after pushing. Keep resume claims tied to source and observed evidence. This file is the durable record for the dedicated Codex project task.
