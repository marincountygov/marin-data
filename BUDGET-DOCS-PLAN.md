# Plan: the FY 2026-28 Budget Book in Marin Docs

Written 5 November. Source: `FY2026-28 June Budget Book - FINAL including CC BOS 06-08-26 revision -7-14-26.pdf` (Desktop). This plan replaces the "give it to ChatGPT" approach. It builds on `BUDGET-PLAN.md` (data rules) and uses what the book actually contains.

Page numbers below are the printed ones. The PDF page is the printed number plus 2.

## What the book contains

| Content | Printed pages | Years | Shape |
|---|---|---|---|
| Sources and uses, all funds summary | 20-21 | FY25-26 approved, FY26-27 proposed (the book also prints FY27-28 planned; not used) | Countywide revenue and expenditure by type |
| Service area overview | 71, 81, 123, 179, 197 (tables); 230 Non Departmental | FY24-25 actual, FY25-26 approved, FY26-27 proposed, change, FTE | **Expenditures only**, one row per department or division, with a total |
| Department budget (23 departments) | 72-227 | FY25-26 approved, FY26-27 proposed (planned column not used) | Mission, overview, revenue and expenditure by type, net County cost, written explanation of changes, priorities, FTE by program |
| Program Overview | 238-263 | FY25-26 approved, FY26-27 proposed only | Per department, per program: expenditures, revenues, net County cost, grouped by **fund bucket** |
| FTE by department | 266-291 | adopted, modified, proposed (planned column not used) | Job classification (with code) and FTE, with department totals |
| FTE by fund | 293 | same | One row per fund |
| Program and fund descriptions | 296-318 | n/a | Already in `programs.jsonld` and `funds.jsonld` |
| Schedule 2, appropriations by fund | 233-235 | FY26-27 | Scanned images, no text |

## What this means for the data

These are findings from reading the tables. They change the earlier plan.

1. **Service-area tables are expenditure only.** Revenue and net County cost come from the department pages and the Program Overview.
2. **Actuals exist only at service-area level** (FY24-25). Department and program tables start at FY25-26 approved.
3. **FY27-28 "planned" is left out entirely.** It is not in the graph and not on any page (decision, 5 November).
4. **The service-area rows are not all departments.** In Health and Human Services the rows are its divisions (Behavioral Health and Recovery Services, Public Health Services and so on), and those exist in our organization data. Others are departments. "Emergency HHS" and "General Administration" need a decision.
5. **Funds are grouped, not listed.** The Program Overview groups each department's programs under "General Fund", "HHS Operations Fund" or "Other Funds". "Other Funds" is not a Fund entity, so those lines carry `fundSource: "Other Funds"` as text. Only General Fund and HHS Operations Fund can be `fund` references. This is a real limit on "program to fund" and on the department Budget tab.
6. **Program names are in capitals and abbreviated** ("COMM DISEASE AND PH LAB", "HHS GENERAL ADMINISTRATION") and wrap across lines. Matching to the 189 programs needs the department as context and a hand-checked alias list.
7. **Revenues print as negative numbers in brackets.** The data stores the positive amount with `direction: "revenue"`.
8. **The book gives its own check totals.** Service-area total equals the sum of its rows. A department's "Total All Funds" equals the sum of its program rows. Department totals roll into the service-area table and the countywide $902.6 million. The extractor fails if any of these do not add up.
9. **Edition.** This is the final edition (decision, 5 November), including the Board's 8 June 2026 revision. The printed column headings still read "Proposed". The graph records FY26-27 as `approved`, and pages show the book's own column heading with a note on the edition. `adoptedBy`, `enactedAt` and `legislation` stay off until the book or an ordinance names them.
10. **Net County cost, change columns and FTE** are derived or have no schemaGov home. They are kept in a separate display file (below), not in the graph.

## Data

Built in `marin-data/` by a deterministic extractor (`extract_budget.py`), not by hand and not by AI summarising. It reads the PDF text layer and writes, with printed page numbers kept on every row:

- `output/budgets.jsonld`: one Budget per fiscal year and phase (FY24-25 `executed`, FY25-26 `approved`, FY26-27 `approved`; no FY27-28).
- `output/budget-lines.jsonld`: lines linked with `administrativeClassification`, `program`, `fund`, `hasPart` and `isPartOf`.
- `output/source/budget-display.json`: what the pages need but schemaGov cannot hold: net County cost, change columns, FTE per row, source page per row, prose from "Description of budget changes".
- `output/source/staffing-source.json`: FTE by department, job classification and fund.
- `output/qa/*.json`: unmatched, ambiguous and unsupported items.

Run in layers, each checked before the next: (a) countywide, (b) service-area rows, (c) department summaries, (d) Program Overview, (e) FTE. Stop for review after (c).

