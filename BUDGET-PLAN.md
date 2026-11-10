# Marin budget and program dataset: plan

Revised 4 November after reading the schemaGov `budget` and `_core` profiles (`main`, commit 2a0ee5e) and running schemaGov's validators on the current Marin data.

## Goal

Connect the County's organizations, programs, funds and money, using schemaGov as the contract and the FY 2026-28 Budget Book as the source:

```text
GovernmentOrganization  <--administrativeClassification--  BudgetLine  --budget-->  Budget
Program                 <--program---------------------        |
Fund                    <--fund------------------------        +--> amount, direction, phase
```

Rule: when the Budget Book holds something schemaGov cannot express, keep the source data, record the gap in `qa/unsupported-source-fields.json`, and do not invent a property.

## What changed from the first draft

1. **The program type is `Program`, not `GovernmentProgram`.** schemaGov has no `GovernmentProgram`. All 189 Marin programs use it, and the validator says "no schema mapped" for each. This is fixed in step 3.
2. **One `Budget` cannot hold several fiscal states.** A `Budget` has one required `budgetPhase` (`proposed`, `approved`, `adjusted` or `executed`), one start and end date, and a publisher. Actual, approved and proposed figures therefore go in separate `Budget` entities, one per fiscal year and phase, not one "FY 2026-28 Budget".
3. **"Planned" is not a schemaGov phase.** See step 4 and question 2.
4. **Hierarchy uses `hasPart` and `isPartOf`.** A parent line must equal the sum of its children, and the validator checks it. Service-area totals are parents of department lines, and department totals are parents of program lines.
5. **The existing data does not validate today**, so step 3 fixes that first (details below).
6. **Paths.** The data lives in `marin-data/output/`, not `data/`. The duplicate `organizations-with-budget-codes.jsonld` is retired once nothing reads it.
7. **The Budget Book is not in the workspace.** The plan needs the PDF or text export (question 1).
8. **Added a last step:** show the result in Marin Docs (the department Budget tab).

## Source of truth

- schemaGov `main`: clone at `/Users/lukefretwell/Git/govfresh/schemaGov` (up to date with origin on 4 November). Read the source files, not the website:
  - `profiles/budget/{README.md, schema/*.json, codelists/*.json}`
  - `profiles/_core/schema/*.json`
  - `examples/example-gov/budget.jsonld`
  - `tools/validate.py` and `tools/shacl.py`
- Re-pull `main` before each checkpoint and note the commit used in `qa/`.

## Exact mapping (from the profile)

| Source information | schemaGov property | Notes |
|---|---|---|
| A fiscal year in one state | `Budget` with `budgetPhase`, `fiscalYear` (label), `startDate`, `endDate` (1 July to 30 June), `currency: "USD"`, `publisher` (County of Marin), `about` (us-ca-marin) | One Budget per year and phase. `budgetPhase` is required. |
| Actual | `executed` | |
| Approved | `approved` | |
| Proposed | `proposed` | |
| Planned (FY 2027-28) | no term | Gap. Use `proposed`, keep "Planned" in the name and `description`, and log it. Confirm in question 2. |
| Amount | `amount: {@type: MonetaryAmount, value, currency}` | Currency is required on every amount and must equal the Budget's. |
| Money in or out | `direction`: `revenue`, `expenditure`, `financing` | Required on every line. |
| Who spends it | `administrativeClassification: {@id}` to an organization | Never a name string. |
| Program | `program: {@id}` | `programClassification` (text) only if the book prints a program code. |
| Fund | `fund: {@id}` | `fundSource` (text) only when no Fund matches. |
| Department inside service area | `hasPart` / `isPartOf` between lines | Sums are checked. |
| Change column, net County cost | none | Derived values. Not lines. Log in unsupported fields. |
| FTE | none | Gap. Goes to `source/staffing-source.json`. |
| What the money is for (COFOG) | `functionalClassification` | Optional. Leave off unless the book states it. Do not guess. |
| Economic type (GFSM) | `economicClassification` | Same. Leave off. |
| Provenance | `sourceDataset`, `url`, `dateModified`, `distribution`, `license` on Budget; `sourceDataset` on lines | Page numbers have no property. Keep them in `qa/` and `sources.json`. |
| Fund's administrator | `Fund.administeredBy` | Only when the book says so. Never inferred from spending. |

IDs follow the existing pattern under `https://marincountygov.github.io/marin-data/id/`:

```text
budget/fy2026-27-proposed
budget-line/fy2026-27-proposed/<organization-slug>/<direction>
budget-line/fy2026-27-proposed/<program-slug>/<fund-code>/<direction>
```

Budget codes are used to match, never as the `@id`.

## Steps

### 1. Pull schemaGov and write the mapping
Done in this document. Add the commit hash to `qa/` when you run it.

### 2. Get the source
Put the Budget Book (PDF or text) in a folder outside the repo, record its title and URL in `sources.json`, and note the page ranges for each table.

