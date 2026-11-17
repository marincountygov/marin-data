#!/usr/bin/env python3
"""Check projects/projects.json: fields, unique ids, names and Links codes, and the shape of each app's block.

  python3 check_projects.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
doc = json.loads((ROOT / "projects" / "projects.json").read_text())
schema = json.loads((ROOT / "schemas" / "projects.schema.json").read_text())
item = schema["properties"]["projects"]["items"]
allowed, links_allowed = set(item["properties"]), set(item["properties"]["links"]["properties"])
mentions_allowed = set(item["properties"]["mentions"]["properties"])
SLUG, CODE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$"), re.compile(r"^cmp-[0-9]{2,}$")
errors, ids, names, codes = [], set(), set(), set()

for p in doc["projects"]:
    i = p.get("id", "?")
    for k in item["required"]:
        if not p.get(k):
            errors.append(f"{i}: missing {k}")
    for k in p:
        if k not in allowed:
            errors.append(f"{i}: unknown field {k}")
    if not SLUG.match(str(p.get("id", ""))):
        errors.append(f"{i}: id must be lowercase words with hyphens")
    if i in ids:
        errors.append(f"{i}: id is used twice")
    ids.add(i)
    n = str(p.get("name", "")).strip().casefold()
    if n in names:
        errors.append(f"{i}: name {p.get('name')!r} is used twice")
    names.add(n)
    if "reach" in p and p["reach"] is not True:
        errors.append(f"{i}: reach must be true, or left out")
    if "links" in p:
        links = p["links"]
        for k in links:
            if k not in links_allowed:
                errors.append(f"{i}: links has an unknown field {k}")
        if not CODE.match(str(links.get("code", ""))):
            errors.append(f"{i}: links.code must look like cmp-01")
        if links.get("code") in codes:
            errors.append(f"{i}: links.code {links.get('code')} is used twice")
        codes.add(links.get("code"))
        if not isinstance(links.get("legacy"), list):
            errors.append(f"{i}: links.legacy must be a list (it may be empty)")
    if "mentions" in p:
        m = p["mentions"]
        for k in m:
            if k not in mentions_allowed:
                errors.append(f"{i}: mentions has an unknown field {k}")
        if not isinstance(m.get("include"), list) or not m["include"] or not all(isinstance(x, str) and x.strip() for x in m["include"]):
            errors.append(f"{i}: mentions.include must list at least one phrase")

print("\n".join(errors) if errors else f"ok: {len(doc['projects'])} projects ({len(codes)} in Links, {sum(1 for p in doc['projects'] if p.get('reach'))} in Reach, {sum(1 for p in doc['projects'] if 'mentions' in p)} in Mentions)")
sys.exit(1 if errors else 0)
