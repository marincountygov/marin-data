#!/usr/bin/env python3
"""Convert County of Marin organization data into schemaGov JSON-LD.

Usage:
    python3 convert_org.py AGENCIES_JSON OUT_DIR [--monitors MONITORS_YAML]

AGENCIES_JSON is the master list (marin-links/data/agencies.json).
MONITORS_YAML is optional. When given, its monitors add alternate names and
monitor ids to the matching organizations, plus a few bodies the master
list does not have.
PyYAML is needed only for that file.

Writes OUT_DIR/organizations.jsonld and OUT_DIR/jurisdictions.jsonld.
Nothing here designs a new schema: every property and value already exists
in schemaGov.
"""
import argparse
import json
import pathlib
import sys

CONTEXT = "https://schema.govfresh.com/v1/context.jsonld"
BASE = "https://marincountygov.github.io/marin-data"
ORG_ID = BASE + "/id/organization/"
JUR_ID = BASE + "/id/jurisdiction/"
URN_ORG = "urn:marin:org:"
OWN_DOMAIN_SUFFIX = "marincounty.gov"

COUNTY_SLUG = "county-of-marin"
COUNTY_JUR = JUR_ID + "us-ca-marin"

# Classification is set from what the source says, never from depth or name.
# Default: the source's own `type` (department or division).
# Overrides: (value, confidence, reason). Anything marked "low" is listed in
# FINDINGS.md as a judgment call.
CLASS_OVERRIDES = {
    "board": ("legislature", "high", "Board of Supervisors is the county legislature (rule from the brief)."),
    "grand-jury": ("department", "low", "Source says department. A grand jury is a court-appointed body; committee or court may fit better."),
    "da": ("department", "low", "Source says department. An elected office; office may fit better."),
    "sheriff": ("department", "low", "Source says department. An elected office; office may fit better."),
    "arcc": ("department", "low", "Source says department. An elected office; office may fit better."),
    "elections": ("department", "low", "Source says department. Registrar of Voters; office may fit better."),
    "public-defender": ("department", "low", "Source says department. office may fit better."),
    "county-counsel": ("department", "low", "Source says department. office may fit better."),
    "retirement": ("department", "low", "Source says department. An independent retirement board; authority may fit better."),
    "uc-extension": ("department", "low", "Source says department. A University of California program, not a county unit."),
    "tax-collector": ("department", "low", "Source says department. Its web page sits under Finance, so its public and administrative parent may differ."),
    "hr/leaves": ("division", "low", "Source says division. Reads like a function or program."),
    "hr/recruitment": ("division", "low", "Source says division. Reads like a function or program."),
    "hr/internships-and-volunteers": ("division", "low", "Source says division. Reads like a function or program."),
    "hr/risk-management": ("division", "low", "Source says division. Reads like a function or program."),
}

# Hand-written join between monitors.yaml ids and master-list ids.
# Never matched by name.
MONITOR_TO_AGENCY = {
    "marin-county-counsel": "county-counsel",
    "marin-sheriff": "sheriff",
    "marin-fire": "fire",
    "marin-cda": "cda",
    "marin-ag-weights-measures": "awm",
    "marin-assessor": "arcc",
    "marin-child-support": "css",
    "marin-county-executive": "county-executive",
    "marin-cultural-services": "cultural-services",
    "marin-da": "da",
    "marin-elections": "elections",
    "marin-finance": "finance",
    "marin-hhs": "hhs",
    "marin-hr": "hr",
    "marin-ist": "ist",
    "marin-library": "library",
    "marin-parks": "parks",
    "marin-probation": "probation",
    "marin-public-defender": "public-defender",
    "marin-public-works": "public-works",
    "marin-retirement": "retirement",
    "marin-tax-collector": "tax-collector",
    "marin-uc-extension": "uc-extension",
    "marin-supervisors": "board",
    "marin-grand-jury": "grand-jury",
}
# Division monitors follow one rule: "marin-" plus the division id with the slash
# turned into a dash (hhs/public-health -> marin-hhs-public-health).

