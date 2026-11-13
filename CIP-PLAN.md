# Plan: the FY 2027-31 Capital Improvement Plan (CIP) in Marin Docs

Source: `4_-_ATTACHMENT_E_FY_2027-31_CIP_BOOK.pdf` (Desktop), 27 pages. Prototype first in marin-data, then a top-level
CIP section in marin-docs, then the schemaGov proposal.

## What the book contains

| Content | Pages | Shape |
|---|---|---|
| CIP revenues and expenses by fund source | 19 | 12 sources, five years and a total, text |
| Project totals by category | 21 | Five groups, seven subcategories, five years, additional funds needed |
| Project tables | 24-27 | 226 projects: status (New or Ongoing), cost estimate, prior approvals, FY27 proposed, FY28-31 programmed, total funding, additional funds needed |
| Narrative, maps and photos | 1-18, 20, 22-23 | Images. Not read. Project descriptions and locations may be here. |

## What the prototype does (`extract_cip.py`)

Writes to `output/cip/`: `cip-projects.jsonld`, `cip-budgets.jsonld` (one per fiscal year, FY 2026-27 proposed and
FY 2027-28 to 2030-31 planned), `cip-budget-lines.jsonld` (one line per project per year, plus fund-source lines),
`source/cip-display.json` (category, CIP status, prior approvals, additional funds needed, page) and `qa/cip-checks.json`.

Checks, all against figures the book prints: every project row (prior + five years = total funding; total funding +
additional needed = cost estimate), every subcategory subtotal, the fund-source tables, and the page 21 category table.

## Known limits

- **One discrepancy in the book itself.** The Civic Center rows add up to $500,000 more prior approvals, $1,750,000 more
  in FY27 and $2,250,000 less in FY28 than the printed Civic Center subtotal. Every row is internally consistent, so
  this is not a parse error. It carries into the page 21 year totals for FY27 and FY28. The data keeps the rows as
  printed. Ask the County which is right before publishing the subtotal.
- **No department per project.** The tables name a category, not a responsible department. Nothing is inferred, so
  projects carry no `parentOrganization`. If the image pages name one, read them (OCR is installed) or ask the County.
- **No fund per project.** Fund sources exist only in aggregate (page 19) and are kept as `fundSource` text. They are
  not mapped to Fund entities because the book does not say which County fund each one is.
- **Status is the book's, not a lifecycle.** "New" and "Ongoing" are the book's labels; the book does not define them.
  They are not mapped to schemaGov `status` or `phase`.

## Proposed schemaGov changes (not made)

1. `BudgetLine.project`: optional reference to a `Project`. The prototype already uses it, so its output does not yet
   validate against the published schema.
2. A place for project category and CIP status. The prototype keeps them in `cip-display.json`. Candidates: a
   `DefinedTermSet` of categories, or reuse `phase` with a Marin capital scheme.
3. Project `location` (`Place` or `Facility`), only if the image pages give locations.

## Done since the first prototype

- **Image pages read with OCR.** They are narrative: the County Executive's message, the overview, the approval process,
  funding discussion and category write-ups. They carry no per-project department, location or description, so
  projects stay as the tables give them. The book's text says 227 projects; its tables list 226.
- **marin-budget section built** (`marin-budget/scripts/build-capital.js`, top level `capital/`): a landing page, a projects page by
  category and a page for each of the 226 projects. It is tied to Budget by a card on the Budget page, a Capital plan
  link on the capital funds (1420, 1430, 1680, 1720). A comparison with the budget book's capital lines was built and
  then removed, because it mixed the plan with one year of the budget.

## Next

1. Ask the County about the Civic Center subtotal and, if they have it, which department and fund each project belongs to.
2. Write the schemaGov plan file: `BudgetLine.project`, a place for category and CIP status, project `location`.
3. Optional: an Insights tab and filters on the projects page; link each project to a department once the County says which.
