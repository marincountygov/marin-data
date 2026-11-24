#!/usr/bin/env python3
"""Build the statistics from the stored ACS source records, in schemaGov JSON-LD.

  python3 build_statistics.py          write the files
  python3 build_statistics.py --check  fail if a file is not what the build would write

Reads only files in this repo: statistics/acs-mapping.json (what to compute), statistics/source/<id>/ (the
numbers, as the Census published them) and output/jurisdictions.jsonld (the places). It never goes to the
Census, so the same inputs always write the same files.

Writes:
  output/statistics/variables.jsonld                      one StatisticalVariable per measure
  output/statistics/datasets.jsonld                       the ACS release as a Dataset
  output/areas.jsonld                                     Census areas that are not already a Marin place
  output/statistics/observations/<id>/{county,places,tracts}.jsonld
  statistics/geography-links.json                         which Marin place each Census area is, and what is left
  statistics/omitted-values.json                          every value left out, with the reason and the source cells

Rules, all from the Census published conventions:
  - A sum or difference has the square root of the sum of squared margins as its margin.
  - A share uses the Census proportion formula; where that root is negative, the ratio formula.
  - A controlled estimate (margin -555555555) has no published margin and counts as 0 inside a derived margin.
  - A margin of -222222222 or any other negative code is no margin; the estimate stays.
  - A margin of -333333333 means the median is in an open-ended interval (top- or bottom-coded). It is not a
    point estimate. Where the mapping gives the variable an openEnded cap and the source estimate is exactly the
    cap plus 1, it is written as a one-sided bound (minValue = cap) with no value and no margin of error. Any
    other open-ended value is left out and listed in omitted-values.json. Nothing is turned into zero.
  - An estimate that is a negative code is left out and listed.
  - Derived values and margins are rounded to 6 decimals only to keep the files stable; sources are not rounded.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = "https://marincountygov.github.io/marin-data"
MAPPING = json.loads((ROOT / "statistics" / "acs-mapping.json").read_text(encoding="utf-8"))
SRC = MAPPING["source"]
SOURCE_DIR = ROOT / "statistics" / "source" / SRC["id"]

CONTROLLED, OPEN_ENDED, NOT_COMPUTABLE = -555555555, -333333333, -222222222
ESTIMATE_CODES = {
    -999999999: "not available",
    -888888888: "not applicable",
    -666666666: "no sample observations or too few",
    -555555555: "estimate is controlled",
    -333333333: "median is in an open-ended interval",
    -222222222: "too few sample cases",
}


# ---- reading a cell -------------------------------------------------------------------------------------------

class Missing(Exception):
    """A value that cannot be turned into a number, with the reason."""

    def __init__(self, reason, cells=()):
        super().__init__(reason)
        self.reason = reason
        self.cells = list(cells)


class OpenEnded(Missing):
    """A median the Census publishes as 'or more' or 'or less'. The estimate is a stand-in, not a measurement."""

    def __init__(self, reason, cells, estimate):
        super().__init__(reason, cells)
        self.estimate = estimate


def number(text):
    """The number in a source cell, as an int when it has no decimal point, else None for a blank cell."""
    text = (text or "").strip()
    if text == "" or text.lower() in ("null", "none", "na"):
        return None
    try:
        return int(text) if re.fullmatch(r"-?\d+", text) else float(text)
    except ValueError:
        return None


def read_cell(tables, geo_id, cell):
    """(estimate, margin_for_publishing, margin_for_calculation) of one cell, or raise Missing.

    margin_for_publishing is None when there is no margin to publish. margin_for_calculation is 0 for a
    controlled estimate and None when the margin is not known."""
    table = tables[cell.split("_")[0]]
    row = table["rows"].get(geo_id)
    if row is None:
        raise Missing("no row for this area in the source", [cell])
    column = cell.replace("_", "_E")
    est_text, moe_text = row[table["columns"].index(column)], row[table["columns"].index(column.replace("_E", "_M"))]
    est, moe = number(est_text), number(moe_text)
    if est is None:
        raise Missing("blank in the source", [cell])
    if est in ESTIMATE_CODES:
        raise Missing(f"estimate is the code {est}: {ESTIMATE_CODES[est]}", [cell])
    if est < 0:
        raise Missing(f"estimate is the unknown negative code {est}", [cell])
    if moe == OPEN_ENDED:
        raise OpenEnded(f"margin code {OPEN_ENDED}: the value is in an open-ended interval, so it is not a point estimate", [cell], est)
    if moe is None:
        return est, None, None
    if moe == CONTROLLED:
        return est, None, 0
    if moe < 0:
        return est, None, None
    return est, moe, moe


def combine(parts):
    """Add (sign, estimate, calc margin) parts. The margin is the root of summed squares, or None if any is unknown."""
    est = sum(sign * e for sign, e, _ in parts)
    if any(m is None for _, _, m in parts):
        return est, None
    return est, math.sqrt(sum(m * m for _, _, m in parts))


def share(num, den):
    """(percent, margin) of a numerator that is part of the denominator. Raise Missing for a zero denominator."""
    (ne, nm), (de, dm) = num, den
    if de == 0:
        raise Missing("the denominator is 0, so there is no share")
    p = ne / de
    if nm is None or dm is None:
        return 100 * p, None
    inside = nm * nm - p * p * dm * dm
    if inside < 0:
        inside = nm * nm + p * p * dm * dm
    return 100 * p, 100 * math.sqrt(inside) / de


def tidy(x):
    """Whole numbers stay whole; other numbers keep 6 decimals."""
    if isinstance(x, int):
        return x
    return int(x) if float(x).is_integer() else round(x, 6)


def value_of(variable, variables, tables, geo_id):
    """(value, margin or None, [cells used]) for one variable at one area, or raise Missing."""
    calc = variable["calculation"]
    if calc["type"] == "direct":
        e, m, calc_m = read_cell(tables, geo_id, calc["cell"])
        return e, m, [calc["cell"]]
    if calc["type"] == "sum":
        used = list(calc["cells"]) + list(calc.get("subtract", []))
        parts = []
        for sign, names in ((1, calc["cells"]), (-1, calc.get("subtract", []))):
            for c in names:
                e, _, calc_m = read_cell(tables, geo_id, c)
                parts.append((sign, e, calc_m))
        e, m = combine(parts)
        if e < 0:
            raise Missing("the difference is negative", used)
        return tidy(e), (None if m is None else tidy(round(m, 6))), used
    num_parts = [(1, *read_cell(tables, geo_id, c)[::2]) for c in calc["numerator"]["cells"]]
    num = combine(num_parts)
    den_variable = variables[calc["denominator"]]
    den_calc = den_variable["calculation"]
    den_parts = [(1, *read_cell(tables, geo_id, c)[::2]) for c in den_calc.get("cells", [den_calc.get("cell")]) if c]
    den_parts += [(-1, *read_cell(tables, geo_id, c)[::2]) for c in den_calc.get("subtract", [])]
    den = combine(den_parts)
    used = list(calc["numerator"]["cells"]) + [c for c in den_calc.get("cells", [den_calc.get("cell")]) if c] + list(den_calc.get("subtract", []))
    try:
        pct, moe = share(num, den)
    except Missing as err:
        raise Missing(err.reason, used)
    return tidy(round(pct, 6)), (None if moe is None else tidy(round(moe, 6))), used


# ---- records ---------------------------------------------------------------------------------------------------

def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def dataset_id():
    return f"{BASE}/id/dataset/{SRC['id']}"


def variable_id(vid):
    return f"{BASE}/id/statistical-variable/{vid}"


def load_inputs():
    tables = {}
    for path in sorted(SOURCE_DIR.glob("b*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        tables[data["table"]] = data
    geographies = json.loads((SOURCE_DIR / "geographies.json").read_text(encoding="utf-8"))
    juris = json.loads((ROOT / "output" / "jurisdictions.jsonld").read_text(encoding="utf-8"))
    return tables, geographies, juris


def ident(record, scheme):
    return [i["value"] for i in record.get("identifier", []) if i.get("propertyID") == scheme]


def tract_label(name):
    return name.replace(", California", "")


def resolve_areas(geographies, juris):
    """For each Census area: the place it is. Existing Marin places are matched by their census-geoid
    identifier (set by hand in jurisdictions.jsonld); anything else becomes a new area record."""
    by_geoid = {}
    for record in juris["@graph"]:
        for g in ident(record, "census-geoid"):
            by_geoid[g] = record
    areas, new = [], []
    for g in geographies:
        record = by_geoid.get(g["geoid"])
        if record:
            areas.append({**g, "id": record["@id"], "label": record["name"], "code": ident(record, "gs:local")[0], "existing": True})
            continue
        if g["kind"] == "tract":
            label = tract_label(g["name"])
            code = "census-tract-" + slug(re.sub(r"^Census Tract ", "", label.split(",")[0]))
            area_type = "statistical-area"
        elif g["kind"] == "place":
            label = re.sub(r", California$", "", g["name"])
            code = slug(label)
            area_type = "designated-place"
        else:
            sys.exit(f"{g['name']} ({g['geoid']}) has no census-geoid on a place in output/jurisdictions.jsonld")
        area = {**g, "id": f"{BASE}/id/area/{code}", "label": label, "code": code, "existing": False}
        areas.append(area)
        new.append({
            "@id": area["id"], "@type": "Place", "name": label, "areaType": area_type,
            "identifier": [
                {"@type": "PropertyValue", "propertyID": "census-geoid", "value": g["geoid"]},
                {"@type": "PropertyValue", "propertyID": "gs:local", "value": code},
            ],
            "containedInPlace": {"@id": f"{BASE}/id/jurisdiction/us-ca-marin", "name": "Marin County"},
        })
    return areas, new


def variable_records():
    out = []
    for v in MAPPING["variables"]:
        r = {"@id": variable_id(v["id"]), "@type": "StatisticalVariable", "name": v["name"], "description": v["description"]}
        if "populationType" in v:
            r["populationType"] = v["populationType"]
        r["statType"] = v["statType"]
        if v["calculation"]["type"] == "share":
            den = next(x for x in MAPPING["variables"] if x["id"] == v["calculation"]["denominator"])
            r["measurementDenominator"] = {"@id": variable_id(den["id"]), "name": den["name"]}
        if "dimension" in v:
            r["additionalProperty"] = [{"@type": "PropertyValue", **v["dimension"]}]
        out.append(r)
    return out


def dataset_record():
    base = SRC["base"]
    return {
        "@id": dataset_id(), "@type": "Dataset", "name": SRC["name"],
        "description": (f"{SRC['program']} {SRC['estimate']} estimates for Marin County, its places and its census tracts. "
                        "Each value is an estimate from a sample survey and carries a margin of error at the 90 percent confidence level where the Census publishes one."),
        "publisher": {"@id": f"{BASE}/id/organization/us-census-bureau", "name": SRC["publisher"]},
        "spatialCoverage": {"@id": f"{BASE}/id/jurisdiction/us-ca-marin", "name": "Marin County"},
        "temporalCoverage": SRC["observationPeriod"],
        "license": "https://www.usa.gov/publicdomain/label/1.0/",
        "version": str(SRC["vintage"]),
        "url": "https://www.census.gov/programs-surveys/acs",
        "distribution": [{
            "@type": "DataDownload", "name": "Table-based summary file, 5-year",
            "contentUrl": f"{base}/data/5YRData/", "encodingFormat": "text/plain",
        }],
    }


def build_observations(areas, tables):
    variables = {v["id"]: v for v in MAPPING["variables"]}
    observations = {"county": [], "places": [], "tracts": []}
    omitted, counts = [], {"with-moe": 0, "without-moe": 0, "bound-only": 0}
    for area in sorted(areas, key=lambda a: ({"county": 0, "place": 1, "tract": 2}[a["kind"]], a["label"] if a["kind"] == "place" else a["geoid"])):
        group = {"county": "county", "place": "places", "tract": "tracts"}[area["kind"]]
        for v in MAPPING["variables"]:
            try:
                value, moe, used = value_of(v, variables, tables, area["geoId"])
            except Missing as err:
                cap = v.get("openEnded")
                if isinstance(err, OpenEnded) and cap and v["calculation"]["type"] == "direct" and err.estimate == cap["cap"] + 1:
                    observations[group].append({
                        "@id": f"{BASE}/id/observation/{area['code']}/{v['id']}/{SRC['observationPeriod'].replace('/', '-')}",
                        "@type": "Observation",
                        "observationAbout": {"@id": area["id"], "name": area["label"]},
                        "variableMeasured": {"@id": variable_id(v["id"]), "name": v["name"]},
                        cap["bound"]: cap["cap"],
                        "unitText": v["unit"],
                        "observationPeriod": SRC["observationPeriod"],
                        "sourceDataset": dataset_id(),
                        "measurementMethod": "survey estimate",
                    })
                    counts["bound-only"] += 1
                    continue
                omitted.append({
                    "area": area["id"], "geoid": area["geoid"], "name": area["label"], "variable": v["id"],
                    "reason": err.reason,
                    "sourceCells": {c: _source_cells(tables, area["geoId"], c) for c in err.cells or _cells_of(v, variables)},
                })
                continue
            record = {
                "@id": f"{BASE}/id/observation/{area['code']}/{v['id']}/{SRC['observationPeriod'].replace('/', '-')}",
                "@type": "Observation",
                "observationAbout": {"@id": area["id"], "name": area["label"]},
                "variableMeasured": {"@id": variable_id(v["id"]), "name": v["name"]},
                "value": value,
                "unitText": v["unit"],
                "observationPeriod": SRC["observationPeriod"],
                "sourceDataset": dataset_id(),
            }
            if moe is not None:
                record["marginOfError"] = {"@type": "QuantitativeValue", "value": moe, "additionalProperty": [
                    {"@type": "PropertyValue", "propertyID": "confidenceLevel", "value": SRC["confidenceLevel"]}]}
                counts["with-moe"] += 1
            else:
                counts["without-moe"] += 1
            record["measurementMethod"] = "survey estimate" if v["calculation"]["type"] == "direct" else "derived from survey estimates"
            observations[group].append(record)
    return observations, omitted, counts


def _cells_of(v, variables):
    calc = v["calculation"]
    if calc["type"] == "direct":
        return [calc["cell"]]
    if calc["type"] == "sum":
        return calc["cells"] + calc.get("subtract", [])
    den = variables[calc["denominator"]]["calculation"]
    return calc["numerator"]["cells"] + [den.get("cell")] * bool(den.get("cell")) + den.get("cells", []) + den.get("subtract", [])


def _source_cells(tables, geo_id, cell):
    table = tables[cell.split("_")[0]]
    row = table["rows"].get(geo_id)
    if row is None:
        return None
    column = cell.replace("_", "_E")
    return {"estimate": row[table["columns"].index(column)], "margin": row[table["columns"].index(column.replace("_E", "_M"))]}


def review_candidates(juris, new_cdps):
    """Marin places whose name is a part of a combined Census place name. Only a name match: no boundary
    is stored here, so nothing about containment or overlap is claimed."""
    names = [r["name"] for r in juris["@graph"] if r["@type"] != "City" and not ident(r, "local:marin-supervisorial-district")
             and not ident(r, "census-geoid") and r["name"] != "Marin County"]
    out = []
    for area in new_cdps:
        parts = [p.replace(" CDP", "") for p in area["label"].split("-")]
        hits = [n for n in names if any(n == p or n.split()[0] == p for p in parts)]
        out.append({"censusPlace": area["label"], "geoid": area["geoid"], "marinPlacesWithMatchingName": hits})
    return out


def geography_links(areas, juris, new):
    linked = [{"geoid": a["geoid"], "census": a["name"], "marinPlace": a["id"], "name": a["label"], "match": "census-geoid identifier on the place"} for a in areas if a["existing"]]
    new_areas = [{"geoid": a["geoid"], "name": a["label"], "id": a["id"], "kind": a["kind"]} for a in areas if not a["existing"]]
    cdps = [a for a in areas if not a["existing"] and a["kind"] == "place"]
    linked_ids = {a["id"] for a in areas if a["existing"]}
    not_linked = sorted(r["name"] for r in juris["@graph"]
                        if r["@id"] not in linked_ids and not ident(r, "local:marin-supervisorial-district") and r["name"] != "Marin County")
    return {
        "note": "Generated by build_statistics.py. A Marin place is linked only where its name is exactly a Census place name. Nothing here claims that a Census area and a Marin community cover the same land.",
        "source": SRC["id"],
        "counts": {"censusAreas": len(areas), "linkedToExistingMarinPlace": len(linked), "newAreas": len(new_areas),
                   "marinPlacesWithoutCensusAreaOrObservations": len(not_linked)},
        "linked": linked,
        "newAreas": [n for n in new_areas if n["kind"] == "place"] + [{"tracts": sum(1 for n in new_areas if n["kind"] == "tract"), "note": "Census tracts are new areas, contained in Marin County"}],
        "needsReview": review_candidates(juris, cdps),
        "marinPlacesWithoutStatistics": not_linked,
    }


def jsonld(graph, context):
    return json.dumps({"@context": context, "@graph": graph}, indent=2, ensure_ascii=False) + "\n"


def build():
    tables, geographies, juris = load_inputs()
    context = juris["@context"]
    areas, new = resolve_areas(geographies, juris)
    observations, omitted, counts = build_observations(areas, tables)
    files = {
        "output/statistics/variables.jsonld": jsonld(variable_records(), context),
        "output/statistics/datasets.jsonld": jsonld([dataset_record()], context),
        "output/areas.jsonld": jsonld(new, context),
        "statistics/geography-links.json": json.dumps(geography_links(areas, juris, new), indent=2, ensure_ascii=False) + "\n",
        "statistics/omitted-values.json": json.dumps({
            "note": "Generated by build_statistics.py. Each value here was left out, not set to zero. sourceCells are the Census values exactly as published.",
            "source": SRC["id"], "count": len(omitted), "omitted": omitted}, indent=2, ensure_ascii=False) + "\n",
    }
    for group, graph in observations.items():
        files[f"output/statistics/observations/{SRC['id']}/{group}.jsonld"] = jsonld(graph, context)
    return files, {"observations": sum(len(g) for g in observations.values()), "omitted": len(omitted), **counts,
                   "areas": len(areas), "newAreas": len(new)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if a file is not current")
    args = parser.parse_args()
    files, stats = build()
    stale = []
    for rel, text in files.items():
        path = ROOT / rel
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    if stale:
        sys.exit("Out of date: " + ", ".join(stale) + "\nRun: python3 build_statistics.py")
    print(("ok: " if args.check else "wrote: ") + ", ".join(f"{k} {v}" for k, v in stats.items()))
