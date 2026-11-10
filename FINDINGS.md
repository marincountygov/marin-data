# County of Marin organization data in schemaGov: findings

## What the data was

Two sources, both from this workspace:

- `marin-links/data/agencies.json` is the master list of County agencies. It has 45 entries: 25 departments and 20 divisions. Each entry has an id, a code, a name, a type, a parent, a web address and a status. All 45 are active. The list is flat, and a division points to its department with `parent`.
- The "Departments" group in `marin-mentions/config/monitors.yaml` has 30 entries. It is a list used to watch news mentions, so each entry has only an id, a name and search phrases. The file says its `group` field only controls screen layout, so I did not use it as evidence of what kind of body something is.

The County web team's original list was not available. Neither source has a code that repeats, so the duplicate-code case is covered by a synthetic test only (see below).

## What was produced

- 49 organizations: the county government, 45 entries from the master list, and 3 extra bodies from the watch list.
- 3 jurisdictions: the United States, California, and the County of Marin. California and the United States are there so the county's `containedInPlace` link resolves.
- Both schemaGov checks pass with no errors: `tools/validate.py` (52 entities, 99 references) and `tools/shacl.py`.

Run it again with:

    python3 convert_org.py ../marin-links/data/agencies.json output --monitors ../marin-mentions/config/monitors.yaml

## Two entities for the county

The territory is an `AdministrativeArea` named County of Marin (`governmentLevel: subregional`). The county government is a separate `GovernmentOrganization` with classification `government` and no parent. It points at the territory with `areaServed`. Every other organization also carries `areaServed` and `governmentLevel`, because the validator requires them for every organization in an org chart.

## Field mapping

| Source | schemaGov |
|---|---|
| master list `name` | `name` |
| master list `url` | `url` |
| master list `id` | slug in `@id` (the slash becomes a dash, so `hhs/public-health` is `hhs-public-health`), and identifier `local:marin-links-agency-id` |
| master list `code` | identifier `local:marin-links-agency-code` |
| master list `parent` | `parentOrganization`. A department's parent is the county government; a division's parent is its department. |
| master list `type` | `organizationClassification` (see below) |
| master list `status` | not mapped (all are active) |
| watch list `id` | identifier `local:marin-mentions-monitor-id` |
| watch list `name` | `alternateName`, only when it differs from the official name (44 entries) |
| file title, version, source, notes | not mapped; they describe the file, not an organization |
| order of the list | not mapped; it is menu order, not structure |

Hierarchy comes only from `parentOrganization`. The `department` and `subOrganization` lists on a parent are generated from it, so every listed child names that parent. Departments and divisions go under `department`. The Board of Supervisors, the Office of Emergency Management and the two service areas go under `subOrganization`.

The master list shows departments with no parent because it stops at the top of the public chart. I placed each under the county government. That parent comes from the file's `organization` entry, not from a field on each department.

The master list and the watch list were joined with a hand-written table of 25 pairs in `convert_org.py` (for example `marin-fire` to `fire`), never by name. The 20 divisions use one rule: `marin-` plus the division id with the slash turned into a dash. Those 20 monitors were added to `marin-mentions/config/monitors.yaml` in a new Divisions group, so every organization except the county government itself now has a monitor id.

The division monitors use narrow search phrases and are not yet tuned against real results.

## Identifiers and duplicate codes

Every code is stored with a named scheme (`local:marin-links-agency-code`), never used as an `@id`, and never assumed to be unique. The synthetic test `tests/duplicate-code-input.json` puts the code `dv-01` under two different departments. The converter keeps two separate organizations with different `@id`s and different parents, and both validators pass. Run it with `tests/run_tests.sh <path to schemaGov clone> [python]`.

## `@id` choices

`@id` names the body and is not its web address. Most use `https://marincountygov.github.io/marin-data/id/organization/<slug>`, a domain you control. These 7 use a `urn:marin:org:<slug>` instead:

- District Attorney, Library, Retirement and Sheriff, because each runs its own website on a separate domain. Their public pages are in `url`.
- The Office of Emergency Management and County Service Areas 6 and 29, because the data has no public page for them.

The marin-data address pattern is not live yet. It needs to be published before those `@id`s will open.

## Classification

For the master list I used the source's own `type` (`department` or `division`), not the name or the depth. The one exception is the Board of Supervisors, which is `legislature`. The county government is `government`.

Low confidence, where the source says one thing and another value may fit better (17 entries):

