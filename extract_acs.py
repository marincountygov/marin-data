#!/usr/bin/env python3
"""Retrieve the ACS 5-year files and keep only the Marin rows the mapping needs.

  python3 extract_acs.py download DIR          fetch the Census files into DIR (skips files already there)
  python3 extract_acs.py extract DIR [--retrieved YYYY-MM-DD]
                                               write statistics/source/<source id>/ from the files in DIR

This is the only step that knows where the numbers come from. It needs no Census API key: it reads the
published table-based summary files. To move to the API later, replace this script; the files it writes are
the whole interface to the rest of the build (build_statistics.py reads only statistics/source/).

The files it writes keep each source value exactly as the Census published it, as text, with the sentinel
codes (-555555555 and the like) untouched. Nothing is rounded, filled in or dropped here except rows for
geographies outside Marin and cells the mapping does not use.
"""
import argparse
import csv
import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAPPING = json.loads((ROOT / "statistics" / "acs-mapping.json").read_text(encoding="utf-8"))
SRC = MAPPING["source"]
OUT = ROOT / "statistics" / "source" / SRC["id"]
UA = "marin-data-extract/1.0"


def cells_by_table():
    """{table: [cell ids in mapping order, no repeats]} for every cell the mapping names."""
    found = {}

    def add(cells):
        for c in cells:
            t = c.split("_")[0]
            if c not in found.setdefault(t, []):
                found[t].append(c)

    for v in MAPPING["variables"]:
        calc = v["calculation"]
        if calc["type"] == "direct":
            add([calc["cell"]])
        elif calc["type"] == "sum":
            add(calc["cells"] + calc.get("subtract", []))
        else:
            add(calc["numerator"]["cells"] + calc["numerator"].get("subtract", []))
    return {t: sorted(c) for t, c in sorted(found.items())}


def files_needed():
    """{local name: url} for every file the extract reads."""
    base = SRC["base"]
    urls = {
        Path(SRC["geographyFile"]).name: f"{base}/{SRC['geographyFile']}",
        Path(SRC["shellsFile"]).name: f"{base}/{SRC['shellsFile']}",
        Path(SRC["placesByCountyUrl"]).name: SRC["placesByCountyUrl"],
    }
    for t in cells_by_table():
        name = Path(SRC["tableFile"].format(table=t.lower())).name
        urls[name] = f"{base}/{SRC['tableFile'].format(table=t.lower())}"
    return urls


def download(folder):
    """Fetch each file with curl, which uses the computer's own certificate list."""
    folder.mkdir(parents=True, exist_ok=True)
    for name, url in files_needed().items():
        target = folder / name
        if target.exists():
            print(f"have {name}")
            continue
        print(f"fetching {url}")
        partial = folder / (name + ".part")
        subprocess.run(["curl", "-fsSL", "--retry", "3", "-A", UA, "-o", str(partial), url], check=True)
        partial.rename(target)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def read_pipe(path):
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        yield from csv.DictReader(f, delimiter="|")


def marin_geographies(folder):
    """Marin's county, census tracts and places, from the Census geography file."""
    by_county = {}
    for row in read_pipe(folder / Path(SRC["placesByCountyUrl"]).name):
        if row["COUNTYFP"] == SRC["county"]:
            by_county[row["PLACEFP"]] = row
    found = []
    for g in read_pipe(folder / Path(SRC["geographyFile"]).name):
        if g["STUSAB"] != "CA" or g["COMPONENT"] != "00":
            continue
        level = g["SUMLEVEL"]
        geoid = g["GEO_ID"].split("US", 1)[1]
        if level == "050" and g["COUNTY"] == SRC["county"]:
            kind = "county"
        elif level == "140" and g["COUNTY"] == SRC["county"]:
            kind = "tract"
        elif level == "160" and g["PLACE"] in by_county:
            kind = "place"
        else:
            continue
        record = {"geoId": g["GEO_ID"], "geoid": geoid, "kind": kind, "name": g["NAME"]}
        if kind == "place":
            record["placeType"] = by_county[g["PLACE"]]["TYPE"].lower()
        found.append(record)
    return sorted(found, key=lambda r: (r["kind"], r["geoid"]))


def extract(folder, retrieved):
    geos = marin_geographies(folder)
    keep = {g["geoId"] for g in geos}
    OUT.mkdir(parents=True, exist_ok=True)
    tables = cells_by_table()
    shell_rows = {}
    with open(folder / Path(SRC["shellsFile"]).name, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter="|")
        header = next(reader)
        i_id = header.index("Unique ID")
        i_label = header.index("Label")
        for row in reader:
            shell_rows[row[i_id]] = row[i_label]
    manifest_files = []
    for table, cells in tables.items():
        name = Path(SRC["tableFile"].format(table=table.lower())).name
        path = folder / name
        columns = [f"{c.split('_')[0]}_{kind}{c.split('_')[1]}" for c in cells for kind in ("E", "M")]
        rows = {}
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="|")
            missing = [c for c in columns if c not in reader.fieldnames]
            if missing:
                sys.exit(f"{name} has no column(s) {missing}")
            for row in reader:
                if row["GEO_ID"] in keep:
                    rows[row["GEO_ID"]] = [row[c] for c in columns]
        absent = sorted(keep - set(rows))
        if absent:
            print(f"note: {table} has no row for {len(absent)} geographies (for example {absent[0]})")
        data = {
            "table": table,
            "columns": columns,
            "labels": {c: shell_rows.get(c, "") for c in cells},
            "rows": dict(sorted(rows.items())),
        }
        (OUT / f"{table.lower()}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        manifest_files.append({"name": name, "table": table, "bytes": path.stat().st_size, "sha256": sha256(path)})
        print(f"{table}: {len(rows)} rows")
    (OUT / "geographies.json").write_text(json.dumps(geos, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    urls = files_needed()
    for name in (Path(SRC["geographyFile"]).name, Path(SRC["shellsFile"]).name, Path(SRC["placesByCountyUrl"]).name):
        manifest_files.append({"name": name, "bytes": (folder / name).stat().st_size, "sha256": sha256(folder / name)})
    for m in manifest_files:
        m["url"] = urls[m["name"]]
    manifest = {
        "source": SRC["id"],
        "publisher": SRC["publisher"],
        "dataset": SRC["name"],
        "retrieved": retrieved,
        "method": "Census table-based summary file download; no API key",
        "files": sorted(manifest_files, key=lambda m: m["name"]),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(f"{len(geos)} geographies; wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download").add_argument("folder", type=Path)
    e = sub.add_parser("extract")
    e.add_argument("folder", type=Path)
    e.add_argument("--retrieved", default=datetime.date.today().isoformat())
    args = parser.parse_args()
    if args.command == "download":
        download(args.folder)
    else:
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", args.retrieved):
            sys.exit("--retrieved must look like 2026-11-24")
        extract(args.folder, args.retrieved)
