#!/usr/bin/env python3
"""Run the schemaGov validators on output/ and fail on any error that is not a known one.

  python3 check_schemagov.py PATH_TO_SCHEMAGOV_CLONE [--output DIR]

Runs tools/validate.py and tools/shacl.py from the schemaGov clone. The shape check (shacl.py) must pass.
The reference check (validate.py) may report only the errors listed in KNOWN below.

KNOWN: the CIP budgets and budget lines for the later programmed years use the budget phase "planned".
schemaGov allows only proposed, approved, adjusted and executed, so each of those is reported. Mapping them to
"proposed" would change what the data says, so they stay as they are until schemaGov decides about "planned".
Remove this entry when it does, or when the data changes.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KNOWN = [
    re.compile(r"^budgetPhase: 'planned' is not one of \[.*\]$"),
]


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

shapes = run(clone, "shacl.py", output)
if shapes.returncode != 0:
    sys.exit("schemaGov shape check failed:\n" + shapes.stdout + shapes.stderr)

refs = run(clone, "validate.py", output)
errs = errors_of(refs.stdout)
unknown = [(title, msgs) for title, msgs in errs if not (msgs and all(any(k.match(m) for k in KNOWN) for m in msgs))]
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
print(f"ok: shapes pass, and the only reference errors are {len(errs)} known ones (budgetPhase 'planned')")