### 3. Make the existing data valid (do this before any new data)
Baseline on 4 November: `validate.py` reports 23 errors and `shacl.py` reports 59 violations.

- **Program type:** change `GovernmentProgram` to `Program` on 189 programs.
- **Jurisdiction type:** the six jurisdictions use `Jurisdiction`, which is not allowed. The profile requires a schema.org place type, one of `AdministrativeArea`, `Country`, `State` or `City`. Use `AdministrativeArea` for the county and districts, `State` for California and `Country` for the United States. This fixes the 54 "areaServed must point at a Jurisdiction" and 5 `representsJurisdiction` violations, which come from this one cause.
- **Hierarchy:** `county-of-marin` lists 23 departments under `department`, but each names a service area as its `parentOrganization`. `parentOrganization` is canonical, so remove the derived lists or rebuild them from it. Marin Docs already builds from `parentOrganization` only.
- **`programClassification` on programs:** the profile defines it on a BudgetLine. On programs it holds a department label, which is really the administrator. Leave it for now, flag it, and revisit once the lines exist.
- Update `convert_org.py` or record that it is superseded, so the next conversion does not undo these fixes.
- Re-run both validators. The target is zero errors on the existing seven files.

### 4. Create the Budgets
One `Budget` for each phase the book prints:

| Budget | Phase | Period |
|---|---|---|
| FY 2024-25 actual | `executed` | 2024-07-01 to 2025-06-30 |
| FY 2025-26 approved | `approved` | 2025-07-01 to 2026-06-30 |
| FY 2026-27 proposed | `proposed` | 2026-07-01 to 2027-06-30 |
| FY 2027-28 planned | `proposed` (see question 2) | 2027-07-01 to 2028-06-30 |

Set `publisher` to the County, `about` to Marin County, and `supersedes` from the proposed budget to the approved one only where the book says so. Leave `adoptedBy`, `enactedAt` and `legislation` off unless the book names them. Leave `totalAmount` off unless the book prints a countywide total.

### 5. Service-area lines
For each of the five service areas and each Budget, create one line per direction the table shows (expenditure, revenue). `administrativeClassification` is the service-area organization. The service-area total is the parent of its department lines.

### 6. Department lines
One line per department row per budget and direction.
- Match each department to its organization by `local:marin-budget-department-code` first, then exact name. The names in the book differ from ours (for example Retirement is MCERA in some places).
- The Civil Grand Jury and the Tax Collector have no code, so match them by name or leave them out.
- Set `isPartOf` to the service-area line, and list the department lines in its `hasPart`.
- Check that each service-area total equals the sum of its departments. If the book's own rounding breaks that, do not adjust the figures. Report the difference in `qa/`.

**Checkpoint 1 (stop here).** Report:
- the Budgets and lines created, by budget and direction
- organizations matched, by code and by name
- fields mapped and fields left out, with reasons
- validator output, with zero errors expected
- any schemaGov gaps found

Only continue once this passes.

### 7. Parse Program Overview
Extract per program: name, department, fund, expenditure, revenue, net County cost, and the fiscal columns. Map only the fields in the table above.

### 8. Match programs
Match in this order: administering organization, then exact name, then normalized name, then the book's position in the hierarchy. A generic name such as "Administration" is never matched on its own. A match is contextual: HHS / Public Health / Administration is not Fire / Administration. Anything uncertain goes to `qa/ambiguous-matches.json`.

### 9. Match funds
Match on fund number first, then exact name, then normalized name. The fund number wins when both exist. Compare against the 28 funds in `funds.jsonld`. Funds that appear in the book but not in the file go to `qa/unmatched-funds.json`; do not create new Fund entities without the book's number and name.

### 10. Program-level lines
One line per program, fund, direction and budget.
- Use `program` and `fund` as `@id` references only.
- A program funded from several funds gets several lines. Do not merge them.
- Never put the fund on the Program. The money relationship belongs to the line.
- Set the line's `isPartOf` to its department line. If the program lines do not sum to the department line, report it. Do not add a balancing line.

### 11. Non-Departmental
Programs such as Animal Services, Countywide Operations and Emergency Operations are `Program` entities administered by the County of Marin, unless the book names another administrator. Do not create a department or a service area for them.

### 12. Fund administration
Add `Fund.administeredBy` only where the book or another authoritative source states who is responsible. Public Safety Realignment and similar multi-department funds stay without an administrator unless one is stated.

### 13. Staffing and workforce (kept out of the graph)
schemaGov has no FTE or position-count model. Write what the book provides to `source/staffing-source.json`: organization, fiscal year, status (adopted, modified, proposed, planned), fund and FTE. Job classifications (for example 0607 Senior Planner) go in `source/workforce-source.json`. They are not `Post` entities, because a Post is a single office such as County Executive or Supervisor, District 1.

