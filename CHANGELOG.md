# Changelog

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
