#!/usr/bin/env python3
"""Dependency-free deployment smoke test for CI or a Raspberry Pi."""

from __future__ import annotations

import json
import sys
from urllib.request import urlopen

base_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"
with urlopen(f"{base_url}/healthz", timeout=3) as response:
    health = json.load(response)
with urlopen(f"{base_url}/api/v1/snapshot", timeout=3) as response:
    snapshot = json.load(response)

assert health["status"] == "ok", health
assert isinstance(snapshot["devices"], list), snapshot
print(
    f"ok source={health['source']} accepted={snapshot['stats']['frames_accepted']} "
    f"devices={len(snapshot['devices'])}"
)
