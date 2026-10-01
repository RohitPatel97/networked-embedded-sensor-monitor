# Changelog

## Unreleased - 2026-10-01

- Enforce the live 2048-byte frame limit in capture validation, with physical error line numbers and recovery after invalid records.
- Stream replay captures through bounded reads instead of loading the entire file; preserve LF framing and accept an optional final newline.
- Keep replay file open, read, and close operations off the event loop, including cleanup after cancellation.
- Add capture boundary, recovery, bounded-read, cancellation, and downstream alert/WebSocket regression tests.
- Clarify PowerShell setup, one-pass replay, repeated-sequence rejection, validation scope, and remaining integration limits in the README.

## 1.1.0 - 2026-09-04

- Reject duplicate, backward, and ambiguous sequence numbers before changing health, history, alerts, or WebSocket output.
- Accept unsigned 32-bit rollover and preserve per-device sequence baselines.
- Add regression cases for stale-data rejection, wraparound, independent devices, and alert/fan-out isolation.
- Document reproducible problem/solution cases, local verification, and reboot/session limitations.

## 1.0.0 - 2026-08-26

- Added strict, bounded newline-delimited JSON ingestion.
- Added serial, replay, and deterministic simulator sources.
- Added bounded telemetry history, device health, transition-based alerts, REST endpoints, and WebSocket fan-out.
- Added a dependency-free dashboard, rotating logs, systemd and container deployment assets, tests, and CI.
