#!/usr/bin/env python3
"""Run the sync and build commands that consumers.json lists for one consumer repo.

  python3 scripts/sync_consumer.py ../marin-links

Run it from anywhere. The commands run inside the consumer's folder, with marin-data next to it.
The consumer is found by its folder name.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if len(sys.argv) != 2:
    sys.exit("usage: sync_consumer.py <consumer folder>")
consumer = Path(sys.argv[1]).resolve()
entry = next((c for c in json.loads((ROOT / "consumers.json").read_text())["consumers"] if c["repo"] == consumer.name), None)
if entry is None:
    sys.exit(f"{consumer.name} is not listed in consumers.json")
for cmd in entry["sync"] + entry["build"]:
    print(f"$ {cmd}", flush=True)
    if subprocess.run(cmd, shell=True, cwd=consumer).returncode != 0:
        sys.exit(f"ERROR: this command failed in {consumer.name}: {cmd}")
print(f"ran {len(entry['sync']) + len(entry['build'])} commands for {consumer.name}")
