#!/usr/bin/env python3
"""Check projects/projects.json: fields, unique ids, names and Links codes, and the shape of each app's block.

  python3 check_projects.py
  python3 check_projects.py --against origin/main

With --against, it also compares the list with the version at that git ref, and fails if anything permanent
changed. A project id is permanent, so a project may not be removed. A Links code is permanent, so it may not
change, and a legacy value (an older value that means the same project) may not be dropped. Removing a
project or changing a code would silently break past links in Marin Links Stats. Renaming a project, adding a
project, adding a legacy value, and adding or removing a reach or mentions entry are allowed.
"""
import json
import re
import subprocess
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
    if "pulse" in p and p["pulse"] is not True:
        errors.append(f"{i}: pulse must be true, or left out")
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


def baseline(ref):
    """The project list at a git ref, or None when the file does not exist there yet."""
    shown = subprocess.run(["git", "show", f"{ref}:projects/projects.json"], cwd=ROOT, capture_output=True, text=True)
    if shown.returncode == 0:
        return json.loads(shown.stdout)["projects"]
    exists = subprocess.run(["git", "cat-file", "-e", f"{ref}:projects"], cwd=ROOT, capture_output=True, text=True)
    if subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=ROOT, capture_output=True).returncode != 0:
        sys.exit(f"cannot compare: the git ref {ref} does not exist here. Fetch it first, for example: git fetch origin main")
    if exists.returncode != 0:
        return None  # the list is new, so there is nothing to protect yet
    sys.exit(f"cannot read projects/projects.json at {ref}: {shown.stderr.strip()}")


if "--against" in sys.argv:
    ref = sys.argv[sys.argv.index("--against") + 1]
    before = baseline(ref)
    now = {p["id"]: p for p in doc["projects"]}
    for old_project in before or []:
        i = old_project["id"]
        if i not in now:
            errors.append(f"{i}: this project was removed. Ids are permanent. Never remove a project, because past links and records refer to it.")
            continue
        old_links, new_links = old_project.get("links"), now[i].get("links")
        if old_links:
            if not new_links:
                errors.append(f"{i}: its links entry was removed. Its code {old_links['code']} is permanent. Never drop a campaign, because past links in Stats use it.")
                continue
            if new_links["code"] != old_links["code"]:
                errors.append(f"{i}: links.code changed from {old_links['code']} to {new_links['code']}. A code is permanent. Never change, reuse, or renumber it.")
            dropped = sorted(set(old_links.get("legacy", [])) - set(new_links.get("legacy", [])))
            if dropped:
                errors.append(f"{i}: links.legacy lost {dropped}. Older values are kept so past visits still resolve.")

print("\n".join(errors) if errors else f"ok: {len(doc['projects'])} projects ({len(codes)} in Links, {sum(1 for p in doc['projects'] if p.get('reach'))} in Reach, {sum(1 for p in doc['projects'] if 'mentions' in p)} in Mentions)")
sys.exit(1 if errors else 0)
