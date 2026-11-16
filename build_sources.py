#!/usr/bin/env python3
"""Write output/sources.json from sources.json, for app scripts that still read the older file.

  python3 build_sources.py           write output/sources.json
  python3 build_sources.py --check   fail if output/sources.json is out of date
"""
import json
import sys
from pathlib import Path

import sources_lib

OUT = Path(__file__).resolve().parent / "output" / "sources.json"
text = json.dumps(sources_lib.legacy(), indent=2, ensure_ascii=False) + "\n"
if "--check" in sys.argv:
    if not OUT.exists() or OUT.read_text() != text:
        sys.exit("output/sources.json is out of date. Run: python3 build_sources.py")
    print("ok: output/sources.json is current")
else:
    OUT.write_text(text)
    print(f"wrote {OUT.name}")