Prerequisite: the existing data fixes from `BUDGET-PLAN.md` step 3 (program type `Program`, jurisdiction types, the County's `department` list). Without them the new data cannot pass the validators.

## Marin Docs

The pages are written at build time as plain HTML tables, so they work without JavaScript. Charts reuse the shell's `data-chart` component where one helps. New table styles (right-aligned numbers, totals, negative values) should go into `marin-ui` first, then the shell, then Docs, as with the card styles.

### A. Budget section (`budget/`)
- **Overview:** key numbers ($902.6M expenditure, revenue, net County cost, FTE) and the sources-and-uses and by-type tables for the three years.
- **Service areas:** the five areas side by side for FY24-25 to FY26-27, with a share chart.
- **Departments:** one table of every department's proposed expenditure, revenue, net County cost and FTE, each linking to its department page.
- **Funds:** the existing funds page, plus FTE by fund where the names match.
- **Staffing:** FTE by department, with the job-classification tables on the department pages.
- **Data and source:** the book's title, the pages used, downloads of the JSON-LD and display files.

### B. Organization page: Budget tab
Shown for the 23 departments and, in a smaller form, for divisions that have rows. Sub-tabs, like the app tabs:
- **Budget:** key numbers; revenues and expenditures by type for the FY25-26 and FY26-27 columns; net County cost; the book's written explanation of changes with its page; a programs table with proposed expenditure, revenue and net County cost, each linking to the program page.
- **Staffing:** FTE for the four columns and the job classifications. These are workforce data, not People or Posts.

The tab is shown only when a department has data. The Civil Grand Jury and the Tax Collector (no budget code) are matched by name or have no tab.

### C. Service area page: Budget tab
Tabs become Programs, Budget and Data. Budget shows the book's overview table (actual, approved, proposed, change, FTE) with each row linking to its department or division, a total, and a stacked chart. The Programs tab gains a spend column.

### D. Program page: Budget tab
Tabs become Overview, Budget and Data. Budget shows approved and proposed expenditures, revenues and net County cost for each fund bucket the program uses. A program with several buckets shows several rows, never a merged one. Where the fund is a named Fund, the row links to it. A note says that "Other Funds" is how the book groups them.

### E. Fund pages
Today funds are cards on one page. Add a page per fund only when there is more than a description to show (General Fund and HHS Operations Fund have program lines; every fund has an FTE row). Otherwise keep the cards.

## Tying it together

1. **Follow the money.** Each program page shows its path: service area, department, program, fund bucket, with the amount at each level. The same path appears in the breadcrumb.
2. **One join key.** The budget department code (and for divisions, the organization `@id`) joins budget, organization, Reach, Mentions and Links. Docs never matches on names where a code exists.
3. **Every figure is traceable.** Each table has a source note with the book's printed page, and the Data tab lists them. If the book has a public URL, link to the page (`#page=N`). I need that URL.
4. **Cross-links both ways.** Department page to its programs and funds; program to its department, service area and funds; fund to the programs and departments that draw on it; service area to its departments.
5. **Home and search.** Add the budget figures to the Docs search index. Show the Budget card with the headline number.
6. **Procedures and apps.** The Procedures, Mentions, Links and Reach tabs sit beside Budget on a department page, so one page answers who runs it, what it spends, what is said about it and which procedures apply.
7. **Checks.** Build tests: every table's total equals the sum of its rows, every page cited exists, no page shows a number without a source page, the new files stay out of pages when empty.

## Order of work

1. Fix the existing data (prerequisite).
2. Extractor, layers (a) to (c), then **checkpoint**: Budget entities, service-area and department lines, check totals, validator output.
3. Docs: Budget section overview, service areas and departments pages, and the organization Budget tab. **Checkpoint.**
4. Extractor layer (d), program matching with an alias list. Review the ambiguous matches with you.
5. Docs: service area Budget tab, program Budget tab, fund buckets.
6. Extractor layer (e), staffing. Docs: Staffing sub-tab and Budget staffing page.
7. Cross-links, search, tests, README, FINDINGS notes. Release in the usual order (marin-ui, shell, docs).

## Decisions (5 November)

1. FY27-28 "Planned" is not added, to the graph or the pages.
2. The book is the final edition. FY26-27 is recorded as `approved`; pages keep the book's printed headings with a note.
3. Public link, used for page links (`#page=N`) and recorded in `sources.json`:
   https://assets.marincounty.gov/marincounty-prod/public/2026-07/FY2026-28%20June%20Budget%20Book%20-%20FINAL%20including%20CC%20BOS%2006-08-26%20revision%20-7-14-26.pdf?VersionId=5vgbSpl5kGRt2S6xwEhVGwSBV266zmcz
4. "Other Funds" is recorded as text (`fundSource`); only named funds are `fund` references.
5. Job classifications and FTE by department may be shown publicly on department pages.
6. Rows that are not organizations ("Emergency HHS", "General Administration") appear on service-area pages as budget rows without a link.

## Still open

- The URL carries a `VersionId`. If the County replaces the file, the link may stop matching the book we read. A link without it, if one exists, is more stable.

## Checkpoint 1 result (5 November)

Built by `extract_budget.py` (layers: service-area tables and department pages). Both schemaGov validators pass on the seven data files plus `budgets.jsonld` and `budget-lines.jsonld`.

- 3 Budgets (FY24-25 executed, FY25-26 approved, FY26-27 approved) and 462 lines.
- **The book disagrees with itself once.** County Counsel's FY26-27 expenditure is 7,394,395 in the Administration and Finance table but 7,754,395 on its own page (and its cost types add to 7,754,395). The department page agrees with the countywide total; the service-area table is $360,000 low. Both figures are kept as printed, the department-page figure as its own line.
- Two FY24-25 service-area totals are $1 off from their rows (rounding in the book).
- "Emergency HHS" has no organization; its line has no administrativeClassification.
- Non Departmental, the Open Space District (code 659, not in our organizations) and the Civil Grand Jury and Tax Collector are not covered yet.

## Plan: Chart.js charts for the budget figures

Written 5 November. Nothing here is built yet.

### What exists
The shell's `[data-chart]` component draws Chart.js cards from a JSON file: a **line** (records per day or month) or a **bar** (ranks the values of one field, horizontal, one series, counts or `data-sum`). It loads Chart.js lazily from the page's own copy (`vendor/chart.min.js`, already in Docs) when the chart is first shown, and gives the canvas a text summary.

### What the budget needs that it lacks
1. **Bars of amounts**, one bar per category, not a count of records.
2. **Several series side by side** (FY 2025-26 against FY 2026-27) and **stacked** bars (departments inside a service area, over three years).
3. **Dollar formatting**: axis in millions ($25M), tooltips and the screen-reader text in whole dollars, a minus sign for decreases.
4. **Data that is already on the page.** The numbers come from the build, not from a service, so the chart should read a small JSON block in the page (`<script type="application/json">`), not make a request. The chart and its table then come from the same figures.

### Extension to the component (in `marin-ui`, then the shell, then Docs)
New attributes on `[data-chart]` (names to be settled when built):
- `data-src="#id"` reads a JSON script block in the page.
- `data-kind="columns"` (vertical) and the existing `bar` (horizontal), each with `data-series` (the series field), `data-label` (the category field), `data-value` (the amount field), and `data-stacked`.
- `data-format="currency"` (and `data-format="number"` for FTE).
- Keeps the existing rules: `data-chart-title`, `data-empty-text`, the text summary of the biggest value, colors from the page's tokens.

Tests follow the record-list pattern: `tests/browser_record_list.py` with the Chart.js stand-in, plus the shell's own checks. The change is a new minor version of `marin-ui` and the shell, released in the usual order (marin-ui, shell, Docs).

### Charts, by page
| Page | Chart | Kind | From |
|---|---|---|---|
| Department Budget tab | Where the money goes: expenditure by type, FY 2026-27 | horizontal bar | by-type lines |
| Department Budget tab | Revenues, expenditures and net County cost, FY 2025-26 against FY 2026-27 | columns, two series | totals and the book's net County cost |
| Department Budget tab | Expenditures over three years (actual, approved, FY 2026-27) | columns | service-area row lines |
| HHS Budget tab | Expenditures by division over three years | stacked columns | division rows |
| Budget: service areas | Each area's expenditure over three years, departments stacked | stacked columns, one per area | service-area tables |
| Budget: departments | FY 2026-27 expenditure by department | horizontal bar | department totals |
| Budget index | The five service areas compared | horizontal bar | service-area totals |
| Service area page (later) | Its departments over three years | stacked columns | same as above |
| Program pages (after Program Overview) | Expenditure, revenue and net County cost by fund group | grouped bars | program lines |

The Dashboard keeps the four key numbers only. A chart there would be one more thing to load for little extra meaning.

### Rules for every chart
- **The table stays.** Each chart sits above or beside its table, which carries every number. The chart is a second way in, never the only one.
- **Plain, honest charts:** bars and columns only, a zero baseline, no pie or doughnut charts. A decrease shows as a negative bar, never hidden.
- **Not color alone:** series are named in the legend and in the table headings, and values are labeled on the bars where there is room.
- **Colors** follow the dataviz skill's validated palette and the page's light and dark tokens.
- **Screen readers:** each canvas names the chart and states the result ("Salaries and Benefits is the largest at $17.9 million of $25.1 million").
- **Same figures as the table:** a build test compares the chart data to the table rows, and the existing sum checks still apply.
- **Loaded when shown:** Chart.js and the chart data are fetched or drawn only when the tab is opened.

### Order of work
1. Extend the component, with tests and the docs (`marin-ui/docs/components.md`, "Charts").
2. Build the chart data beside the tables in `budget-data.js`, and add the department charts.
3. Add the Budget section and HHS division charts.
4. After the Program Overview extraction, add the program charts.

### Decisions (5 November)
1. Charts go above the tables.
2. Vertical columns are fine for time comparisons.
3. Net County cost is its own series in the revenue and expenditure chart.
