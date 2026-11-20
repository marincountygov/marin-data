"""What every builder needs to know about a place, a facility, an event or a person in marin-data.

The code of a record is its gs:local identifier. It is the one name other apps use for the record: the page name
in Marin Pulse, the value Marin Links puts in a link, and the key the link files carry. It does not belong to any
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
FILES = ("jurisdictions", "facilities", "events", "people", "external-organizations", "services", "topics")


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
    """district, city, community, area, region or county, for a jurisdiction."""
    explicit = [p["value"] for p in record.get("additionalProperty", []) if p.get("propertyID") == "local:place-kind"]
    if explicit:
        return explicit[0]
    if ident(record, DISTRICT_ID):
        return "district"
    if not record.get("containedInPlace"):
        return "county"
    return "city" if record.get("governmentLevel") == "municipal" else "community"


# Search hints. These say how apps should look for a record by its names. They are facts about the names, so
# every app can use them, and they are kept on the record in additionalProperty, each one repeatable.
HINTS = {
    "searchPhrases": "local:search-phrase",        # a phrase that points at the record though it is not a name for it
    "needsContext": "local:name-needs-context",    # a name or phrase that counts only beside the word Marin
    "insideWords": "local:name-inside-words",      # a name that is also inside other words, so it counts as a whole word only
    "hashtags": "local:hashtag",                   # a hashtag for the record
    "confusableNames": "local:confusable-name",    # a name the record is often confused with, which is not it
}


def search_of(record):
    """The other names and the search hints of a record, as the link files carry them. Empty ones are left out."""
    found = {}
    if record.get("alternateName"):
        found["alternateNames"] = record["alternateName"]
    for key, scheme in HINTS.items():
        values = [p["value"] for p in record.get("additionalProperty", []) if p.get("propertyID") == scheme]
        if values:
            found[key] = values
    return found


def parts_of(record, facilities):
    """The facilities that sit inside a facility (a theater in a center): their names and hints."""
    return [{"name": f["name"], **search_of(f)} for f in facilities if (f.get("containedInPlace") or {}).get("@id") == record["@id"]]
