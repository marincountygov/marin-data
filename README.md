# marin-data

The shared County of Marin data that the Marin apps use. The data is kept here, once. The apps read it. They do not keep their own master copies.

Published at https://marincountygov.github.io/marin-data/. Every file in this repo is public.

## What is here

| Path | What it holds | How it changes | Used by |
|---|---|---|---|
| `sources.json` | The source documents (budget books, the CIP book, the style guide) with a link, an edition and a fingerprint for each | By hand | marin-budget, marin-docs (through `output/sources.json`) |
| `organizations/agencies.json` | The master list of County agencies, departments and divisions: ids, codes, names, web pages, menu order | By hand | marin-links |
| `output/organizations.jsonld` | The full record for each organization, in schemaGov JSON-LD. The same folder holds `jurisdictions`, `programs`, `people`, `posts` and `roles` | By hand, and by the budget extract | marin-docs, marin-budget |
| `output/budgets*.jsonld`, `budget-lines*.jsonld`, `funds*.jsonld`, `output/cip/`, `output/budget-2025-26/` | The budget and capital plan figures | Generated from the books by the `extract_*.py` scripts | marin-budget, marin-docs |
| `organizations/monitors.json` | Which organization each watched department is about | Generated | marin-mentions |
| `organizations/place-kinds.json` | The kinds of place, facility and event, and the singular and plural name every app uses for each | By hand | marin-mentions, marin-docs, marin-links |
| `organizations/places.json` | Which jurisdiction (district, city or town, community) or facility each watched place is about | Generated | marin-mentions |
| `organizations/facilities.json` | Every facility and venue, with address, coordinates and who runs it (government, nongovernment, unknown) | Generated | marin-reach |
| `organizations/locations.json` | The places and sites people can name in a tracked link, each with a permanent code | Generated | marin-links |
| `organizations/people.json` | Which person each watched person is about, with their seat and district | Generated | marin-mentions |
| `organizations/events.json` | Which event each watched event is about | Generated | marin-mentions |
| `organizations/monitors-not-places.json` | Watched place names that are not jurisdictions, with the reason | By hand | marin-mentions |
| `organizations/monitors-not-organizations.json` | Watched names that are not County organizations, with the reason | By hand | marin-mentions |
| `organizations/aliases.json` | Other names for organizations, such as CDA | Generated | marin-reach |
| `organizations/place-aliases.json` | Other names for each place (such as `D3` for District 3), and the name an app shows for it | Generated | marin-reach |
| `projects/projects.json` | The projects and campaigns the apps show: each with a Links campaign code, and whether Reach lists it and Mentions watches its name | By hand | marin-links, marin-reach, marin-mentions |
| `organizations/index.json` | A short list of every organization: id, name, other names, type and parent | Generated | marin-os |
| `output/sources.json` | The older shape of `sources.json` that some app scripts still read | Generated | marin-budget, marin-docs |
| `brand/<slug>/` | Each brand's `brand.json` and its logo and picture files | By hand | marin-brand |
| `schemas/`, `templates/` | The shapes of `sources.json` and `brand.json`, and a blank brand to copy | By hand | marin-brand |
| `consumers.json` | Which app copies which files, and how to update it | By hand | The scripts in this repo |

The files marked "Generated" are never edited by hand. Change what they come from, then run `bash scripts/build.sh`.

## Common changes

**Change an agency** (name, web page, code, parent): edit it in `organizations/agencies.json` and on its record in `output/organizations.jsonld`. Never rename or reuse an id. `check_orgs.py` fails until the two agree.

**Add a project:** add an entry to `projects/projects.json`. Give it an `id` (permanent), a `name`, and only the apps that should show it:
- `links` with a new permanent `code` (the next `cmp-NN`) and `legacy: []`, to show it as a campaign in Marin Links.
- `reach: true`, to list it in the Project filter in Marin Reach. It shows with a count of 0 until it has engagements.
- `mentions` with `include`, the phrases Marin Mentions watches for. Use the exact project name.

Never reuse or renumber a code. Run `python3 check_projects.py`. The apps pick it up on their next scheduled update, or run Data sync in each one. An engagement in Marin Reach for a project that is not in this list fails its build.

**Add an organization that is not on the agencies list** (a unit that apps name but that has no web page or code yet): add a record to `output/organizations.jsonld`. Copy a similar one. It needs a name, a classification, `areaServed`, a `parentOrganization`, and an `identifier` (use `gs:local` with the slug if no app has one). Then list it in its parent's `department` (or `subOrganization`) list. Do not add it to `organizations/agencies.json` unless it should appear in the agency picker in marin-links. Run `bash scripts/build.sh`. The schemaGov check fails if the record is incomplete.

**Add another name for an organization**, such as an acronym: add it to `alternateName` on its record in `output/organizations.jsonld`. Then run `bash scripts/build.sh`. A name that fits two organizations is left out and listed as ambiguous.

