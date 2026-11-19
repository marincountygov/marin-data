"""What every builder needs to know about a place, a facility, an event or a person in marin-data.

The code of a record is its gs:local identifier. It is the one name other apps use for the record: the page name
in Marin Docs, the value Marin Links puts in a link, and the key the link files carry. It does not belong to any
one app. A record that Marin Mentions watches also has a local:marin-mentions-monitor-id, which says which
monitor, and is usually the same word. A code is permanent: it ends up inside links people have shared.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
CODE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
CODE_ID, MONITOR_ID, DISTRICT_ID = "gs:local", "local:marin-mentions-monitor-id", "local:marin-supervisorial-district"
FILES = ("jurisdictions", "facilities", "events", "people")


def graph(name):
    return json.loads((OUTPUT / f"{name}.jsonld").read_text())["@graph"]


def ident(record, scheme):
    return [i["value"] for i in record.get("identifier", []) if i.get("propertyID") == scheme]


def code_of(record):
    """The record's code, or None when it has none or more than one."""
    found = ident(record, CODE_ID)
    return found[0] if len(found) == 1 else None


def monitor_of(record):
    found = ident(record, MONITOR_ID)
    return found[0] if found else None


def kind_of(record):
    """district, city, community or county, for a jurisdiction."""
    if ident(record, DISTRICT_ID):
        return "district"
    if not record.get("containedInPlace"):
        return "county"
    return "city" if record.get("governmentLevel") == "municipal" else "community"
