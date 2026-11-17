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
| `organizations/monitors-not-organizations.json` | Watched names that are not County organizations, with the reason | By hand | marin-mentions |
| `organizations/aliases.json` | Other names for organizations, such as CDA | Generated | marin-reach |
| `organizations/index.json` | A short list of every organization: id, name, other names, type and parent | Generated | marin-os |
| `output/sources.json` | The older shape of `sources.json` that some app scripts still read | Generated | marin-budget, marin-docs |
| `brand/<slug>/` | Each brand's `brand.json` and its logo and picture files | By hand | marin-brand |
| `schemas/`, `templates/` | The shapes of `sources.json` and `brand.json`, and a blank brand to copy | By hand | marin-brand |
| `consumers.json` | Which app copies which files, and how to update it | By hand | The scripts in this repo |

The files marked "Generated" are never edited by hand. Change what they come from, then run `bash scripts/build.sh`.

## Common changes

**Change an agency** (name, web page, code, parent): edit it in `organizations/agencies.json` and on its record in `output/organizations.jsonld`. Never rename or reuse an id. `check_orgs.py` fails until the two agree.

**Add an organization that is not on the agencies list** (a unit that apps name but that has no web page or code yet): add a record to `output/organizations.jsonld`. Copy a similar one. It needs a name, a classification, `areaServed`, a `parentOrganization`, and an `identifier` (use `gs:local` with the slug if no app has one). Then list it in its parent's `department` (or `subOrganization`) list. Do not add it to `organizations/agencies.json` unless it should appear in the agency picker in marin-links. Run `bash scripts/build.sh`. The schemaGov check fails if the record is incomplete.

**Add another name for an organization**, such as an acronym: add it to `alternateName` on its record in `output/organizations.jsonld`. Then run `bash scripts/build.sh`. A name that fits two organizations is left out and listed as ambiguous.

**Watch a new department in marin-mentions:** give its record in `output/organizations.jsonld` an identifier named `local:marin-mentions-monitor-id` with the monitor's id. If the monitor is not a County organization, add it to `organizations/monitors-not-organizations.json` with a reason. Then run `bash scripts/build.sh`.

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

GitHub also checks the JSON-LD against the schemaGov validators. To do the same here, with a clone of schemaGov (https://github.com/govfresh/schemaGov): `python3 -m pip install -r requirements-schemagov.txt`, then `python3 check_schemagov.py ../path/to/schemaGov`. The packages matter: without them the validators skip checks and still say they passed, so the script fails when it sees a skipped check. It fails on any error. The GitHub job uses a fixed schemaGov version, set in `.github/workflows/check.yml`.

## How the apps get the data

An app never edits a copy. `consumers.json` lists each app, the files it copies, and the commands that update it.

- **Daily:** each app (marin-links, marin-mentions, marin-reach, marin-docs, marin-budget and marin-brand) has a Data sync workflow that runs once a day. If something it copies has changed, it updates its copies, rebuilds its pages, runs its checks, and pushes a branch called `data-sync`. The run summary has the link to review it. It never merges anything.
- **Right away:** open the app's Actions tab, choose Data sync, and choose Run workflow.
- **Pinned version:** each app has a `marin-data.lock` file naming the version of this repo it last used. Its checks use that version, so a change here cannot turn an app's checks red before the app is updated. `bash scripts/lock.sh ../<app>` records the current version after a sync. This repo must be merged and clean first.
- **Check one app by hand:** `python3 check_copies.py ../marin-docs`.

## Retired and leftover

- `convert_org.py` and `tests/` made the first version of the organization data. Do not run them. The organization data is now kept by hand. `FINDINGS.md` explains why.
- `BUDGET-PLAN.md`, `BUDGET-DOCS-PLAN.md` and `CIP-PLAN.md` are design notes for the budget and capital extracts.