| Body | Used | Why it is doubtful |
|---|---|---|
| Assessor-Recorder-County Clerk, District Attorney, Sheriff | department | Elected offices; `office` may fit |
| Elections, Public Defender, County Counsel | department | `office` may fit |
| Civil Grand Jury | department | A court-appointed body; `committee` or `court` may fit |
| Retirement | department | An independent board; `authority` may fit |
| UC Cooperative Extension | department | A University of California program, not a county unit |
| Tax Collector | department | Its web page sits under Finance, so its public and administrative parent may differ. Kept as a top-level department; not changed. |
| HR: Leaves, Recruitment, Internships and Volunteers, Risk Management | division | Read like functions or programs |
| Office of Emergency Management | office | Not in the master list; real parent unknown, placed under the county |
| County Service Areas 6 and 29 | authority | Data does not say what kind of body they are |

## Left out

None of the 45 master-list entries was left out, though the four HR divisions above are borderline. From the watch list, these were not added:

- Marin Transit: a separate district with its own board and territory. It would need its own jurisdiction and `governmentLevel: specialPurpose`.
- Zero Waste Marin: it may be a program or a joint authority; the data does not say.
- Gnoss Field Airport: a facility.
- Gallinas Creek: a place.

No programs, services, permits or fees were found in the data.

## What schemaGov cannot represent

1. **Retired bodies.** The master list has a `retired` status but no date. `dissolutionDate` needs a date. Option: schema.org `dissolutionDate`. Why not enough: no date in the source. Proposal: record the date when a body is retired.
2. **Administrative parent that differs from the public parent.** For example the Tax Collector, whose page sits under Finance. W3C ORG has no second hierarchy either. Why not enough: only one parent link is allowed. Proposal: use an identifier or a note until a standard way exists.
3. **Order of listing.** The list order is the menu order people see. schema.org has `position` for list items, but it is not a property of an organization. Proposal: keep the order in the app, not the data.
4. **Independence of a body.** The Sheriff, District Attorney, Grand Jury, Retirement board and Library each answer to someone other than the county executive. `organizationClassification` does not say who. Option: Popolo `Organization` links. Proposal: a short note on how to show an elected or independent body.
5. **Service areas.** County Service Areas are funding zones run by the Board. There is no clear term for a body that is a district of its parent. Proposal: guidance on whether to use `authority` or `division`.
6. **Wikidata and other external ids.** Not added, because I could not verify them offline. Marin's Wikidata QID is worth adding.

## Decisions I made that you may want to change

- The official `name` is the master list's name (for example "Sheriff"). The watch list's longer name ("Marin County Sheriff") is an `alternateName`. If you prefer the longer names, swap them in `convert_org.py`.
- California and the United States are included as jurisdictions only so references resolve.

## Notes on the data uploaded to `output/` on 3 November

These are for the data's source to fix. Marin Docs leaves the trailing text off the mission it shows, but does not change the data.

- **Missions end with a name.** In 23 department records the `mission` text ends with the department head's name, and some also end with a phone number or web address (for example "…residents. Joe Deviney"). They look like page text from the budget book that was kept with the sentence.
- **Program classification labels are mis-capitalised.** "County Executive’S Office", "Department Of Finance", "Marin County Sheriff-Coroner’S Office". Six programs have no classification at all.
- **Funds are not linked to anything.** A fund has a name, a code and a description, but no organization, program or amount refers to it, so a department cannot show its funds.
- **A service area and a department share a name.** The Health and Human Services service area contains a department of the same name.

## Notes on the budget codes added on 4 November

- **Budget codes added.** 23 departments now carry `local:marin-budget-department-code` (for example 530 for Cultural Services). The Civil Grand Jury and the Tax Collector have none, and nothing was invented for them.
- **Service area classification.** The five service areas now use `serviceArea`, the value schemaGov's organization code list allows (it was `service-area`). A service area stays a `GovernmentOrganization`; schemaGov has no separate class and schema.org has no closer type.
- **Service areas have an identifier.** schemaGov requires at least one identifier per organization, so each service area carries `local:marin-service-area-id` with its short name (for example `public-safety`).
- **Fund codes do not carry the department code.** Fund codes (1000 to 6620) and department codes (100 to 540) are separate numbering schemes, so a fund cannot be tied to a department from the numbers. The budget book's fund-by-department tables are the source for that link.
- **Report to schemaGov.** The org README's identifier example `erp-org-unit` has no `local:` prefix, so it would fail the profile's own identifier schema.

