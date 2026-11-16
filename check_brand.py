#!/usr/bin/env python3
"""Check the brand data in brand/<slug>/: brand.json and assets/.

For each brand, every file brand.json names under assets/ must exist, every file under assets/ must be named,
and the folder must hold nothing else. The schema check stays in marin-brand (scripts/validate-brand.js),
which runs on its copy.

  python3 check_brand.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BRANDS = ROOT / "brand"
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


errors, slugs = [], sorted(d.name for d in BRANDS.iterdir() if d.is_dir())
if not slugs:
    errors.append("brand/ has no brands")
for slug in slugs:
    folder = BRANDS / slug
    if not SLUG.match(slug):
        errors.append(f"{slug}: folder name is not a lowercase slug")
    try:
        data = json.loads((folder / "brand.json").read_text())
    except (OSError, ValueError) as e:
        errors.append(f"{slug}: brand.json cannot be read ({e})")
        continue
    refs = {s for s in strings(data) if s.startswith("assets/")}
    files = {f.relative_to(folder).as_posix() for f in (folder / "assets").rglob("*") if f.is_file() and f.name != ".DS_Store"}
    for r in sorted(refs - files):
        errors.append(f"{slug}: brand.json names {r}, which does not exist")
    for f in sorted(files - refs):
        errors.append(f"{slug}: {f} is not named in brand.json")
    other = sorted(p.name for p in folder.iterdir() if p.name not in ("brand.json", "assets", ".DS_Store"))
    if other:
        errors.append(f"{slug}: only brand.json and assets/ belong here, not {', '.join(other)}")
print("\n".join(errors) if errors else f"ok: {len(slugs)} brands, {sum(1 for f in BRANDS.rglob('*') if f.is_file() and f.name != '.DS_Store')} files")
sys.exit(1 if errors else 0)
