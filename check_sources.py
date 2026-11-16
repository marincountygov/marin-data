#!/usr/bin/env python3
"""Check sources.json: required fields, unique ids, and hashes of files stored in marin-data.

  python3 scripts_check_sources.py            check the registry
  python3 scripts_check_sources.py --urls     also check that each url answers (some County hosts block scripts)
"""
import hashlib, json, re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
reg = json.loads((ROOT / "sources.json").read_text())
schema = json.loads((ROOT / "schemas" / "sources.schema.json").read_text())
props = schema["properties"]["sources"]["items"]
required = props["required"]
allowed = set(props["properties"])
errors, seen = [], set()
for s in reg["sources"]:
    i = s.get("id", "?")
    for k in required:
        if s.get(k) in (None, "", []):
            errors.append(f"{i}: missing {k}")
    for k in s:
        if k not in allowed:
            errors.append(f"{i}: unknown field {k}")
    if i in seen:
        errors.append(f"{i}: duplicate id")
    seen.add(i)
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i):
        errors.append(f"{i}: bad id")
    if s.get("access") == "internal":
        if s.get("url") or s.get("file"):
            errors.append(f"{i}: an internal source must have no url and no file")
    elif bool(s.get("url")) == bool(s.get("file")):
        errors.append(f"{i}: needs exactly one of url or file")
    if s.get("file"):
        p = ROOT / s["file"]
        if not p.is_file():
            errors.append(f"{i}: file not found {s['file']}")
        else:
            data = p.read_bytes()
            if hashlib.sha256(data).hexdigest() != s["sha256"]:
                errors.append(f"{i}: sha256 does not match {s['file']}")
            if len(data) != s["bytes"]:
                errors.append(f"{i}: byte size does not match {s['file']}")
    if "--urls" in sys.argv and s.get("url"):
        try:
            req = urllib.request.Request(s["url"], method="HEAD")
            urllib.request.urlopen(req, timeout=20)
        except Exception as e:
            errors.append(f"{i}: url check failed ({e})")
print("\n".join(errors) if errors else f"ok: {len(reg['sources'])} sources")
sys.exit(1 if errors else 0)