## Fixes made to the data on 5 November (so it passes schemaGov's validators)

Before: `tools/validate.py` reported 23 errors and `tools/shacl.py` 59 violations. After: both pass on the seven data files.

- **Programs** are typed `Program` (schemaGov has no `GovernmentProgram`), and `administeredBy` is a single reference, as the profile requires.
- **Jurisdictions** are typed `AdministrativeArea` (a place type; `Jurisdiction` is not allowed) and each has an identifier: the Open Civic Data division id for the county, and a local district number for each supervisorial district.
- **The County's `department` and `subOrganization` lists** now name only organizations whose `parentOrganization` is the County. `parentOrganization` is the canonical link.
- `convert_org.py` is superseded by the uploaded files and still writes the old values. Do not run it over `output/`.
- `organizations-with-budget-codes.jsonld` is now out of date and no longer needed; `organizations.jsonld` carries the codes and the other fixes.

## Telephone number cut short

County Counsel's `telephone` is `415-473-61`, which is not a whole number. Marin Docs shows it as plain text, not a `tel:` link. The source needs the full number.

## What the Program Overview shows (5 November)

- **The book repeats a page.** The second Health and Human Services Program Overview page (printed 240) is printed again under the Public Safety heading (printed 241). The extractor reads it once.
- **County Counsel's totals disagree with its own rows.** The service-area table and the Program Overview totals print FY 2026-27 expenditures of 7,394,395. County Counsel's own page and the program rows add to 7,754,395, which also matches the countywide total.
- **Programs under the wrong organization.** County Clerk, Electronic Recording, Recording Operations, Records Modernization, Social Security Number Truncation and Vital Statistics are administered by the Office of the County Executive in `programs.jsonld`, but the Program Overview lists them under the Assessor-Recorder-County Clerk. Property Tax and Tax Collector sit under Finance in the data and under the Assessor in the book. These rows are left unmatched (see `output/qa/ambiguous-matches.json`).
- **Matching.** 234 of the 333 Program Overview rows match one of the 189 programs, 133 by name and 101 through `program-aliases.json`, covering 161 programs. The other rows keep the book's own label as `programClassification`; 28 programs have no row.
- **Funds.** The book groups programs under General Fund, HHS Operations Fund and Other Funds. Only the General Fund is a fund in `funds.jsonld`. The others stay as `fundSource` text.

## Countywide totals (5 November)

The countywide sources and uses and the all funds summary (printed pages 20 and 21) are read: FY 2026-27 expenditures of 902,592,232 and revenues of 855,613,964, with their types. Types add to totals exactly. Non Departmental's programs equal the countywide total less the five service areas to the dollar for FY 2025-26. For FY 2026-27 they differ by 360,000, which is the County Counsel figure in the service-area table (7,394,395 there against 7,754,395 on its own page), a second sign that the service-area table is the stale one.

## Fund names

Fund names in `funds.jsonld` are title-cased by a program: "Hhs Social Services Realignment", "Mcera Employees", "Community Development Block Grant (Cdbg)", "Funds (3440)" for a Measure W fund whose name is only its number. Marin Docs writes HHS, MCERA and CDBG as the County does and leaves the data alone; the names belong fixed at the source.

## Contracts and vendors in Marin Docs (9 November)

`build_contracts_view.py` reads `contracts.jsonld` (5,256 contracts) and `vendors.jsonld` (1,654 vendors) and writes `output/source/contracts-display.json`. 20 placeholder contracts (a name with "Test Contract", or a value of $100 or less) are left out and listed in the file; 5,236 remain, about $892 million.

- `buyer` is always the County. The agency is `tender.procuringEntity`, a four-digit code (73 of them) that matches no organization `@id`. The first two digits match the department's three-digit budget code (1002 is Health and Human Services, 100), so `erp-department-codes.json` maps by prefix. Every contract matches.
- Sub-codes (1001 to 1005, 4001 to 4007) are not matched to divisions yet; they roll up to the department.
- Open Space (65xx), Parks service areas (72xx, 73xx) and 9001 have no organization page. They are shown under their own group names and marked `needsReview` in the crosswalk. Code 6531 is Zero Waste JPA work and may belong elsewhere.
- A contract's value is its amount, not payments. Types (Prof Serv_Other, Trade, HHS_PSC_CBO and so on) are shown as recorded; their meaning is not documented in the data.
- Vendors include individuals, shown by name.

