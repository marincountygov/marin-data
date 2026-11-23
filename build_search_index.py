#!/usr/bin/env python3
"""Write organizations/search-index.json: one flat list of what a person can look up, for a search box.

Each entry is { "k": kind, "n": name, "a": other names, "c": a code (when it has one), "d": one plain line, "h": where it opens }.
`h` is a page of Marin Pulse, relative to "base" (or a whole address, for an organization that is not the County's). The kinds:

  Organization  the County's departments and offices (output/organizations.jsonld) and the other organizations (external-organizations.jsonld)
  Program       output/programs.jsonld
  Place         every city, district, community and building (organizations/locations.json), with their other names
  Service       output/services.jsonld, opened on its provider's page
  Person        the people who hold a post (output/people.jsonld and roles.jsonld): the name and the post, opened on the organization they serve

Nothing here that is not already public on a Marin Pulse page. Built from the files in output/; do not edit by hand.

  python3 build_search_index.py           write organizations/search-index.json
  python3 build_search_index.py --check   fail if the file is out of date
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "organizations" / "search-index.json"
BASE = "https://marincountygov.github.io/marin-pulse/"


def graph(name):
    return json.loads((ROOT / "output" / f"{name}.jsonld").read_text())["@graph"]


def slug(identifier):
    return identifier.split("/")[-1]


def clip(text, n=160):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def prop(record, property_id):
    for i in record.get("identifier", []) or []:
        if i.get("propertyID") == property_id:
            return str(i.get("value"))
    return ""


organizations = graph("organizations")
org_name = {o["@id"]: o["name"] for o in organizations}
org_page = {o["@id"]: f"organization/{slug(o['@id'])}.html" for o in organizations}
CLASS = {"department": "Department", "division": "Division", "serviceArea": "Service area", "office": "Office", "government": "County government", "authority": "Authority", "legislature": "Board", "court": "Court"}
entries = []

for o in organizations:
    kind = CLASS.get(o.get("organizationClassification"), "Organization")
    parent = org_name.get((o.get("parentOrganization") or {}).get("@id"))
    line = clip(o.get("description")) or (f"{kind} of {parent}" if parent else kind)
    entries.append({"k": "Organization", "n": o["name"], "a": sorted(o.get("alternateName", [])), "c": prop(o, "local:marin-budget-department-code"), "d": line, "h": org_page[o["@id"]]})

for o in graph("external-organizations"):
    if not o.get("url"):
        continue  # no page of ours and no address: nothing to open
    kind = CLASS.get(o.get("organizationClassification"), "Organization")
    entries.append({"k": "Organization", "n": o["name"], "a": sorted(o.get("alternateName", [])), "c": "", "d": kind, "h": o.get("url") or ""})

for p in graph("programs"):
    owner = org_name.get((p.get("administeredBy") or {}).get("@id"), "")
    entries.append({"k": "Program", "n": p["name"], "a": sorted(p.get("alternateName", [])), "c": "", "d": f"Program of {owner}" if owner else "Program", "h": f"programs/{slug(p['@id'])}.html"})

# Places: the list of places that have a page, with each one's other names.
locations = json.loads((ROOT / "organizations" / "locations.json").read_text())
kind_label = {k["key"]: k["singular"] for k in locations["kinds"]}
others = {r["@id"]: r.get("alternateName", []) for r in graph("jurisdictions") + graph("facilities")}
for loc in locations["locations"]:
    entries.append({"k": "Place", "n": loc["label"], "a": sorted(others.get(loc["id"], [])), "c": "", "d": kind_label.get(loc["kind"], str(loc["kind"]).title()), "h": f"places/{loc['code']}.html"})

for s in graph("services"):
    provider = (s.get("provider") or {}).get("@id")
    entries.append({"k": "Service", "n": s["name"], "a": sorted(s.get("alternateName", [])), "c": "", "d": f"Service of {org_name[provider]}" if provider in org_name else "Service", "h": org_page.get(provider, "")})

roles = {}
for r in graph("roles"):
    roles.setdefault((r.get("member") or {}).get("@id"), []).append(r)
for person in graph("people"):
    mine = roles.get(person["@id"], [])
    if not mine:
        continue
    where = (mine[0].get("memberOf") or {}).get("@id")
    entries.append({"k": "Person", "n": person["name"], "a": [], "c": "", "d": "; ".join(sorted({r["roleName"] for r in mine})), "h": org_page.get(where, "")})

errors = [f"{e['k']} {e['n']!r}: needs a page to open" for e in entries if not e["h"]]
errors += [f"{e['k']} {e['n']!r}: needs a name" for e in entries if not e["n"].strip()]
if errors:
    sys.exit("\n".join(errors))
entries.sort(key=lambda e: (e["k"], e["n"].casefold()))
for e in entries:  # empty fields are left out: the file stays small
    for key in ("a", "c"):
        if not e[key]:
            del e[key]
doc = {
    "schemaVersion": "1.0.0",
    "title": "What a person can look up in County of Marin data: one list for a search box",
    "generated": "Generated by build_search_index.py from output/ and organizations/locations.json. Do not edit.",
    "base": BASE,
    "entries": entries,
}
text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
if "--check" in sys.argv:
    if not OUT.exists() or OUT.read_text() != text:
        sys.exit("organizations/search-index.json is out of date. Run: python3 build_search_index.py")
    print(f"ok: organizations/search-index.json is current ({len(entries)} entries)")
else:
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(entries)} entries, {len(text) // 1024} KB")
