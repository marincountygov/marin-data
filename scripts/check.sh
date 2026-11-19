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
python3 -m py_compile check_sources.py check_orgs.py check_consumers.py check_copies.py check_brand.py check_projects.py check_schemagov.py copies.py sources_lib.py scripts/sync_consumer.py \
  build_sources.py build_org_links.py build_place_links.py build_event_links.py build_place_aliases.py build_facility_list.py build_location_list.py build_person_links.py check_locations.py check_codes.py check_search_hints.py place_lib.py build_org_aliases.py build_org_index.py

python3 check_sources.py            # source registry: fields, ids, hashes of stored files
python3 build_sources.py --check    # output/sources.json is current
python3 check_orgs.py               # agencies list and organizations.jsonld agree
python3 build_org_links.py --check  # organizations/monitors.json is current
python3 build_place_links.py --check # organizations/places.json is current
python3 build_event_links.py --check # organizations/events.json is current
python3 build_facility_list.py --check # organizations/facilities.json is current
python3 build_location_list.py --check # organizations/locations.json is current
python3 build_person_links.py --check # organizations/people.json is current
python3 build_place_aliases.py --check # organizations/place-aliases.json is current
python3 build_org_aliases.py --check # organizations/aliases.json is current
python3 build_org_index.py --check   # organizations/index.json is current
python3 check_search_hints.py       # the search hints agree with the names
python3 check_codes.py              # every place, facility, event and person has its own code
python3 check_consumers.py          # every file a consumer copies exists
python3 check_brand.py              # brand.json files and their assets agree
python3 check_projects.py           # the shared list of projects is well formed
# Nothing permanent about a project may change (ids, Links codes). Compared with main. In GitHub the check
# must run, so a missing main is an error there. On your own machine it is skipped if main has not been fetched.
if git rev-parse --verify --quiet origin/main >/dev/null 2>&1; then
  python3 check_projects.py --against origin/main
  python3 check_locations.py --against origin/main
elif [[ -n "${CI:-}" ]]; then
  printf 'ERROR: origin/main is not fetched, so the projects guard cannot run. Run: git fetch origin main\n' >&2; exit 1
else
  printf 'SKIP: origin/main is not fetched here, so the check for removed projects and changed Links codes was not run.\n' >&2
fi
printf 'Requested checks completed successfully.\n'
