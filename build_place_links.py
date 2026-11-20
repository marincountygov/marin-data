#!/usr/bin/env python3
"""Write organizations/places.json: which place each Marin Mentions monitor is about.

The link lives on the jurisdiction, as the identifier local:marin-mentions-monitor-id in
output/jurisdictions.jsonld. This file is generated from it for apps that cannot read JSON-LD
easily. marin-mentions copies it. Do not edit it by hand.

districts says which supervisorial districts a place is in: each is the district's monitor id, with relation
within (the whole place is in that district) or overlaps (the place is partly in it, so it is in more than
one). It comes from geoWithin and geoOverlaps on the place. A district has none.

kind is district (a supervisorial district), city (a city or town) or community (an
unincorporated community). The kinds and what apps call them are in organizations/place-kinds.json.
code is the record's own code (its gs:local identifier, see place_lib.py), which is not tied to Mentions.
label is the name an app shows for the place: the place's name, except a district, which is District N.
alternateNames are the other names the record goes by (City of Novato, Tam Valley), and the other keys are search hints (see place_lib.py). A facility lists the facilities inside it as parts, and a district lists its supervisor as people and the areas in it as parts. Marin Mentions watches for all of them. Facilities (output/facilities.jsonld) are Places too, so they are listed
here as well, under facilities, with their schemaGov type.

  python3 build_place_links.py           write organizations/places.json
  python3 build_place_links.py --check   fail if the file is out of date
"""
import json
import sys
from pathlib import Path

import place_lib as lib

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "organizations" / "places.json"
graph = json.loads((ROOT / "output" / "jurisdictions.jsonld").read_text())["@graph"]
not_places = json.loads((ROOT / "organizations" / "monitors-not-places.json").read_text())["monitors"]
facility_graph = json.loads((ROOT / "output" / "facilities.jsonld").read_text())["@graph"]
kinds_doc = json.loads((ROOT / "organizations" / "place-kinds.json").read_text())
kinds = kinds_doc["kinds"]
labels = {v: k for k, v in json.loads((ROOT / "organizations" / "place-aliases.json").read_text())["labels"].items()}
org_monitors = {m["monitorId"] for m in json.loads((ROOT / "organizations" / "monitors.json").read_text())["monitors"]}


ident = lib.ident
kind = lib.kind_of


monitor_of = {}
for o in graph:
    for v in ident(o, "local:marin-mentions-monitor-id"):
        monitor_of[o["@id"]] = v


def districts(o):
    found = []
    for key, relation in (("geoWithin", "within"), ("geoOverlaps", "overlaps")):
        refs = o.get(key) or []
        for ref in refs if isinstance(refs, list) else [refs]:
            target = next((g for g in graph if g["@id"] == ref["@id"]), None)
            if not target or not ident(target, "local:marin-supervisorial-district") or ref["@id"] not in monitor_of:
                sys.exit(f"{o['name']}: {key} must point at a supervisorial district that has a monitor")
            found.append({"monitorId": monitor_of[ref["@id"]], "relation": relation})
    if o.get("geoWithin") and o.get("geoOverlaps"):
        sys.exit(f"{o['name']}: a place is within one district or overlaps several, not both")
    if len([d for d in found if d["relation"] == "within"]) > 1:
        sys.exit(f"{o['name']}: within can name only one district")
    return sorted(found, key=lambda d: d["monitorId"])


roles = lib.graph("roles")
posts = {x["@id"]: x for x in lib.graph("posts")}
people = {x["@id"]: x for x in lib.graph("people")}


def supervisors(district):
    """The names of the people whose post represents this district."""
    names = []
    for role in roles:
        post = posts.get((role.get("post") or {}).get("@id"))
        if post and (post.get("representsJurisdiction") or {}).get("@id") == district["@id"]:
            names.append(people[role["member"]["@id"]]["name"])
    return sorted(names)


def areas_of(district):
    """The places in a district that Marin Mentions does not watch by themselves (an area, a valley): their names."""
    found = []
    for o in graph:
        refs = [r["@id"] for key in ("geoWithin", "geoOverlaps") for r in (o.get(key) if isinstance(o.get(key), list) else [o.get(key)] if o.get(key) else [])]
        if district["@id"] in refs and o["@id"] not in monitor_of:
            found.append({"name": o["name"], **lib.search_of(o)})
    return sorted(found, key=lambda a: a["name"])


rows = []
for o in graph:
    for monitor_id in ident(o, "local:marin-mentions-monitor-id"):
        rows.append({
            "monitorId": monitor_id,
            "code": lib.code_of(o),
            "jurisdiction": o["@id"],
            "name": o["name"],
            "label": labels[o["@id"]],
            **lib.search_of(o),
            "kind": kind(o),
            "governmentLevel": o["governmentLevel"],
            **({"districts": districts(o)} if districts(o) else {}),
            **({"people": supervisors(o)} if kind(o) == "district" and supervisors(o) else {}),
            **({"parts": areas_of(o)} if kind(o) == "district" and areas_of(o) else {}),
        })
rows.sort(key=lambda r: r["monitorId"])
facilities = sorted(
    ({"monitorId": m, "code": lib.code_of(o), "facility": o["@id"], "name": o["name"], "label": o["name"], "kind": "facility", "type": o["@type"],
      **lib.search_of(o), **({"parts": lib.parts_of(o, facility_graph)} if lib.parts_of(o, facility_graph) else {})}
     for o in facility_graph for m in ident(o, "local:marin-mentions-monitor-id")),
    key=lambda r: r["monitorId"],
)
known = {k["key"] for k in kinds}
unknown = sorted({r["kind"] for r in rows + facilities} - known)
if unknown:
    sys.exit(f"kinds not in organizations/place-kinds.json: {unknown}")
ids = [r["monitorId"] for r in rows] + [r["monitorId"] for r in facilities]
if len(ids) != len(set(ids)):
    sys.exit("a monitor id is on two jurisdictions or facilities")
both = set(ids) & {n["monitorId"] for n in not_places}
if both:
    sys.exit(f"monitor ids both linked to a jurisdiction and listed as not places: {sorted(both)}")
clash = set(ids) & org_monitors
if clash:
    sys.exit(f"monitor ids linked to both an organization and a jurisdiction: {sorted(clash)}")
doc = {
    "schemaVersion": "1.0.0",
    "title": "Marin Mentions monitors and the places and facilities they are about",
    "generated": "Generated by build_place_links.py from output/jurisdictions.jsonld and output/facilities.jsonld. Do not edit.",
    "kinds": kinds,
    "facets": kinds_doc["facets"],
    "places": rows,
    "facilities": facilities,
    "notPlaces": not_places,
}
text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
if "--check" in sys.argv:
    if not OUT.exists() or OUT.read_text() != text:
        sys.exit("organizations/places.json is out of date. Run: python3 build_place_links.py")
    print(f"ok: organizations/places.json is current ({len(rows)} places, {len(facilities)} facilities)")
else:
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} places, {len(facilities)} facilities, {len(not_places)} not places")
