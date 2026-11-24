#!/usr/bin/env python3
"""Run the schemaGov validators on output/ and fail on any error that is not a known one.

  python3 -m pip install -r requirements-schemagov.txt
  python3 check_schemagov.py PATH_TO_SCHEMAGOV_CLONE [--output DIR]

Runs tools/validate.py and tools/shacl.py from the schemaGov clone. Both must pass.
The reference check (validate.py) may report only the errors listed in KNOWN below.
To tolerate a known problem for a while, add the record id and message patterns to KNOWN, with a comment saying why and when to remove it.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KNOWN = []  # (pattern for the record id, pattern for the message); both must match. Empty now.


def run(clone, tool, output):
    return subprocess.run([sys.executable, f"tools/{tool}", str(output)], cwd=clone, capture_output=True, text=True)


def errors_of(text):
    """The errors under the 'N error(s):' heading, as (first line, [message lines])."""
    out, current, inside = [], None, False
    for line in text.splitlines():
        if re.match(r"^\d+ error\(s\):", line):
            inside = True
        elif inside and line.startswith("  - "):
            current = (line[4:], [])
            out.append(current)
        elif inside and line.startswith("    ") and current is not None:
            current[1].append(line.strip())
    return out


parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
parser.add_argument("clone", help="path to a schemaGov clone")
parser.add_argument("--output", default=str(ROOT / "output"), help="the folder of JSON-LD to check (default: output/)")
args = parser.parse_args()
clone, output = Path(args.clone).resolve(), Path(args.output).resolve()
if not (clone / "tools" / "validate.py").is_file():
    sys.exit(f"{clone} does not look like a schemaGov clone (no tools/validate.py).")

HINT = "Install the packages with: python3 -m pip install -r requirements-schemagov.txt"
shapes = run(clone, "shacl.py", output)
if shapes.returncode != 0:
    sys.exit("schemaGov shape check failed:\n" + shapes.stdout + shapes.stderr)
if "SKIPPED" in shapes.stdout:
    sys.exit("The schemaGov shape check (shacl.py) skipped its checks, so nothing was checked.\n" + shapes.stdout.strip() + "\n" + HINT)

refs = run(clone, "validate.py", output)
if "SKIPPED" in refs.stdout:
    sys.exit("The schemaGov validator (validate.py) skipped some checks, so they were not run.\n"
             + "\n".join(l for l in refs.stdout.splitlines() if "SKIPPED" in l) + "\n" + HINT)
errs = errors_of(refs.stdout)
unknown = [(title, msgs) for title, msgs in errs if not (msgs and all(any(t.match(title) and m_.match(m) for t, m_ in KNOWN) for m in msgs))]
if refs.returncode != 0 and not errs:
    sys.exit("schemaGov validate failed without a readable error list:\n" + refs.stdout[-2000:] + refs.stderr[-1000:])
if unknown:
    print(f"{len(unknown)} schemaGov error(s) that are not on the known list:")
    for title, msgs in unknown[:40]:
        print(f"  - {title}")
        for m in msgs:
            print(f"      {m}")
    if len(unknown) > 40:
        print(f"  ... and {len(unknown) - 40} more")
    sys.exit(1)
print("ok: shapes pass" + (f", and the only reference errors are {len(errs)} known ones" if errs else ", and every reference resolves"))
