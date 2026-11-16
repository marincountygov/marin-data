#!/usr/bin/env python3
"""Check that a consumer's copies of marin-data files are current, using consumers.json.

  python3 check_copies.py ../marin-docs

The consumer is found by its folder name. Fails if a copied file is missing or differs from marin-data.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if len(sys.argv) != 2:
    sys.exit("usage: check_copies.py <consumer folder>")
consumer = Path(sys.argv[1]).resolve()
entry = next((c for c in json.loads((ROOT / "consumers.json").read_text())["consumers"] if c["repo"] == consumer.name), None)
if entry is None:
    sys.exit(f"{consumer.name} is not listed in consumers.json")
errors = []
for item in entry["copies"]:
    src, dst = ROOT / item["from"], consumer / item["to"]
    if not dst.is_file():
        errors.append(f"{item['to']}: missing")
    elif dst.read_bytes() != src.read_bytes():
        errors.append(f"{item['to']}: differs from marin-data/{item['from']}")
if errors:
    sys.exit(f"{consumer.name} is out of date with marin-data:\n  " + "\n  ".join(errors)
             + "\nRun the sync and build commands listed for it in marin-data/consumers.json.")
print(f"ok: {consumer.name} has {len(entry['copies'])} current copies")
