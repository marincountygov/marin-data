#!/usr/bin/env python3
"""Extracts the County of Marin FY 2027-31 Capital Improvement Plan (CIP) book into schemaGov JSON-LD.

    python3 extract_cip.py CIP_BOOK.pdf [OUTPUT_DIR] [--cache PAGES.pkl]

Reads the text tables only: CIP revenues and expenses by fund source (printed page 19), project totals by category
(page 21) and the project tables (pages 24-27). The other pages are images and are not read. Nothing is inferred:
the tables name no responsible department and no fund per project, so the projects carry neither.

Writes cip-projects.jsonld, cip-budgets.jsonld, cip-budget-lines.jsonld, source/cip-display.json and
qa/cip-checks.json in OUTPUT_DIR (default: ./output/cip). Every project row is checked against its own printed
totals, every group against its printed subtotal, and the groups against the page 21 and page 19 totals.

The BudgetLine `project` property is PROPOSED for schemaGov and is not yet in its schema or context. It is used
here to prototype the link; see CIP-PLAN.md.
"""
import json
import re
import statistics
import sys
from datetime import date
from pathlib import Path

BASE = 'https://marincountygov.github.io/marin-data/id/'
CONTEXT = 'https://schema.govfresh.com/v1/context.jsonld'
OFFSET = 0  # printed page number = PDF page number (the book's pages are numbered "PROPOSED CIP | n")
TODAY = date.today().isoformat()
COUNTY = BASE + 'organization/county-of-marin'
JURISDICTION = BASE + 'jurisdiction/us-ca-marin'

YEARS = ['2026-27', '2027-28', '2028-29', '2029-30', '2030-31']
YEAR_DATES = {y: (f'{y[:4]}-07-01', f'20{y[-2:]}-06-30') for y in YEARS}
# The first year is "Proposed"; the rest are "Programmed".
PHASE = {y: ('proposed' if i == 0 else 'planned') for i, y in enumerate(YEARS)}
FIELDS = ['cost', 'prior'] + [f'fy{y[-2:]}' for y in YEARS] + ['total', 'needed']

NUMTOK = re.compile(r'(\(?-?[\d,]*\d\)?|-)\s*\$')
STATUS = re.compile(r'^(.*?)\s*(Ongoing|New)\s*(?=[\d(\-])')


def read_pages(pdf, cache):
    if cache and Path(cache).exists():
        import pickle
        return pickle.load(open(cache, 'rb'))
    from pypdf import PdfReader
    pages = {i: p.extract_text(extraction_mode='layout') or '' for i, p in enumerate(PdfReader(pdf).pages, 1)}
    if cache:
        import pickle
        pickle.dump(pages, open(cache, 'wb'))
    return pages


def num(t):
    t = t.strip()
    if t == '-':
        return 0
    neg = t.startswith('(')
    v = int(t.strip('()').replace(',', ''))
    return -v if neg else v


def tokens(line):
    """(label, [(end position, value)]) for a table line: the text before the first figure, then each figure."""
    ms = list(NUMTOK.finditer(line))
    if not ms:
        return line.strip(), []
    return line[:ms[0].start()].strip(), [(m.end(1), num(m.group(1))) for m in ms]


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower().replace('&', 'and')).strip('-')


def calibrate(lines, width):
    """Right edge of each of the `width` columns, from the lines that print every column."""
    full = [t for _, t in (tokens(l) for l in lines) if len(t) == width]
    if not full:
        return None
    return [statistics.median(row[i][0] for row in full) for i in range(width)]


def assign(toks, edges):
    """Place each figure in the nearest column. Blank cells stay None. Two figures in one column is an error."""
    # Figures keep their left-to-right order, so choose strictly increasing columns that minimise the total distance
    # to the column edges. Blank cells are the columns left over.
    n, m = len(toks), len(edges)
    if n > m:
        raise ValueError('more figures than columns')
    INF = float('inf')
    best = [[INF] * (m + 1) for _ in range(n + 1)]  # best[i][j]: first i figures placed in the first j columns
    for j in range(m + 1):
        best[0][j] = 0
    for i in range(1, n + 1):
        for j in range(i, m + 1):
            best[i][j] = min(best[i][j - 1], best[i - 1][j - 1] + abs(edges[j - 1] - toks[i - 1][0]))
    out = [None] * m
    i, j = n, m
    while i > 0:
        if best[i][j] == best[i][j - 1]:
            j -= 1
        else:
            out[j - 1] = toks[i - 1][1]
            i, j = i - 1, j - 1
    return out


