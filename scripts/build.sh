#!/usr/bin/env bash
# Regenerates every file that is generated from the data. Run it after changing output/organizations.jsonld,
# organizations/monitors-not-organizations.json or sources.json, then commit the result.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
python3 build_sources.py          # output/sources.json
python3 build_org_links.py        # organizations/monitors.json
python3 build_org_aliases.py      # organizations/aliases.json
python3 build_org_index.py        # organizations/index.json