# Bodies only in monitors.yaml that are organizations. No page URL in the source.
MONITOR_ONLY_ORGS = {
    "marin-oem": ("office-of-emergency-management", "office", "low",
                  "No parent in the data. Placed under the county government; its real administrative parent is unknown."),
    "marin-csa-6": ("county-service-area-6", "authority", "low",
                    "Board-governed service area; the data does not say what kind of body it is."),
    "marin-csa-29": ("county-service-area-29", "authority", "low",
                     "Board-governed service area; the data does not say what kind of body it is."),
}

# Monitors.yaml entries deliberately left out, with the reason.
MONITOR_LEFT_OUT = {
    "marin-transit": "Separate district with its own board and territory, not a county unit.",
    "zero-waste-marin": "Program or joint authority; the data does not say. Not placed in the county.",
    "gnoss-field-airport": "A facility, not an organization.",
    "gallinas-creek": "A place, not an organization.",
}


def slug_of(agency_id):
    return agency_id.replace("/", "-")


def prop(prop_id, value):
    return {"@type": "PropertyValue", "propertyID": prop_id, "value": value}


def org_id(slug, urn):
    return (URN_ORG if urn else ORG_ID) + slug


def own_domain(url):
    host = url.split("/")[2].lower()
    return host == OWN_DOMAIN_SUFFIX or host.endswith("." + OWN_DOMAIN_SUFFIX)


def load_monitors(path):
    import yaml  # only needed for this file
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {m["id"]: m for m in data["monitors"]}


