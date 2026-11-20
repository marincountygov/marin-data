#!/usr/bin/env python3
"""Check the search hints on places, facilities, events, people and organizations (see place_lib.py).

  python3 check_search_hints.py

A name that needs context, or sits inside other words, must be one of the record's own names or search phrases
(or a name of a facility inside it). A hashtag starts with #. Nothing is empty.
"""
import sys

import place_lib as lib

errors, total = [], 0
facilities = lib.graph("facilities")
for name in (*lib.FILES, "organizations"):
    for record in lib.graph(name):
        names = {record["name"], *record.get("alternateName", [])}
        for part in lib.parts_of(record, facilities) if name == "facilities" else []:
            names |= {part["name"], *part.get("alternateNames", [])}
        search = lib.search_of(record)
        phrases = set(search.get("searchPhrases", []))
        where = f"{name}: {record['name']}"
        for key in ("needsContext", "insideWords"):
            for value in search.get(key, []):
                total += 1
                if value not in names | phrases:
                    errors.append(f"{where}: {value!r} under {lib.HINTS[key]} is not one of its names or search phrases")
        for value in search.get("hashtags", []):
            total += 1
            if not value.startswith("#") or " " in value:
                errors.append(f"{where}: the hashtag {value!r} must start with # and have no spaces")
        for key, values in search.items():
            if key != "alternateNames" and any(not str(v).strip() for v in values):
                errors.append(f"{where}: an empty value under {lib.HINTS.get(key, key)}")
print("\n".join(errors) if errors else f"ok: {total} search hints agree with their names")
sys.exit(1 if errors else 0)
