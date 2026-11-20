#!/usr/bin/env python3
"""Copy the files marin-data gives a consumer into its folder, or check that its copies are current.

  python3 ../marin-data/scripts/sync_copies.py .           copy what consumers.json lists for this folder
  python3 ../marin-data/scripts/sync_copies.py . --check   fail if a copy differs, is missing or is left over

Run it from the consumer's folder, with marin-data next to it. The consumer is found by its folder name in
consumers.json, so one script serves every app and the list of what each app copies is in one place.

consumers.json lists each copy as { "from": path in marin-data, "to": path in the consumer }. A copy with
"dir": true is a whole folder: files that marin-data no longer has are removed, a top-level folder that is gone
is removed, and "ignore" lists the files that belong to the consumer (matched as paths inside the folder).
Never edit a copy: change the data in marin-data, then sync.
"""
import fnmatch
import json
import shutil
import sys
from pathlib import Path

JUNK = ".DS_Store"


def entry_for(data, consumer):
    entry = next((c for c in json.loads((data / "consumers.json").read_text())["consumers"] if c["repo"] == consumer.name), None)
    if entry is None:
        raise SystemExit(f"{consumer.name} is not listed in marin-data/consumers.json")
    return entry


def wanted_files(data, entry):
    """Every file a consumer copies: destination (relative to the consumer) -> the file in marin-data."""
    want = {}
    for copy in entry["copies"]:
        src = data / copy["from"]
        if copy.get("dir"):
            for f in sorted(src.rglob("*")):
                if f.is_file() and f.name != JUNK:
                    want[(Path(copy["to"]) / f.relative_to(src)).as_posix()] = f
        else:
            want[Path(copy["to"]).as_posix()] = src
    return want


def leftovers(data, consumer, entry, want):
    """Files and folders in a copied folder that marin-data no longer has and the consumer does not own."""
    stale_files, gone_dirs = [], []
    for copy in entry["copies"]:
        if not copy.get("dir"):
            continue
        src, dst = data / copy["from"], consumer / copy["to"]
        if not dst.is_dir():
            continue
        ignore = copy.get("ignore", [])
        here = {d.name for d in src.iterdir() if d.is_dir()}
        gone_dirs += [(Path(copy["to"]) / d.name).as_posix() for d in sorted(dst.iterdir()) if d.is_dir() and d.name not in here]
        for f in sorted(dst.rglob("*")):
            if not f.is_file() or f.name == JUNK:
                continue
            rel = f.relative_to(dst).as_posix()
            whole = (Path(copy["to"]) / rel).as_posix()
            if whole in want or any(fnmatch.fnmatch(rel, p) for p in ignore):
                continue
            if any(whole.startswith(g + "/") for g in gone_dirs):
                continue
            stale_files.append(whole)
    return stale_files, gone_dirs


def run(data, consumer, check):
    """Returns a list of problems (check) or the actions taken (copy)."""
    entry = entry_for(data, consumer)
    want = wanted_files(data, entry)
    stale_files, gone_dirs = leftovers(data, consumer, entry, want)
    if check:
        problems = []
        for dest, src in want.items():
            f = consumer / dest
            if not f.is_file():
                problems.append(f"{dest}: missing")
            elif f.read_bytes() != src.read_bytes():
                problems.append(f"{dest}: differs from marin-data")
        problems += [f"{d}: not in marin-data any more" for d in stale_files]
        problems += [f"{d}/: not in marin-data any more" for d in gone_dirs]
        return problems, len(want), entry
    done = []
    for d in gone_dirs:
        shutil.rmtree(consumer / d)
        done.append(f"removed {d}/ (not in marin-data any more)")
    for dest, src in want.items():
        f = consumer / dest
        if not f.is_file() or f.read_bytes() != src.read_bytes():
            f.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, f)
            done.append(f"copied {dest}")
    for d in stale_files:
        if (consumer / d).exists():
            (consumer / d).unlink()
            done.append(f"removed {d}")
    for copy in entry["copies"]:
        if copy.get("dir") and (consumer / copy["to"]).is_dir():
            for d in sorted((p for p in (consumer / copy["to"]).rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
                if not any(d.iterdir()):
                    d.rmdir()
    return done, len(want), entry


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit("usage: sync_copies.py <consumer folder> [--check]")
    consumer = Path(args[0]).resolve()
    data = Path(__file__).resolve().parents[1]
    check = "--check" in argv
    result, total, entry = run(data, consumer, check)
    if check:
        if result:
            fix = " && ".join(entry["sync"] + entry["build"])
            raise SystemExit(f"{consumer.name} differs from marin-data:\n  " + "\n  ".join(result) + f"\nRun: {fix}")
        print(f"ok: {total} files match marin-data")
    else:
        print("\n".join(result) if result else f"nothing to copy: {total} files already match marin-data")


if __name__ == "__main__":
    main(sys.argv[1:])