def convert(agencies_doc, monitors):
    agencies = agencies_doc["agencies"]
    ids = [a["id"] for a in agencies]
    if len(ids) != len(set(ids)):
        raise SystemExit("Duplicate agency id in source; ids must be unique.")
    by_id = {a["id"]: a for a in agencies}
    for a in agencies:
        if a["parent"] is not None and a["parent"] not in by_id:
            raise SystemExit("Unknown parent %r for %r" % (a["parent"], a["id"]))

    agency_to_monitor = {v: k for k, v in MONITOR_TO_AGENCY.items()}
    for a in agencies:
        if "/" in a["id"] and "marin-" + slug_of(a["id"]) in monitors:
            agency_to_monitor[a["id"]] = "marin-" + slug_of(a["id"])
    notes = {"low_confidence": [], "urn": [], "left_out": [], "alt_names": 0, "monitor_only": []}

    county_name = agencies_doc["organization"]["name"]
    county_url = agencies_doc["organization"]["url"]
    county_oid = org_id(COUNTY_SLUG, False)
    county_ref = {"@id": county_oid}

    def base(oid, name, classification, url, identifiers):
        o = {
            "@id": oid,
            "@type": "GovernmentOrganization",
            "name": name,
            "organizationClassification": classification,
            "governmentLevel": "subregional",
            "identifier": identifiers,
            "areaServed": {"@id": COUNTY_JUR},
        }
        if url:
            o["url"] = url
        return o

    orgs = [base(county_oid, county_name, "government", county_url,
                 [prop("gs:local", COUNTY_SLUG)])]
    node = {county_oid: orgs[0]}
    children = {county_oid: []}  # parent @id -> [(child @id, classification)]

    def add(o, parent_oid, classification):
        o["parentOrganization"] = {"@id": parent_oid}
        orgs.append(o)
        node[o["@id"]] = o
        children.setdefault(parent_oid, []).append((o["@id"], classification))

    def oid_of(a):
        return org_id(slug_of(a["id"]), not own_domain(a["url"]))

    for a in agencies:
        urn = not own_domain(a["url"])
        oid = oid_of(a)
        if urn:
            notes["urn"].append((a["id"], oid, "own domain: " + a["url"].split("/")[2]))
        cls, conf, why = CLASS_OVERRIDES.get(
            a["id"], (a["type"], "source", "Taken from the source's own type field."))
        if conf == "low":
            notes["low_confidence"].append((a["id"], cls, why))
        ids = [prop("local:marin-links-agency-id", a["id"]),
               prop("local:marin-links-agency-code", a["code"])]
        o = base(oid, a["name"], cls, a["url"], ids)
        mid = agency_to_monitor.get(a["id"])
        if mid and mid in monitors:
            o["identifier"].append(prop("local:marin-mentions-monitor-id", mid))
            mname = monitors[mid]["name"]
            if mname != a["name"]:
                o["alternateName"] = [mname]
                notes["alt_names"] += 1
        parent = by_id[a["parent"]] if a["parent"] else None
        add(o, oid_of(parent) if parent else county_oid, cls)

    for mid, (slug, cls, conf, why) in MONITOR_ONLY_ORGS.items():
        if mid not in monitors:
            continue
        oid = org_id(slug, True)
        notes["urn"].append((slug, oid, "no public page in the source"))
        notes["low_confidence"].append((slug, cls, why))
        notes["monitor_only"].append(slug)
        o = base(oid, monitors[mid]["name"], cls, None,
                 [prop("local:marin-mentions-monitor-id", mid)])
        add(o, county_oid, cls)
    for mid, why in MONITOR_LEFT_OUT.items():
        if mid in monitors:
            notes["left_out"].append((mid, monitors[mid]["name"], why))

    # Derived views of parentOrganization. Units of administration go under
    # `department`; bodies with their own constitution under `subOrganization`.
    for parent_oid, kids in children.items():
        dept = [{"@id": k} for k, c in kids if c in ("department", "division")]
        sub = [{"@id": k} for k, c in kids if c not in ("department", "division")]
        if dept:
            node[parent_oid]["department"] = dept
        if sub:
            node[parent_oid]["subOrganization"] = sub

    jurisdictions = [
        {"@id": JUR_ID + "us", "@type": "Country", "name": "United States of America",
         "governmentLevel": "national",
         "identifier": [prop("iso3166-1-alpha2", "US"), prop("wikidata", "Q30")]},
        {"@id": JUR_ID + "us-ca", "@type": "State", "name": "California",
         "governmentLevel": "regional",
         "identifier": [prop("iso3166-2", "US-CA"), prop("wikidata", "Q99")],
         "containedInPlace": {"@id": JUR_ID + "us"}},
        {"@id": COUNTY_JUR, "@type": "AdministrativeArea", "name": county_name,
         "governmentLevel": "subregional", "url": county_url,
         "identifier": [prop("ocd-division", "ocd-division/country:us/state:ca/county:marin"),
                        {"@type": "PropertyValue",
                         "propertyID": "https://www.census.gov/library/reference/code-lists/ansi.html",
                         "name": "FIPS county code", "value": "06041"}],
         "containedInPlace": {"@id": JUR_ID + "us-ca"},
         "jurisdictionOf": [county_ref]},
    ]
    return orgs, jurisdictions, notes


def write(path, graph):
    path.write_text(json.dumps({"@context": CONTEXT, "@graph": graph}, indent=2,
                               ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("agencies")
    ap.add_argument("out_dir")
    ap.add_argument("--monitors")
    args = ap.parse_args()
    doc = json.loads(pathlib.Path(args.agencies).read_text(encoding="utf-8"))
    monitors = load_monitors(args.monitors) if args.monitors else {}
    orgs, jurs, notes = convert(doc, monitors)
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write(out / "organizations.jsonld", orgs)
    write(out / "jurisdictions.jsonld", jurs)
    print("organizations: %d, jurisdictions: %d" % (len(orgs), len(jurs)))
    print("alternate names added: %d" % notes["alt_names"])
    print("urn @ids: %d" % len(notes["urn"]))
    for t in notes["urn"]:
        print("  urn:", t)
    print("low confidence classifications: %d" % len(notes["low_confidence"]))
    for t in notes["low_confidence"]:
        print("  low:", t)
    for t in notes["left_out"]:
        print("  left out:", t)


if __name__ == "__main__":
    sys.exit(main())
