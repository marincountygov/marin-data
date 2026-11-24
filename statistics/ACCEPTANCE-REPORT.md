# Marin acceptance report: ACS 5-year, first import

| | |
|---|---|
| Source | U.S. Census Bureau, American Community Survey 5-year estimates, 2020-2024 (table-based summary file) |
| Vintage and period | 2024; `observationPeriod` 2020/2024 |
| Retrieved | 2026-11-24, from the Census download site, no API key |
| Indicators | 10, plus 4 denominators published so every share can be reproduced |
| Observations | 1,306 (of 1,330 possible), including 33 one-sided bounds for open-ended medians |
| Left out | 24, each listed in `omitted-values.json` with its Census cells |
| Validation | schemaGov shapes pass and every reference resolves, against schemaGov 9ef81ef; 23 calculation tests pass; local checks pass |

## Geography

- 95 Census areas: the county, 31 places (11 cities and towns, 20 Census-designated places) and 63 census tracts. Block groups were not imported.
- Linked to an existing Marin place by exact name: the county, all 11 cities and towns, and 16 Census-designated places (28 in all). The link is a `census-geoid` identifier on the Marin place.
- Four combined Census places have no single Marin counterpart, so each is a new area: Black Point-Green Point, Lagunitas-Forest Knolls, Lucas Valley-Marinwood and Tamalpais-Homestead Valley. Marin lists those as eight separate communities. They are named in `geography-links.json` under `needsReview`. No containment or overlap is claimed, because no boundaries are stored.
- 35 Marin places have no statistics: for example Greenbrae, Kent Woodlands, Inverness Park, East San Rafael, West Novato and West Marin. They have no matching Census place, and the plan does not allow estimating them from tracts without a documented method. The full list is in `geography-links.json`.
- Marin's communities are still typed as jurisdictions (kept as they are, as decided). The 63 tracts and 4 combined places are `Place` records with `areaType` and are contained in Marin County.

## Uncertainty

- 1,272 of 1,273 observations with a value carry a margin of error at the 90 percent level. The one without is the county's total population, which the Census controls and publishes with no margin.
- Margins for sums, differences and shares are calculated with the Census formulas and are covered by tests.
- Margins are wide in small places. Marin City's median household income is $68,846 with a margin of $26,081.

## Missing and special values

- Open-ended medians (margin code -333333333): 25 median gross rent values and 8 median household income values. The Census publishes 250,001 and 3,501 as stand-ins for "$250,000 or more" and "$3,500 or more". They are written as one-sided bounds (`minValue` 250000 and 3500) with no `value` and no margin of error, and only where the source estimate is exactly the cap plus 1. Affected places include Belvedere, Ross, Corte Madera, Sausalito and Tiburon. A consumer should show them as "250,000 or more".
- No sample or too few (estimate code -666666666): 13 median gross rent, 3 median household income, 1 median age. These are left out.
- A zero denominator (so no share): 7 observations, in tracts or places with no residents, renters or people with poverty status determined.
- No value was written as zero. No other special codes appeared.

## schemaGov findings

All three problems found in the first import are fixed upstream (schemaGov PRs 40 and 41) and consumed here.

1. **Open-ended (top-coded) values.** An observation can now state a one-sided bound with `minValue` and no `value`. marin-data writes the 33 open-ended medians this way.
2. **A plain `Place` needed `areaType`.** The validator now treats a `Place` with no `areaType` as a facility, so the six facilities (St. Vincent's, Gallinas Creek, Tam Valley Community Center, Homestead Valley Community Center, Marin Art & Garden Center, Marin Humane) pass with no exception and were not retyped. The tolerance in `check_schemagov.py` is removed. Always set `areaType` on a statistical area: one that forgets it passes silently as a facility.
3. **The CI pin for schemaGov** now points at 9ef81ef.
4. **Rent burden denominator.** It is all renter households (`B25070_001`), as the schemaGov crosswalk says. The Census's own published percentage leaves out households where the rent share is "not computed", so this reads slightly lower. The variable's description says so.

Still not representable: why a value was suppressed, quality flags and annotations, and survey weights.

## Data quality notes

- Source tables are the Census's table-based summary file, not the API. Values match an independent read of the raw files (checked for 65+ population in the county and the poverty counts for Marin City).
- Tract GEOIDs use 2020 tract boundaries. A future release on new boundaries needs a new geography check.
- Names match exactly (for example "Marin City"). That is a name match, not a boundary match.

## Recommended next indicators

Prioritize ones staff will act on: renter and owner share, vacancy, language spoken at home with limited English, children in poverty, older adults living alone, vehicle availability, commute mode and educational attainment. Propose the full list for review before building.
