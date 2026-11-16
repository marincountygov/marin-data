"""Read sources.json, the registry of source documents."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load():
    return json.loads((ROOT / "sources.json").read_text())


def get(source_id):
    for s in load()["sources"]:
        if s["id"] == source_id:
            return s
    raise KeyError(f"no source with id {source_id} in sources.json")


def legacy():
    """The shape older scripts read from output/sources.json: one entry per legacyKey."""
    reg = load()
    out = {}
    for s in reg["sources"]:
        key = s.get("legacyKey")
        if not key:
            continue
        e = {"title": s["title"], "edition": s.get("edition"), "url": s.get("url")}
        if s.get("sourcePages"):
            e["sourcePages"] = s["sourcePages"]
        if s.get("notes") and key == "budgetBook":
            e["note"] = s["notes"]
        if s.get("pageOffset"):
            e["pageOffset"] = s["pageOffset"]
        e.update(s.get("extraction", {}))
        out[key] = {k: v for k, v in e.items() if v is not None}
    for ref in reg.get("references", []):
        out[ref["legacyKey"]] = {"url": ref["url"], **({"note": ref["notes"]} if ref.get("notes") else {})}
    return out
