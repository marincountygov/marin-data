# Statistics

Statistics about Marin's places, kept as schemaGov `Observation` records. The first source is the U.S. Census Bureau's American Community Survey (ACS) 5-year estimates, 2020-2024. The original publisher stays the authority. This repo holds Marin's normalized, versioned copy that the apps read.

```
Census files -> extract_acs.py -> statistics/source/ -> build_statistics.py -> output/ -> apps
                (retrieve)         (as published)        (map, calculate,       (schemaGov JSON-LD)
                                                          normalize)
```

## What is where

| Path | What it holds |
|---|---|
| `statistics/acs-mapping.json` | Each measure (a schemaGov statistical variable), the ACS cells it is made from, and its calculation. The only place a Census cell code appears. |
| `statistics/source/acs-2024-5yr/` | The Census values for Marin, exactly as published (text, sentinel codes untouched). `manifest.json` has the retrieval date and each downloaded file's address, size and SHA-256. |
| `output/statistics/variables.jsonld` | The measures. |
| `output/statistics/datasets.jsonld` | The ACS release, as a schemaGov dataset. Observations point at it with `sourceDataset`. |
| `output/statistics/observations/acs-2024-5yr/` | The observations, in `county`, `places` and `tracts` files. |
| `output/areas.jsonld` | Census areas that are not already a Marin place: the census tracts and four combined Census places. |
| `statistics/geography-links.json` | Which Census area is which Marin place, what needs review, and which Marin places have no statistics. Generated. |
| `statistics/omitted-values.json` | Every value left out, with the reason and the Census cells. Generated. |
| `statistics/ACCEPTANCE-REPORT.md` | What the first import showed. |

Marin's places stay in `output/jurisdictions.jsonld`. An existing place gets a `census-geoid` identifier; its statistics are observations that point at it. A place never holds statistics itself.

## Rules

- Public ids are plain words (`median-household-income`), never Census codes.
- Nothing is rounded when it is read. A share and its margin are rounded to 6 decimals when they are calculated.
- A blank, a Census code (`-666666666` and the others) or a value that is not a point estimate is left out and listed in `omitted-values.json`. It is never written as 0.
- A margin of error is published only where the Census published it or where Census methodology gives one (sums, differences, shares). See the header of `build_statistics.py` for the formulas.
- Boundaries are not stored, and "which communities overlap which tracts" are not claimed. Marin's own communities have no statistics unless a Census place has exactly their name.
- No Census API key is needed or stored. Do not add one to any file in this repo.

## Add a measure

Add a variable to `acs-mapping.json` (its cells, universe, unit and calculation; a share names a denominator variable). Run the steps below. `check_statistics.py` fails if a cell is not in the stored source.

## Bring in a new ACS release

1. Copy `acs-mapping.json`'s `source` block: change `id`, `name`, `vintage`, `observationPeriod`, the URLs and `tableFile`. Keep the old release's folder and observations: they are history, and do not change.
2. `python3 extract_acs.py download DIR` then `python3 extract_acs.py extract DIR --retrieved YYYY-MM-DD`.
3. `python3 build_statistics.py`, `python3 check_statistics.py`, then the schemaGov check.
4. Review the pull request in parts: `statistics/source/` (the source changed), `acs-mapping.json` (a calculation changed), `output/areas.jsonld` and `geography-links.json` (the geography changed).

Do not compare two 5-year releases as a trend by default. Consecutive releases share four of five survey years, tract boundaries and some definitions change between them, and each estimate has its own margin of error. A change is only worth showing when it is larger than the margins and the geography and definition are the same.

## Whether to automate a source

Decide for each source: how often it is released, how fresh the County needs it, how much a manual update costs, and what a bad automatic update would do. ACS 5-year is released once a year, so a manual update with a reviewed pull request is enough for now. If it is automated later, the job should only open a pull request (never merge) and keep any key in a repository secret. Static, version-controlled data is fine for slowly changing sources.
