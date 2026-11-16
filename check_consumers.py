#!/usr/bin/env python3
"""Check consumers.json: every file a consumer copies exists here, and every dependsOn names a listed repo.

  python3 check_consumers.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
doc = json.loads((ROOT / "consumers.json").read_text())
errors, repos = [], [c["repo"] for c in doc["consumers"]]
if len(repos) != len(set(repos)):
    errors.append("a repo is listed twice")
for c in doc["consumers"]:
    for k in ("repo", "copies", "sync", "build", "check"):
        if k not in c:
            errors.append(f"{c.get('repo', '?')}: missing {k}")
    for item in c.get("copies", []):
        if not (ROOT / item["from"]).is_file():
            errors.append(f"{c['repo']}: {item['from']} does not exist in marin-data")
    tos = [i["to"] for i in c.get("copies", [])]
    if len(tos) != len(set(tos)):
        errors.append(f"{c['repo']}: two files are copied to the same place")
    for dep in c.get("dependsOn", []):
        if dep not in repos:
            errors.append(f"{c['repo']}: dependsOn {dep}, which is not listed")
print("\n".join(errors) if errors else f"ok: {len(repos)} consumers, {sum(len(c['copies']) for c in doc['consumers'])} copied files")
sys.exit(1 if errors else 0)
