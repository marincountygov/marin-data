#!/usr/bin/env bash
# Converts the synthetic duplicate-code input and runs both schemaGov validators.
# Usage: tests/run_tests.sh PATH_TO_SCHEMAGOV_CLONE [PYTHON]
set -euo pipefail
CLONE="${1:?path to the schemaGov clone}"
PY="${2:-python3}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$(mktemp -d)"
"$PY" "$HERE/convert_org.py" "$HERE/tests/duplicate-code-input.json" "$OUT" >/dev/null
# the two "Intake" divisions share a code but must stay separate entities
"$PY" - "$OUT/organizations.jsonld" <<'P'
import json, sys
g = json.load(open(sys.argv[1]))["@graph"]
intake = [o for o in g if o["name"] == "Intake"]
assert len(intake) == 2, "expected two Intake divisions"
assert intake[0]["@id"] != intake[1]["@id"], "same @id for different bodies"
assert intake[0]["parentOrganization"] != intake[1]["parentOrganization"]
codes = {i["value"] for o in intake for i in o["identifier"] if i["propertyID"].endswith("agency-code")}
assert codes == {"dv-01"}, "the shared code should appear on both"
print("duplicate code kept as an identifier on two separate bodies: ok")
P
cd "$CLONE"
"$PY" tools/validate.py "$OUT"
"$PY" tools/shacl.py "$OUT"