def consistent(cells):
    c = [x or 0 for x in cells]
    return c[0] == c[7] + c[8] and c[1] + sum(c[2:7]) == c[7]


def resolve(toks, edges):
    """Nearest-column placement, unless the row's own arithmetic fails: then the placement that satisfies it
    (cost estimate = total funding + additional needed; total funding = prior approvals + the five years)."""
    from itertools import combinations
    cells = assign(toks, edges)
    if consistent(cells) or len(toks) >= len(edges):
        return cells
    options = []
    for cols in combinations(range(len(edges)), len(toks)):
        cand = [None] * len(edges)
        for c, (pos, val) in zip(cols, toks):
            cand[c] = val
        if consistent(cand):
            options.append((sum(abs(edges[c] - t[0]) for c, t in zip(cols, toks)), cand))
    return min(options, key=lambda o: o[0])[1] if options else cells


def parse_projects(pages):
    """Project rows and group totals from the PDF pages that carry them (24-27)."""
    projects, totals, problems = [], [], []
    group = sub = None
    for pg in (24, 25, 26, 27):
        lines = pages[pg].split('\n')
        edges = calibrate(lines, 9)
        if not edges:
            problems.append(f'page {pg}: no full rows to calibrate columns')
            continue
        for raw in lines:
            line = raw.rstrip()
            if not line.strip():
                continue
            label, toks = tokens(line)
            s = line.strip()
            if s == 'Special Projects - Miscellaneous':  # a subcategory of Special Projects, not the group heading
                sub = s
                continue
            hm = re.match(r'^(Facilities|Public Safety|Water Resources|Transportation|Special) Projects\b', s)
            if hm and not toks:  # the heading can share a line with the column headers
                name = hm.group(1) + (' Projects' if hm.group(1) == 'Special' else '')
                if name != group:  # the same heading repeats when a table continues on the next page
                    group, sub = name, None
                continue
            if not toks:
                m = re.match(r'^(Facilities|Public Safety|Water Resources|Transportation|Special) Projects$', s) or \
                    re.match(r'^Special Projects$', s)
                if m:
                    group, sub = s.replace(' Projects', ''), None
                elif s in ('Special Projects - Miscellaneous', 'Studies/Assessments'):
                    sub = s
                elif re.match(r'^[A-Za-z/& \-]+ Projects$', s) and s not in ('Project Status',):
                    sub = s.replace(' Projects', '')
                continue
            if 'Total' in label and not STATUS.match(line.strip()):
                try:
                    totals.append({'label': label, 'page': pg, 'group': group, 'sub': sub, 'cells': assign(toks, edges)})
                except ValueError as e:
                    problems.append(f'page {pg}: {e}: {s[:80]}')
                continue
            m = STATUS.match(line.strip())
            if not m:
                problems.append(f'page {pg}: unreadable row: {s[:80]}')
                continue
            try:
                cells = resolve(toks, edges)
            except ValueError as e:
                problems.append(f'page {pg}: {e}: {s[:80]}')
                continue
            projects.append({'name': re.sub(r'\s+', ' ', m.group(1)).strip(), 'status': m.group(2), 'page': pg,
                             'group': group, 'sub': sub, 'cells': cells, 'blank': [FIELDS[i] for i, c in enumerate(cells) if c is None]})
    return projects, totals, problems


def v(x):
    return x or 0


def check_projects(projects):
    bad = []
    for p in projects:
        c = dict(zip(FIELDS, [v(x) for x in p['cells']]))
        years = sum(c[f'fy{y[-2:]}'] for y in YEARS)
        if c['prior'] + years != c['total']:
            bad.append({'project': p['name'], 'page': p['page'], 'issue': 'prior + five years != total', 'cells': c})
        if c['cost'] != c['total'] + c['needed']:
            bad.append({'project': p['name'], 'page': p['page'], 'issue': 'total + additional needed != cost estimate', 'cells': c})
    return bad


def fund_tables(pages):
    """Page 19: CIP revenues and expenses by fund source, five years and a total."""
    out = {}
    kind = None
    for raw in pages[19].split('\n'):
        label, toks = tokens(raw)
        if raw.strip().startswith('CIP Revenues'):
            kind = 'revenue'
            continue
        if raw.strip().startswith('CIP Expenses'):
            kind = 'expenditure'
            continue
        if kind and len(toks) == 6:
            out.setdefault(kind, []).append((label, [t[1] for t in toks]))
    return out


