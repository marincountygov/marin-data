#!/usr/bin/env bash
# Checks the data and that every generated file is current. Needs only Python 3.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
command -v python3 >/dev/null 2>&1 || { printf 'ERROR: Python 3 is required.\n' >&2; exit 1; }

bash -n scripts/check.sh
bash -n scripts/build.sh
bash -n scripts/lock.sh
bash -n scripts/data_sync.sh
python3 -m py_compile check_sources.py check_orgs.py check_consumers.py check_copies.py check_brand.py copies.py sources_lib.py scripts/sync_consumer.py \
  build_sources.py build_org_links.py build_org_aliases.py

python3 check_sources.py            # source registry: fields, ids, hashes of stored files
python3 build_sources.py --check    # output/sources.json is current
python3 check_orgs.py               # agencies list and organizations.jsonld agree
python3 build_org_links.py --check  # organizations/monitors.json is current
python3 build_org_aliases.py --check # organizations/aliases.json is current
python3 check_consumers.py          # every file a consumer copies exists
python3 check_brand.py              # brand.json files and their assets agree
printf 'Requested checks completed successfully.\n'
