#!/usr/bin/env python3
"""Check engage/campaigns.json: each campaign has a unique id, a name and a link on Engage Marin, belongs to exactly one
project (in projects/projects.json) or organization (in output/organizations.jsonld), and has questions with text and a link.

  python3 check_engage.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
doc = json.loads((ROOT / "engage" / "campaigns.json").read_text())
projects = {p["id"] for p in json.loads((ROOT / "projects" / "projects.json").read_text())["projects"]}
orgs = {o["@id"].rsplit("/", 1)[-1] for o in json.loads((ROOT / "output" / "organizations.jsonld").read_text())["@graph"]}
SLUG, SITE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$"), "https://engage.marincounty.gov/"
errors, ids, urls = [], set(), set()

for c in doc["campaigns"]:
    i = c.get("id", "?")
    for k in c:
        if k not in {"id", "name", "url", "project", "organization", "questions"}:
            errors.append(f"{i}: unknown field {k}")
    if not SLUG.match(str(i)) or i in ids:
        errors.append(f"{i}: id must be lowercase words with hyphens, and used once")
    ids.add(i)
    if not str(c.get("name", "")).strip():
        errors.append(f"{i}: missing name")
    if ("project" in c) == ("organization" in c):
        errors.append(f"{i}: give exactly one of project or organization")
    if "project" in c and c["project"] not in projects:
        errors.append(f"{i}: project {c['project']} is not in projects/projects.json")
    if "organization" in c and c["organization"] not in orgs:
        errors.append(f"{i}: organization {c['organization']} is not in output/organizations.jsonld")
    for label, item in [("campaign", c)] + [("question", q) for q in c.get("questions", [])]:
        if not str(item.get("url", "")).startswith(SITE):
            errors.append(f"{i}: a {label} link must start with {SITE}")
        if item["url"] in urls:
            errors.append(f"{i}: {item['url']} is used twice")
        urls.add(item["url"])
    if not c.get("questions"):
        errors.append(f"{i}: a campaign needs at least one question")
    for q in c.get("questions", []):
        if not str(q.get("text", "")).strip():
            errors.append(f"{i}: a question has no text")

print("\n".join(errors) if errors else f"ok: {len(doc['campaigns'])} campaigns, {sum(len(c['questions']) for c in doc['campaigns'])} questions")
sys.exit(1 if errors else 0)