def category_table(pages):
    """Page 21: project categories, six figures then additional funds needed."""
    rows = []
    for raw in pages[21].split('\n'):
        label, toks = tokens(raw)
        if len(toks) == 7 and label:
            rows.append((label, [t[1] for t in toks]))
    return rows


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    cache = None
    if '--cache' in sys.argv:
        cache = sys.argv[sys.argv.index('--cache') + 1]
        args = [a for a in args if a != cache]
    if not args:
        sys.exit(__doc__)
    pdf = args[0]
    out = Path(args[1] if len(args) > 1 else Path(__file__).parent / 'output' / 'cip')
    (out / 'source').mkdir(parents=True, exist_ok=True)
    (out / 'qa').mkdir(parents=True, exist_ok=True)
    pages = read_pages(pdf, cache)

    projects, totals, problems = parse_projects(pages)
    funds = fund_tables(pages)
    cats = category_table(pages)

    # --- checks ---------------------------------------------------------------------------------------------------
    qa = {'problems': problems, 'rowChecks': check_projects(projects), 'groupChecks': [], 'fundChecks': [], 'categoryChecks': []}
    cols = FIELDS
    for t in totals:
        if t['label'].startswith('All ') or t['label'] in ('Facilities Total', 'Transportation Total', 'Water Resources Total',
                                                           'Public Safety Total', 'Special Projects Total'):
            continue
        members = [p for p in projects if p['group'] == t['group'] and (p['sub'] == t['sub'])]
        if not members:
            continue
        sums = [sum(v(p['cells'][i]) for p in members) for i in range(9)]
        printed = [v(c) for c in t['cells']]
        diff = [cols[i] for i in range(9) if sums[i] != printed[i]]
        qa['groupChecks'].append({'total': t['label'], 'page': t['page'], 'projects': len(members), 'ok': not diff, 'differs': diff,
                                  'sum': dict(zip(cols, sums)), 'printed': dict(zip(cols, printed))})
    # Fund-source tables: each year's total row equals the sum of its rows; the five years equal the printed total.
    for kind, rows in funds.items():
        body = [r for r in rows if r[0] != 'TOTAL']
        total = next(r for r in rows if r[0] == 'TOTAL')
        for i in range(6):
            s = sum(r[1][i] for r in body)
            qa['fundChecks'].append({'table': kind, 'column': (YEARS + ['total'])[i], 'sum': s, 'printed': total[1][i], 'ok': s == total[1][i]})
    # Category table (page 21) against the project sums, and the CIP expense total.
    expense_total = next(r for r in funds['expenditure'] if r[0] == 'TOTAL')[1]
    all_row = next(r for r in cats if r[0].startswith('All Project'))[1]
    qa['categoryChecks'].append({'check': 'all-categories total equals fund-source expense total', 'ok': all_row[:6] == expense_total})
    proj_year = [sum(v(p['cells'][2 + i]) for p in projects) for i in range(5)]
    qa['categoryChecks'].append({'check': 'sum of project rows by year equals page 21 all-categories', 'projects': proj_year, 'printed': all_row[:5],
                                 'ok': proj_year == all_row[:5]})
    qa['summary'] = {'projects': len(projects), 'rowIssues': len(qa['rowChecks']), 'groupMismatches': sum(1 for g in qa['groupChecks'] if not g['ok']),
                     'fundMismatches': sum(1 for f in qa['fundChecks'] if not f['ok']), 'unreadable': len(problems)}
    json.dump(qa, open(out / 'qa' / 'cip-checks.json', 'w'), indent=1)

    # --- JSON-LD --------------------------------------------------------------------------------------------------
    book = json.load(open(Path(__file__).parent / 'output' / 'cip-sources.json')) if (Path(__file__).parent / 'output' / 'cip-sources.json').exists() else {}
    book_url = (book.get('cip') or {}).get('url')
    bid = lambda y: BASE + f'budget/cip-fy{y}'
    pid = {}
    used = set()
    for p in projects:
        base = slug(p['name'])
        key = base
        n = 2
        while key in used:  # the same name can appear in two groups
            key = f'{base}-{slug(p["sub"] or p["group"] or "")}' if n == 2 else f'{base}-{n}'
            n += 1
        used.add(key)
        pid[id(p)] = BASE + 'project/' + key
        p['key'] = key

    project_nodes, lines = [], []
    dataset = BASE + 'dataset/cip-fy2027-31'
    for p in projects:
        project_nodes.append({'@id': pid[id(p)], '@type': 'Project', 'name': p['name'], 'sourceDataset': dataset, 'dateModified': TODAY})
        c = dict(zip(FIELDS, p['cells']))

        def line(tail, name, value, budget_key, phase, page):
            lines.append({'@id': BASE + f'budget-line/cip-{budget_key}/{p["key"]}/{tail}', '@type': 'BudgetLine', 'name': name,
                          'budget': {'@id': bid(budget_key[2:] if budget_key.startswith('fy') else budget_key)},
                          'amount': {'@type': 'MonetaryAmount', 'value': value, 'currency': 'USD'},
                          'direction': 'expenditure', 'budgetPhase': phase, 'project': {'@id': pid[id(p)]}})
        for y in YEARS:
            val = c[f'fy{y[-2:]}']
            if val:
                lines.append({'@id': BASE + f'budget-line/cip-fy{y}/{p["key"]}', '@type': 'BudgetLine', 'name': p['name'],
                              'budget': {'@id': bid(y)}, 'amount': {'@type': 'MonetaryAmount', 'value': val, 'currency': 'USD'},
                              'direction': 'expenditure', 'budgetPhase': PHASE[y], 'project': {'@id': pid[id(p)]}})
    # Aggregate lines by fund source (text: the book does not say which County fund each source is).
    for kind, rows in funds.items():
        for label, vals in rows:
            if label == 'TOTAL':
                continue
            for y, val in zip(YEARS, vals[:5]):
                if val:
                    lines.append({'@id': BASE + f'budget-line/cip-fy{y}/fund-source/{kind}/{slug(label)}', '@type': 'BudgetLine',
                                  'name': f'CIP {kind} by fund source: {label}', 'budget': {'@id': bid(y)},
                                  'amount': {'@type': 'MonetaryAmount', 'value': val, 'currency': 'USD'}, 'direction': kind,
                                  'budgetPhase': PHASE[y], 'fundSource': label})
    budgets = []
    for y in YEARS:
        budgets.append({'@id': bid(y), '@type': 'Budget', 'name': f'County of Marin Capital Improvement Plan FY {y} ({"proposed" if PHASE[y] == "proposed" else "programmed"})',
                        'description': 'Capital projects and their funding for this fiscal year, as printed in the County of Marin FY 2027-31 Proposed Capital Improvement Plan.',
                        **({'url': book_url} if book_url else {}),
                        'publisher': {'@id': COUNTY}, 'about': {'@id': JURISDICTION}, 'budgetPhase': PHASE[y], 'fiscalYear': y,
                        'startDate': YEAR_DATES[y][0], 'endDate': YEAR_DATES[y][1], 'currency': 'USD', 'dateModified': TODAY,
                        'budgetLine': [{'@id': l['@id']} for l in lines if l['budget']['@id'] == bid(y)]})
    for name, nodes in (('cip-projects.jsonld', project_nodes), ('cip-budgets.jsonld', budgets), ('cip-budget-lines.jsonld', lines)):
        json.dump({'@context': CONTEXT, '@graph': nodes}, open(out / name, 'w'), indent=1, ensure_ascii=False)

    # Display data that has no schemaGov home yet: category, CIP status, prior approvals, additional funds needed, page.
    display = {
        'book': {'title': 'County of Marin FY 2027-31 Proposed Capital Improvement Plan', 'pages': 'Fund sources p. 19; categories p. 21; projects pp. 24-27'},
        'years': YEARS,
        'projects': [{'@id': pid[id(p)], 'name': p['name'], 'category': p['group'], 'subcategory': p['sub'], 'cipStatus': p['status'],
                      'page': p['page'] - OFFSET, 'costEstimate': v(p['cells'][0]), 'priorApprovals': v(p['cells'][1]),
                      'byYear': {y: v(p['cells'][2 + i]) for i, y in enumerate(YEARS)}, 'totalFunding': v(p['cells'][7]),
                      'additionalFundsNeeded': v(p['cells'][8]), 'blankCells': p['blank']} for p in projects],
        'categoryTotals': [{'label': l, 'byYear': dict(zip(YEARS, vals[:5])), 'total': vals[5], 'additionalFundsNeeded': vals[6]} for l, vals in cats],
        'fundSources': {k: [{'label': l, 'byYear': dict(zip(YEARS, vals[:5])), 'total': vals[5]} for l, vals in rows] for k, rows in funds.items()},
    }
    json.dump(display, open(out / 'source' / 'cip-display.json', 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(qa['summary']))


if __name__ == '__main__':
    main()