**Watch a new department in marin-mentions:** give its record in `output/organizations.jsonld` an identifier named `local:marin-mentions-monitor-id` with the monitor's id. If the monitor is not a County organization, add it to `organizations/monitors-not-organizations.json` with a reason. Then run `bash scripts/build.sh`.

**Watch a new place in marin-mentions:** add a record to `output/jurisdictions.jsonld` (a `City` for an incorporated place, otherwise an `AdministrativeArea`, contained in the county, with a `governmentLevel`) and give it an identifier named `local:marin-mentions-monitor-id` with the monitor's id. If the monitor is not a territory, add it to `organizations/monitors-not-places.json` with a reason. Then run `bash scripts/build.sh`.

**Watch a new person in marin-mentions:** give their record in `output/people.jsonld` an identifier named `local:marin-mentions-monitor-id` with the monitor's id. Their seat comes from their role in `output/roles.jsonld`. Then run `bash scripts/build.sh`.

**Say which district a place is in:** on the place's record in `output/jurisdictions.jsonld`, add `geoWithin` (the whole place is in one district) or `geoOverlaps` (a list of districts, when the place is partly in each), pointing at the district's `@id`. Then run `bash scripts/build.sh`. `organizations/places.json` then lists each place's `districts` with a relation of `within` or `overlaps`. The first lists were taken from the district monitors in marin-mentions (Ignacio, Las Gallinas and Seadrift are in none of them, so they have no district yet).

**Watch a new facility or event in marin-mentions:** add a record to `output/facilities.jsonld` (a `GovernmentBuilding`, `EventVenue`, `CivicStructure`, or plain `Place`) or to `output/events.jsonld`, with an identifier named `local:marin-mentions-monitor-id` holding the monitor's id. Every facility also needs `local:operator-type` (in `additionalProperty`): `government`, `nongovernment`, `unknown` or `notApplicable`. A venue Reach uses needs no monitor. Then run `bash scripts/build.sh`.

**Add or replace a source document:** add a record to `sources.json`.
- If the County posts it publicly, set `url` and leave `file` empty. Do not store the file here.
- If it is not public, set `"access": "internal"` with no `url` and no `file`. Never link it from a public page.
- Get the fingerprint with `shasum -a 256 <file>` and the size in bytes. Then run `bash scripts/build.sh`.

**Change or add a brand:** edit `brand/<slug>/brand.json` and put the files it names in `brand/<slug>/assets/`. To start a new brand, copy `templates/brand.template.json`. Run `python3 check_brand.py`. It fails if `brand.json` names a file that is missing, or a file is not named.

**Read a new budget book:** download it from its link in `sources.json`, then run the extract script, for example `python3 extract_budget.py BOOK.pdf`. The scripts need `pypdf`. They write into `output/` and check their numbers against the totals the book prints.

## Check before you commit

```sh
bash scripts/build.sh    # remakes every generated file
bash scripts/check.sh    # checks the data and that every generated file is current
```

`check.sh` needs only Python 3. It also runs in GitHub on every push and pull request.

It also compares the list of projects with the version on `main`, and fails if a project was removed, a Links code changed, or an older Links value was dropped. Those are permanent, because past links in Marin Links Stats depend on them. Run `git fetch origin main` first so the comparison can run.

GitHub also checks the JSON-LD against the schemaGov validators. To do the same here, with a clone of schemaGov (https://github.com/govfresh/schemaGov): `python3 -m pip install -r requirements-schemagov.txt`, then `python3 check_schemagov.py ../path/to/schemaGov`. The packages matter: without them the validators skip checks and still say they passed, so the script fails when it sees a skipped check. It fails on any error. The GitHub job uses a fixed schemaGov version, set in `.github/workflows/check.yml`.

## How the apps get the data

An app never edits a copy. `consumers.json` lists each app, the files it copies, and the commands that update it.

- **Scheduled:** each app (marin-links, marin-mentions, marin-reach, marin-docs, marin-budget, marin-brand and marin-os) has a Data sync workflow that runs every hour. GitHub starts scheduled runs late and skips many of them, so it asks often; a run with nothing to do takes about 20 seconds. If something it copies has changed, it updates its copies, rebuilds its pages, runs its checks, and pushes a branch called `data-sync`. The run summary has the link to review it. It never merges anything.
- **Right away:** open the app's Actions tab, choose Data sync, and choose Run workflow.
- **Pinned version:** each app has a `marin-data.lock` file naming the version of this repo it last used. Its checks use that version, so a change here cannot turn an app's checks red before the app is updated. `bash scripts/lock.sh ../<app>` records the current version after a sync. This repo must be merged and clean first.
- **Check one app by hand:** `python3 check_copies.py ../marin-docs`.

## Retired and leftover

- `convert_org.py` and `tests/` made the first version of the organization data. Do not run them. The organization data is now kept by hand. `FINDINGS.md` explains why.
- `BUDGET-PLAN.md`, `BUDGET-DOCS-PLAN.md` and `CIP-PLAN.md` are design notes for the budget and capital extracts.
