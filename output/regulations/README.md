# Personnel Management Regulations (PMR)

The County's Personnel Management Regulations as schemaGov JSON-LD (policy profile). The saved page of the County's Human Resources site, `source/pmr/`, is the authority. These files are its structured form.

Canonical page: https://www.hr.marincounty.gov/regulations-policies-procedures/personnel-management-regulations/all-personnel-management-regulations

## Files

| File | What it holds |
|---|---|
| `manual.jsonld` | The manual, its saved page, and the four major groups |
| `regulations.jsonld` | Each PMR (a chapter) and each numbered provision under it, with its text |
| `definitions.jsonld` | The defined terms, each linked to its provision by `subjectOf` |
| `qa.json` | Counts from the last run: groups, PMRs, provisions, definitions, tables, citations |

## Generated, never edited

```
python3 -m pip install -r requirements-pmr.txt
python3 extract_pmr.py            # write these files from source/pmr/
python3 extract_pmr.py --check    # fail if they are out of date
```

Correct a mistake in `extract_pmr.py` and regenerate. Ids are under `https://marincountygov.github.io/marin-data/id/regulation/`. The jurisdiction is `us-ca-marin` and the publisher is the Human Resources record (`organization/hr`), both already in `output/`.

## Checked with schemaGov

`python3 check_schemagov.py <schemaGov clone>` runs on all of `output/`, these files included. The shapes and every reference pass.

## Where the source is odd (kept as written)

- PMR 35 has a provision numbered `25.3` ("Actual Service Required"). PMR 25 also has a `25.3`. The id follows the PMR it sits in (`pmr-35/25.3`), the number is kept.
- PMR 22 and PMR 26 are headed `PMR 22:` and `PMR 26:`. The other 27 are headed `Personnel Regulation N:`.
- Two citations name `PMR 1.2`, which the page does not contain. They stay as text, as written.
- PMR 34 gives its effective date as `02-07-17`, which does not say which part is the day or the year.

## Where the schema falls short (values kept in a local identifier)

- A date that is not a whole date (`2005-01`, `2026-04`, `02-07-17`) cannot go in `legislationDateOfApplicability`. It is kept in `local:pmr-effective-date-as-written`.
- A preparer or approver named only as text (`Laura Armor`, `ss/President, Board of Supervisors`) cannot go in `creator` or `legislationCountersignedBy`, which take a reference. They are kept in `local:pmr-prepared-by-as-written` and `local:pmr-approved-by-as-written`. Pointing them at an organization or person record would be a guess.
- Tables (two, one in PMR 40) are not modelled. Their text is in the provision.
