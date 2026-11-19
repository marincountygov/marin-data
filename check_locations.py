#!/usr/bin/env python3
"""Check that no location code that Marin Links may already have sent has been removed or changed.

  python3 check_locations.py --against origin/main

Compares organizations/locations.json with the version at that git ref. A code is permanent: it is inside
links people have shared, and Marin Links Stats reads it back. A location may be renamed or added. A code may
not be removed, so a place that closes keeps its record and its code.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if "--against" not in sys.argv:
    sys.exit("usage: check_locations.py --against <git ref>")
ref = sys.argv[sys.argv.index("--against") + 1]
now = {l["code"]: l for l in json.loads((ROOT / "organizations" / "locations.json").read_text())["locations"]}
if subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=ROOT, capture_output=True).returncode != 0:
    sys.exit(f"cannot compare: the git ref {ref} does not exist here. Fetch it first, for example: git fetch origin main")
shown = subprocess.run(["git", "show", f"{ref}:organizations/locations.json"], cwd=ROOT, capture_output=True, text=True)
before = json.loads(shown.stdout)["locations"] if shown.returncode == 0 else []  # not there yet: nothing to protect
errors = []
for old in before:
    if old["code"] not in now:
        errors.append(f"{old['code']}: this location code was removed. A code is permanent. Past links and Stats use it.")
    elif now[old["code"]]["id"] != old["id"]:
        errors.append(f"{old['code']}: it now points at a different place. A code must keep meaning the same place.")
print("\n".join(errors) if errors else f"ok: {len(before)} location codes at {ref} are all still here ({len(now)} now)")
sys.exit(1 if errors else 0)
