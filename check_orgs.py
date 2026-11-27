#!/usr/bin/env python3
"""Check that organizations/agencies.json and output/organizations.jsonld agree.

agencies.json is the master list of County agencies (ids, codes, order, status). organizations.jsonld holds the
full record for each body and links to the list through the identifier local:marin-links-agency-id.

Fails if an agency has no matching organization, or if id, code, name, parent or url disagree.
A budget short link kept in sameAs is allowed.

  python3 check_orgs.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
agencies = json.loads((ROOT / "organizations" / "agencies.json").read_text())["agencies"]
graph = json.loads((ROOT / "output" / "organizations.jsonld").read_text())["@graph"]

LINKS_ID, LINKS_CODE = "local:marin-links-agency-id", "local:marin-links-agency-code"


def ident(o, prop):
    return [i["value"] for i in o.get("identifier", []) if i.get("propertyID") == prop]


by_agency = {}
errors = []
for o in graph:
    for v in ident(o, LINKS_ID):
        if v in by_agency:
            errors.append(f"{v}: two organizations carry this agency id")
        by_agency[v] = o

ids = [a["id"] for a in agencies]
if len(ids) != len(set(ids)):
    errors.append("agencies.json has a duplicate id")

for a in agencies:
    o = by_agency.get(a["id"])
    if not o:
        errors.append(f"{a['id']}: no organization carries this agency id")
        continue
    if o["name"] != a["name"]:
        errors.append(f"{a['id']}: name {a['name']!r} in the list, {o['name']!r} in organizations.jsonld")
    if ident(o, LINKS_CODE) != [a["code"]]:
        errors.append(f"{a['id']}: code {a['code']!r} in the list, {ident(o, LINKS_CODE)} in organizations.jsonld")
    if (o.get("url") or "") != a["url"]:
        errors.append(f"{a['id']}: url {a['url']} in the list, {o.get('url')} in organizations.jsonld")
    parent = (o.get("parentOrganization") or {}).get("@id", "")
    if a["parent"]:
        want = by_agency.get(a["parent"])
        if not want or parent != want["@id"]:
            errors.append(f"{a['id']}: parent {a['parent']} in the list, {parent or 'none'} in organizations.jsonld")

print("\n".join(errors) if errors else f"ok: {len(agencies)} agencies match organizations.jsonld")
sys.exit(1 if errors else 0)
