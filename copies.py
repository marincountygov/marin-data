"""What a consumers.json copy entry means: the files it copies, and the files that should not be at the destination.

An entry is either one file, {"from": "a.json", "to": "data/a.json"}, or a folder,
{"from": "brand", "to": "brands", "dir": true, "ignore": ["*/index.html"]}.
A folder entry copies every file under from. A file already under to that is not copied, and does not match an
ignore pattern (relative to to), is stale: it was removed here and must be removed there.
"""
import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALWAYS_IGNORED = [".DS_Store", "*/.DS_Store"]


def pairs(item):
    """(file here, destination path relative to the consumer) for every file the entry copies."""
    src = ROOT / item["from"]
    if item.get("dir"):
        to = item["to"].rstrip("/")
        return [(f, f"{to}/{f.relative_to(src).as_posix()}") for f in sorted(src.rglob("*")) if f.is_file() and f.name != ".DS_Store"]
    return [(src, item["to"])]


def stale(consumer, item):
    """Destination paths (relative to the consumer) under a folder entry that should not be there."""
    if not item.get("dir"):
        return []
    to = item["to"].rstrip("/")
    wanted = {dst for _, dst in pairs(item)}
    patterns = item.get("ignore", []) + ALWAYS_IGNORED
    dest = Path(consumer) / to
    out = []
    if dest.is_dir():
        for f in sorted(dest.rglob("*")):
            if f.is_file():
                rel = f.relative_to(dest).as_posix()
                if f"{to}/{rel}" not in wanted and not any(fnmatch.fnmatch(rel, p) for p in patterns):
                    out.append(f"{to}/{rel}")
    return out
