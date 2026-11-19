#!/usr/bin/env python3
"""Check that every place, facility, event and person has one code, and that no two share one.

  python3 check_codes.py

The code is the gs:local identifier (see place_lib.py). It must be lowercase words joined by hyphens. A record
that Marin Mentions watches carries a local:marin-mentions-monitor-id as well; the two are allowed to differ,
but they are the same word everywhere today.
"""
import sys

import place_lib as lib

errors, seen, total = [], {}, 0
for name in lib.FILES:
    for record in lib.graph(name):
        total += 1
        found = lib.ident(record, lib.CODE_ID)
        where = f"{name}: {record['name']}"
        if len(found) != 1:
            errors.append(f"{where}: needs exactly one {lib.CODE_ID} code, has {len(found)}")
            continue
        if not lib.CODE.match(found[0]):
            errors.append(f"{where}: the code {found[0]!r} must be lowercase words joined by hyphens")
        if found[0] in seen:
            errors.append(f"{where}: the code {found[0]!r} is also used by {seen[found[0]]}")
        seen[found[0]] = where
print("\n".join(errors) if errors else f"ok: {total} records each have their own code")
sys.exit(1 if errors else 0)
