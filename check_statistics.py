#!/usr/bin/env python3
"""Check the statistics files against each other and against the stored source.

  python3 check_statistics.py

Fails if:
  - the mapping names a cell that is not in the stored source, or a variable twice, or a missing denominator;
  - an observation points at a variable, area or dataset that does not exist, or twice at the same pair;
  - an observation has a margin without the 90 percent confidence level, a negative margin, or a share over 100;
  - a generated file is not what build_statistics.py would write from the stored source (so every value matches
    the source cells it was computed from);
  - a Census area or code is claimed by two records, or a GEOID sits on two places;
  - a key, token or password appears in the mapping, the source records or the generated files.
The schemaGov shape check is separate: python3 check_schemagov.py PATH_TO_SCHEMAGOV_CLONE.
"""
import json
import re
import sys
from pathlib import Path

import build_statistics as b

ROOT = Path(__file__).resolve().parent
errors = []


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


tables, geographies, juris = b.load_inputs()
variables = {v["id"]: v for v in b.MAPPING["variables"]}

# mapping
if len(variables) != len(b.MAPPING["variables"]):
    errors.append("mapping: a variable id is used twice")
for v in b.MAPPING["variables"]:
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", v["id"]):
        errors.append(f"mapping: {v['id']!r} must be lowercase words joined by hyphens, never a Census code")
    for cell in b._cells_of(v, variables):
        table = tables.get(cell.split("_")[0])
        if not table or cell.replace("_", "_E") not in table["columns"]:
            errors.append(f"mapping: {v['id']} uses {cell}, which is not in the stored source")
    if v["calculation"]["type"] == "share" and variables.get(v["calculation"]["denominator"], {}).get("statType") != "count":
        errors.append(f"mapping: {v['id']} needs a denominator variable that is a count")

# areas and codes
files, _ = b.build()
for rel, text in files.items():
    if not (ROOT / rel).is_file() or (ROOT / rel).read_text(encoding="utf-8") != text:
        errors.append(f"{rel} is not current: run python3 build_statistics.py")
areas_graph = json.loads(files["output/areas.jsonld"])["@graph"]
codes, geoids = {}, {}
for record in juris["@graph"] + areas_graph:
    for g in b.ident(record, "census-geoid"):
        if g in geoids:
            errors.append(f"GEOID {g} is on both {geoids[g]} and {record['name']}")
        geoids[g] = record["name"]
for record in areas_graph:
    code = b.ident(record, "gs:local")[0]
    if code in codes or code in {c for r in juris["@graph"] for c in b.ident(r, "gs:local")}:
        errors.append(f"area code {code!r} is not unique")
    codes[code] = record["name"]
    if "jurisdictionOf" in record or record.get("areaType") not in ("statistical-area", "designated-place"):
        errors.append(f"area {record['name']}: must be a Place with an areaType and no jurisdictionOf")
for g in geographies:
    if g["geoid"] not in geoids and g["kind"] != "county" and g["geoid"] not in {b.ident(r, "census-geoid")[0] for r in areas_graph}:
        errors.append(f"Census area {g['name']} is not linked to a place or a new area")

# observations
known_ids = {r["@id"] for r in juris["@graph"] + areas_graph}
known_variables = {b.variable_id(v) for v in variables}
seen, total = set(), 0
for rel in sorted(files):
    if "/observations/" not in rel:
        continue
    for o in json.loads(files[rel])["@graph"]:
        total += 1
        where = o["@id"]
        pair = (o["observationAbout"]["@id"], o["variableMeasured"]["@id"], o.get("observationPeriod"))
        if pair in seen:
            errors.append(f"{where}: another observation has the same area, variable and period")
        seen.add(pair)
        if o["observationAbout"]["@id"] not in known_ids:
            errors.append(f"{where}: its area does not exist")
        if o["variableMeasured"]["@id"] not in known_variables:
            errors.append(f"{where}: its variable does not exist")
        if o["sourceDataset"] != b.dataset_id():
            errors.append(f"{where}: sourceDataset is not the ACS dataset")
        if "observationDate" in o:
            errors.append(f"{where}: a 5-year estimate uses observationPeriod, not observationDate")
        moe = o.get("marginOfError")
        if moe:
            levels = [p["value"] for p in moe.get("additionalProperty", []) if p["propertyID"] == "confidenceLevel"]
            if levels != [b.SRC["confidenceLevel"]]:
                errors.append(f"{where}: the margin of error needs confidenceLevel {b.SRC['confidenceLevel']}")
            if moe["value"] < 0:
                errors.append(f"{where}: negative margin of error")
        if "value" not in o:
            if "marginOfError" in o or not ("minValue" in o or "maxValue" in o):
                errors.append(f"{where}: a bound-only observation needs minValue or maxValue, and no value or margin of error")
            continue
        if o["unitText"] == "percent" and not 0 <= o["value"] <= 100:
            errors.append(f"{where}: a percent outside 0 to 100")
        if o["value"] < 0:
            errors.append(f"{where}: negative value (a Census code leaked through?)")

# nothing is missing without a record of it: every area has every variable either observed or listed as omitted
omitted = {(x["area"], x["variable"]) for x in load("statistics/omitted-values.json")["omitted"]}
for a in b.resolve_areas(geographies, juris)[0]:
    for vid in variables:
        have = (a["id"], b.variable_id(vid), b.SRC["observationPeriod"]) in seen
        if have == ((a["id"], vid) in omitted):
            errors.append(f"{a['label']} / {vid}: must be exactly one of observed or listed in omitted-values.json")

# no credentials
for path in [ROOT / "statistics" / "acs-mapping.json", *sorted(b.SOURCE_DIR.glob("*.json")), *(ROOT / r for r in files)]:
    text = path.read_text(encoding="utf-8")
    if re.search(r"(api[_-]?key|CENSUS_API_KEY|[?&]key=|password|secret|token)", text, re.I):
        errors.append(f"{path.relative_to(ROOT)}: looks like it holds a credential")

print("\n".join(errors[:40]) if errors else f"ok: {total} observations, {len(areas_graph)} new areas, {len(geoids)} GEOIDs, every value traced")
sys.exit(1 if errors else 0)