### 14. Validation
Run `tools/validate.py` and `tools/shacl.py` from the schemaGov clone on the output directory, plus these checks of our own:
- valid JSON and JSON-LD; unique `@id` values
- every `@id` reference resolves (organization, program, fund, budget); no inline copies of referenced entities
- no BudgetLine without a Budget; every line's currency equals its Budget's
- parent lines equal the sum of their parts, or the difference is in `qa/`
- no service-area total treated as a department; no department treated as a program
- no actual, approved, proposed or planned values merged into one line
- no fund administration inferred from spending; no job classification as a Post

### 15. QA reports
Under `output/qa/`:
`budget-matches.json`, `unmatched-programs.json`, `unmatched-funds.json`, `unmatched-organizations.json`, `ambiguous-matches.json`, `unsupported-source-fields.json`.

Seed `unsupported-source-fields.json` with at least:
- FTE (no property)
- "Planned" phase (no term)
- net County cost and the change column (derived, not lines)
- source page numbers (no property)
- job classifications (no model)

Each entry has `field`, `source` (section and pages), `reason` and `recommendation`. These are the evidence for future schemaGov changes.

### 16. Show it in Marin Docs
After the lines validate, `build-budget.js` reads `budgets.jsonld` and `budget-lines.jsonld`, and the department page gets a Budget tab (phase by phase, with the fund and program breakdown), linked from the Budget section. The tab only appears for a department that has lines. The Docs build ignores the new files until then.

## Output layout

```text
marin-data/output/
  organizations.jsonld  people.jsonld  posts.jsonld  roles.jsonld
  jurisdictions.jsonld  programs.jsonld  funds.jsonld
  budgets.jsonld  budget-lines.jsonld
  sources.json
  source/   staffing-source.json  workforce-source.json
  qa/       six reports above, plus the schemaGov commit used
```

Keep the line file as one file unless it grows past what is practical to review. If so, split it by Budget, not by entity type.

## Acceptance criteria

- [ ] The existing seven files validate (zero validator errors, zero SHACL violations).
- [ ] No program is typed `GovernmentProgram` and no jurisdiction is typed `Jurisdiction`.
- [ ] One Budget per fiscal year and phase; actual, approved, proposed and planned figures stay distinct.
- [ ] Every amount has a currency; every line has a direction.
- [ ] Canonical organization, program and fund `@id` values are unchanged.
- [ ] Budget department codes are used for matching, not as identity.
- [ ] The five service areas and their departments have lines; parent totals equal the sum of their parts or the difference is reported.
- [ ] Program lines reference existing `Program` and `Fund` entities by `@id`.
- [ ] Multi-fund programs have one line per fund.
- [ ] No fund is administered by a department without a stated source.
- [ ] Non-Departmental programs have no invented department.
- [ ] FTE and job classifications are outside the graph and documented as gaps.
- [ ] Ambiguous matches are reported, not guessed.
- [ ] Both schemaGov validators pass on the final output.
- [ ] Marin Docs still builds and its checks pass.

## Questions to answer before starting

1. Where is the Budget Book (PDF or text), and which pages hold the service-area tables and the Program Overview?
2. How should FY 2027-28 "Planned" be recorded? I suggest `proposed`, with "Planned" in the Budget's name and description. The alternative is to leave it out of the graph until schemaGov has a term.
3. Is it OK to change the existing data in step 3 (program type, jurisdiction type, the County's `department` list)? Nothing in Marin Docs reads those values.


## FY 2025-26 Final Budget book

Added 10 November. The book (`source/2026 Budget Book - Not Remediated.pdf`, 385 pages) is organised by State Controller schedule, not by department, so `extract_budget_2025.py` reads it row by row into `output/budget-2025-26/schedules.json` and builds schemaGov entities from the schedules that map cleanly.

- **Budgets:** `fy2023-24-executed`, `fy2024-25-estimated` (phase `adjusted`; schemaGov has no "estimated"), `fy2025-26-recommended` (`proposed`) and `fy2025-26-adopted` (`approved`). These are separate from `fy2025-26-approved`, which comes from the FY 2026-28 book.
- **Lines:** Schedule 8 (function, activity, budget unit; expenditure, all four columns), Schedule 5 (additional financing sources by source; revenue) and Schedule 2 (financing uses and additional financing sources by fund; adopted). Budget units map to organizations by `local:marin-budget-department-code`; units 000, 653, 659 and 900 have no organization and are listed in `qa/budget-2025-26-unmapped.json`.
- **Funds:** `funds-2025-26.jsonld` holds the 106 fund numbers in Schedule 2 that `funds.jsonld` lacks (name and code only).
- **Totals:** the book's own subtotals differ from their parts by $1 or $2 in a few places; the amount is kept as printed, the `hasPart` link is left out, and each is listed in the QA file. The extractor fails if anything larger differs.
- **Overprinted cells:** four values in Schedule 4 (pages 51, 71, 77, 83) are printed over each other and cannot be read; they are null and listed in `qa/budget-2025-26-checks.json`.
- **Not in schemaGov:** schedule rows that have no entity here (fund balance, obligated fund balances, budget unit by object, internal service and enterprise funds, special districts, personnel allocation, Road Fund work program, property tax trends) stay in `schedules.json` with the book's labels.
