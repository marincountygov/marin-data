#!/usr/bin/env python3
"""Reads the County of Marin FY 2025-26 Final Budget book into rows, one list per schedule.

    python3 extract_budget_2025.py BOOK.pdf [OUTPUT_DIR] [--cache PAGES.pkl]

Writes OUTPUT_DIR/budget-2025-26/schedules.json (default OUTPUT_DIR: ./output) and qa/budget-2025-26-checks.json.
Every row keeps the book's own label and numbers. A row is {"label", "code", "values", "page"}; a heading
is {"heading", "page"}. Nothing is inferred: a line is a row only when it ends in numbers, and a line
without numbers is a heading. Revenues and negatives in brackets are stored as negative numbers.
Printed page number = PDF page number - 8.

Checks (see checks()) compare sums with totals the book itself prints; any difference is written to the
qa file and fails the run.
"""
import json
import pickle
import re
import sys
from pathlib import Path

OFFSET = 8  # printed page number = PDF page number - 8
TITLE = 'County of Marin Final Budget FY 2025-26'

# Schedule number -> (title, columns). Columns are the book's own headings.
YEARS = ['2023-24 Actual', '2024-25 Estimated', '2025-26 Recommended', '2025-26 Adopted by the Board of Supervisors']
FUNDS = ['Fund Balance Available June 30, 2025', 'Decreases to Obligated Fund Balances', 'Additional Financing Sources',
         'Total Financing Sources', 'Financing Uses', 'Increases to Obligated Fund Balances', 'Total Financing Uses']
SCHEDULES = {
    1: ('All Funds Summary', FUNDS),
    2: ('Governmental Funds Summary', FUNDS),
    3: ('Fund Balance - Governmental Funds', ['Total Fund Balance June 30, 2025', 'Nonspendable, Restricted, and Encumbrances', 'Committed', 'Assigned', 'Fund Balance Available June 30, 2025']),
    4: ('Obligated Fund Balances - By Governmental Funds', ['Obligated Fund Balances June 30, 2025', 'Decreases or Cancellations: Recommended', 'Decreases or Cancellations: Adopted by the Board of Supervisors', 'Increases or New Obligated Fund Balances: Recommended', 'Increases or New Obligated Fund Balances: Adopted by the Board of Supervisors', 'Total Obligated Fund Balances for the Budget Year']),
    5: ('Summary of Additional Financing Sources by Source and Fund', YEARS),
    6: ('Detail of Additional Financing Sources by Fund and Account', YEARS),
    7: ('Summary of Financing Uses by Function and Fund', YEARS),
    8: ('Detail of Financing Uses by Function, Activity and Budget Unit', YEARS),
    9: ('Financing Sources and Uses by Budget Unit by Object', YEARS),
    10: ('Operation of Internal Service Fund', YEARS),
    11: ('Operation of Enterprise Fund', YEARS),
    12: ('Special Districts and Other Agencies Summary - Non Enterprise', FUNDS),
    13: ('Fund Balance - Special Districts and Other Agencies - Non Enterprise', ['Total Fund Balance June 30, 2025', 'Nonspendable, Restricted, and Encumbrances', 'Committed', 'Assigned', 'Fund Balance Available June 30, 2025']),
    14: ('Special Districts and Other Agencies - Non Enterprise Obligated Fund Balances', ['Obligated Fund Balances June 30, 2025', 'Decreases or Cancellations: Recommended', 'Decreases or Cancellations: Adopted by the Board of Supervisors', 'Increases or New Obligated Fund Balances: Recommended', 'Increases or New Obligated Fund Balances: Adopted by the Board of Supervisors', 'Total Obligated Fund Balances for the Budget Year']),
    15: ('Special Districts and Other Agencies - Non Enterprise Financing Sources and Uses by Budget Unit by Object', YEARS),
}
FTE = ['FTE 2023-24 Final', 'FTE 2024-25 Adopted', 'FTE 2024-25 Modified', 'FTE 2025-26 Adopted']

NUM = re.compile(r'^\(?-?\$?\d[\d,]*(\.\d+)?\)?$')
MONEY = re.compile(r'\(?\d{1,3}(?:,\d{3})+\)?|\(?\d+\)?')


def read_pages(pdf, cache, mode='layout'):
    cache = f'{cache}.{mode}' if cache and mode != 'layout' else cache
    if cache and Path(cache).exists():
        return pickle.load(open(cache, 'rb'))
    from pypdf import PdfReader
    pages = [(p.extract_text(extraction_mode=mode) if mode == 'layout' else p.extract_text()) or '' for p in PdfReader(pdf).pages]
    if cache:
        pickle.dump(pages, open(cache, 'wb'))
    return pages


def number(s):
    s = s.replace('$', '').strip()
    if s in ('-', '--'):
        return None
    neg = s.startswith('(') or s.startswith('-')
    s = s.strip('()-').replace(',', '')
    v = float(s) if '.' in s else int(s)
    return -v if neg else v


def cells_of(line):
    return [c.strip() for c in re.split(r'\s{2,}', line.strip()) if c.strip()]


def split_row(cells):
    """(label parts, values) from the cells of one line; values are the trailing numeric cells."""
    out = []
    while cells and (NUM.match(cells[-1]) or cells[-1] in ('-', '--', '$')):
        c = cells.pop()
        if c != '$':
            out.append(c)
    out.reverse()
    vals = []
    for c in out:
        # two numbers printed with no space between them, as in the Road Fund page
        parts = MONEY.findall(c) if c.count(',') > 2 or re.search(r'\d,\d{3}\d', c) else [c]
        vals += [number(p) for p in parts]
    return cells, vals


def clean_label(parts):
    label = ' '.join(p for p in parts if p).strip()
    code = None
    m = re.match(r'^(\d{3,4})(?:\s+|(?=[A-Za-z]))(.+)$', label)
    if m:
        code, label = m.group(1), m.group(2)
    return code, re.sub(r'\s+', ' ', label)


NOISE = re.compile(r'^(State Controller Schedules|County Budget Act|Text\d+)')


WELL = re.compile(r'^\(?\d{1,3}(,\d{3})*\)?$|^-$')


def positioned(text, plain, pdf_page, sched):
    """Schedules 4 and 14 print rows with some columns blank, so the values go by their place under the column numbers.
    A few cells are printed twice on top of each other in the PDF (unreadable in the layout text); the first value is then
    read from the plain text of the same page, and any other unreadable cell is left empty and listed in the QA file."""
    lines = [l for l in text.splitlines() if l.strip()]
    anchors = None
    items = []
    problems = []
    plain_lines = [re.sub(r'\s+', ' ', l).strip() for l in plain.splitlines()]
    for l in lines:
        spans = [(m.start(), m.end(), m.group()) for m in re.finditer(r'\S+(?: \S+)*', l)]
        if anchors is None:
            nums = [(a, b, t) for a, b, t in spans if re.fullmatch(r'\d', t)]
            if len(nums) >= 6 and [int(t) for _, _, t in nums] == list(range(1, len(nums) + 1)):
                anchors = [(a + b) / 2 for a, b, _ in nums[1:]]  # column 1 is the label
            continue
        if not spans or NOISE.match(spans[0][2]):
            continue
        tail = []
        while spans and (NUM.match(spans[-1][2]) or spans[-1][2] == '-' or re.search(r'\d', spans[-1][2]) and ',' in spans[-1][2] and not re.search(r'[A-Za-z]', spans[-1][2])):
            tail.append(spans.pop())
        tail.reverse()
        if not tail:
            items.append({'heading': ' '.join(t for _, _, t in spans), 'page': pdf_page})
            continue
        code, label = clean_label([t for _, _, t in spans])
        vals = [None] * len(anchors)
        bad = []
        for a, b, t in tail:
            k = min(range(len(anchors)), key=lambda j: abs(anchors[j] - (a + b) / 2))
            if WELL.match(t) or NUM.match(t) and WELL.match(t.replace('$', '')):
                if vals[k] is None:
                    vals[k] = number(t)
                else:
                    bad.append(k)
            else:
                # a stray digit printed over a number (430,526,7240 for 430,526,724) is left out
                m = re.match(r'^(\(?\d{1,3}(?:,\d{3})+\)?)\d$', t)
                if m and vals[k] is None:
                    vals[k] = number(m.group(1))
                else:
                    bad.append(k)
        if bad:
            first = None
            for pl in plain_lines:
                if (code and pl.startswith(code + ' ') or not code and pl.startswith(label)) and label in pl:
                    m = re.match(r'\s*(\(?\d{1,3}(?:,\d{3})*\)?)(?!\d)', pl[pl.index(label) + len(label):])
                    first = number(m.group(1)) if m else None
                    break
            for k in bad:
                if k == 0 and first is not None and vals[0] is None:
                    vals[0] = first
                else:
                    problems.append({'page': pdf_page, 'label': label, 'column': k + 2})
        items.append({'label': label, 'code': code, 'values': vals, 'page': pdf_page})
    return items, problems


def parse_schedule_page(text, pdf_page, sched):
    """Rows and headings from one schedule page, after its column-number line."""
    lines = [l for l in text.splitlines() if l.strip()]
    start = 0
    head = []
    for i, l in enumerate(lines):
        cs = cells_of(l)
        if len(cs) >= 4 and all(re.fullmatch(r'\d', c) for c in cs) and [int(c) for c in cs] == list(range(1, len(cs) + 1)):
            start = i + 1
            break
        head.append(re.sub(r'\s{2,}', ' ', l.strip()))
    items = []
    for l in lines[start:]:
        cs = cells_of(l)
        if not cs or NOISE.match(cs[0]):
            continue
        label_parts, vals = split_row(list(cs))
        code, label = clean_label(label_parts)
        if vals and (label or code):
            items.append({'label': label, 'code': code, 'values': vals, 'page': pdf_page})
        elif vals:
            items.append({'label': '', 'code': None, 'values': vals, 'page': pdf_page})
        else:
            items.append({'heading': ' '.join(cs), 'page': pdf_page})
    return head, items


def heading_text(head, key):
    for h in head:
        if key in h:
            return h
    return ''


def schedule_pages(pages):
    """PDF page -> schedule number."""
    out = {}
    for i, p in enumerate(pages, 1):
        if i < 9 or i > 345:
            continue
        m = re.search(r'Schedule\s+(\d+)\b', p[:700])
        if m and int(m.group(1)) in SCHEDULES:
            out[i] = int(m.group(1))
    return out


def personnel(pages):
    """Personnel allocation by department (pages 373-384) and by fund (385)."""
    depts = []
    cur = None
    for i in range(373, 385):
        for l in pages[i - 1].splitlines():
            cs = cells_of(l)
            if not cs or cs[0].startswith('County of Marin Personnel') or cs[0].startswith('FTE '):
                continue
            joined = ' '.join(cs)
            m = re.match(r'^(\d{3})\s+(.+?)\s+Final\b', joined)
            if m:
                cur = {'unit': m.group(1), 'name': m.group(2), 'rows': [], 'page': i}
                depts.append(cur)
                continue
            if cur is None:
                continue
            cs = [c.replace('$', '').strip() for c in cs]
            cs = [c for c in cs if c]
            if cs[0] == 'TOTAL':
                cur['total'] = [number(c) for c in cs[1:]]
                continue
            if re.fullmatch(r'\d{3,4}', cs[0]) and len(cs) >= 7:
                cur['rows'].append({'code': cs[0].zfill(4), 'label': cs[1], 'fte': [number(c) for c in cs[2:6]],
                                    'min': number(cs[6]) if len(cs) > 6 else None, 'max': number(cs[7]) if len(cs) > 7 else None, 'page': i})
    funds = []
    for l in pages[384].splitlines():
        cs = cells_of(l)
        if len(cs) == 5 and all(NUM.match(c) or c == '-' for c in cs[1:]):
            funds.append({'label': cs[0], 'values': [number(c) for c in cs[1:]], 'page': 385})
    return depts, funds


def trends(pages):
    rows = []
    for l in pages[371].splitlines():
        cs = cells_of(l)
        if len(cs) == 6 and re.fullmatch(r'\d{4}-\d{2}', cs[0]):
            rows.append({'fiscalYear': cs[0], 'budgetRequirements': number(cs[1]), 'budgetRequirementsChange': cs[2],
                         'currentSecured': number(cs[4]), 'currentSecuredChange': cs[5], 'page': 372})
    return rows


def road_fund(pages):
    items = []
    for l in pages[297].splitlines():
        cs = cells_of(l)
        if not cs or cs[0].startswith('2026 Requested') or cs[0].startswith('2024-25 Adopted'):
            continue
        label_parts, vals = split_row(list(cs))
        _, label = clean_label(label_parts)
        items.append({'label': label, 'values': vals, 'page': 298} if vals or label.startswith('Total') else {'heading': ' '.join(cs), 'page': 298})
    return items


def charts(pages):
    out = {}
    for i, name in ((4, 'Means of Financing by Major Sources'), (5, 'Appropriations by Major Functions')):
        txt = re.sub(r'\s+', ' ', pages[i - 1])
        items = [(m.group(1).strip(' ,'), number(m.group(2))) for m in re.finditer(r'([A-Z&][A-Z &,\']+?),\s*([\d,]+),', txt)]
        out[name] = {'page': i, 'rows': [{'label': a.title().replace('&', '&'), 'values': [b]} for a, b in items]}
    return out


def build(pages, plain):
    sp = schedule_pages(pages)
    problems = []
    sched = {}
    for n, (title, cols) in SCHEDULES.items():
        sched[n] = {'number': n, 'title': title, 'columns': cols, 'pages': [], 'items': []}
    for i in sorted(sp):
        n = sp[i]
        head, items = parse_schedule_page(pages[i - 1], i, n)
        if n in (4, 14):
            items, probs = positioned(pages[i - 1], plain[i - 1], i, n)
            problems += probs
        s = sched[n]
        s['pages'].append(i)
        if n in (10, 11):
            ft = heading_text(head, 'Fund Title')
            m = re.search(r'Fund Title:\s*(\d{4})\s*(.+?)(?:\s+Fiscal|$)', ft)
            act = heading_text(head, 'Service Activity')
            m2 = re.search(r'Service Activity:\s*(.+)$', act)
            ent = {'heading': f"{m.group(1)} {m.group(2)}" if m else ft, 'page': i, 'fund': m.group(1) if m else None,
                   'serviceActivity': m2.group(1).strip() if m2 else None}
            s['items'].append(ent)
        s['items'] += items
    depts, pfunds = personnel(pages)
    return problems, {
        'book': TITLE,
        'offset': OFFSET,
        'schedules': [sched[n] for n in sorted(sched)],
        'roadFund': {'title': 'Road Fund Work Program Statement', 'columns': ['2024-25 Adopted', '2025-26 Adopted'], 'items': road_fund(pages), 'page': 298},
        'charts': charts(pages),
        'personnel': {'columns': FTE + ['Minimum Salary', 'Maximum Salary'], 'departments': depts,
                      'byFund': {'columns': ['FY 2023-24 Final', 'FY 2024-25 Adopted', 'FY 2024-25 Modified', 'FY 2025-26 Adopted'], 'rows': pfunds}},
        'propertyTaxTrends': trends(pages),
    }


def rows(s):
    return [x for x in s['items'] if 'heading' not in x]


def find(s, label, start=0, code=None):
    for x in rows(s):
        if x['label'] == label and (code is None or x['code'] == code):
            return x
    return None


def checks(data):
    out = []
    bad = []

    def expect(name, got, want, tolerance=0):
        # The book rounds its own subtotals; a difference of a dollar or two between parts and a printed total is the book's.
        ok = abs(got - want) <= tolerance if isinstance(got, (int, float)) else got == want
        out.append({'check': name, 'got': got, 'want': want, 'ok': ok, **({'difference': got - want} if got != want and ok else {})})
        if not ok:
            bad.append(name)

    S = {s['number']: s for s in data['schedules']}
    s1 = find(S[1], 'Total All Funds')
    expect('Schedule 1 total financing uses = total financing sources', s1['values'][4] + s1['values'][5], s1['values'][3])
    expect('Schedule 1 additional financing + fund balance + decreases = total financing sources', sum(s1['values'][:3]), s1['values'][3])
    # Schedule 2: the five groups add to the governmental total
    s2 = [x for x in rows(S[2]) if x['label'].startswith('Total') and x['code'] is None]
    gov1 = find(S[1], 'Total Governmental Funds')
    for k in range(7):
        expect(f'Schedule 2 groups add to Schedule 1 governmental total, column {k + 1}', sum(x['values'][k] for x in s2 if x['label'] in ('Total General Fund', 'Total Special Revenue Funds', 'Total Capital Project Funds', 'Total Debt Service Funds')), gov1['values'][k])
    # Schedule 5 and 6: each source total adds up; the all-source total equals Schedule 1's additional financing sources
    t5 = find(S[5], 'Total Summarization by Source')
    parts5 = []
    for x in rows(S[5]):
        if x is t5:
            break
        if x['code'] is None and len(x['values']) == 4 and x['label'] not in ('Total',):
            parts5.append(x)
    for k in range(4):
        expect(f'Schedule 5 sources add to their total, {YEARS[k]}', sum(x['values'][k] for x in parts5), t5['values'][k], tolerance=2)
    expect('Schedule 5 total (adopted) = Schedule 1 governmental additional financing sources', t5['values'][3], gov1['values'][2])
    # Schedule 7 and 8
    t7 = find(S[7], 'Total Financing Uses by Function')
    expect('Schedule 7 subtotal (adopted) = Schedule 1 governmental financing uses', find(S[7], 'Subtotal Financing Uses')['values'][3], gov1['values'][4])
    fn = [x for x in rows(S[7]) if x['code'] is None and len(x['values']) == 4 and rows(S[7]).index(x) < rows(S[7]).index(t7)]
    for k in range(4):
        expect(f'Schedule 7 functions add to their total, {YEARS[k]}', sum(x['values'][k] for x in fn), t7['values'][k])
    # Schedule 8 function totals equal Schedule 7 functions
    f8 = {}
    cur = None
    for x in S[8]['items']:
        if 'heading' in x:
            continue
        if x['label'].startswith('Function Total:'):
            f8[x['label'].replace('Function Total: ', '')] = x['values']
    for x in fn:
        if x['label'] in f8:
            expect(f"Schedule 8 function total = Schedule 7, {x['label']}", f8[x['label']], x['values'])
    # Row arithmetic printed on each row of Schedules 3, 4, 13 and 14, and of Schedules 2 and 12 (sources = uses)
    def every_row(n, name, fn):
        rs = [x for x in rows(S[n]) if len(x['values']) == len(S[n]['columns']) and None not in x['values']]
        wrong = [f"p.{x['page']} {x['label']}" for x in rs if not fn(x['values'])]
        out.append({'check': name, 'rows': len(rs), 'wrong': wrong[:20], 'ok': not wrong})
        if wrong:
            bad.append(name)
    every_row(2, 'Schedule 2 rows: sources add up and equal uses', lambda v: v[0] + v[1] + v[2] == v[3] and v[4] + v[5] == v[6] and v[3] == v[6])
    every_row(12, 'Schedule 12 rows: sources add up and equal uses', lambda v: v[0] + v[1] + v[2] == v[3] and v[4] + v[5] == v[6] and v[3] == v[6])
    every_row(3, 'Schedule 3 rows: total fund balance less obligated = available', lambda v: v[0] - v[1] - v[2] - v[3] == v[4])
    every_row(13, 'Schedule 13 rows: total fund balance less obligated = available', lambda v: v[0] - v[1] - v[2] - v[3] == v[4])
    every_row(4, 'Schedule 4 rows: balance less decreases plus increases = total', lambda v: v[0] - v[2] + v[4] == v[5] or v[0] - v[1] + v[3] == v[5] or v[0] - v[2] + v[3] == v[5] or v[0] - v[1] + v[4] == v[5])
    every_row(14, 'Schedule 14 rows: balance less decreases plus increases = total', lambda v: v[0] - v[2] + v[4] == v[5] or v[0] - v[1] + v[3] == v[5] or v[0] - v[2] + v[3] == v[5] or v[0] - v[1] + v[4] == v[5])
    # Personnel: department totals add to the County Operating Funds total
    tot = sum((d.get('total') or [0, 0, 0, 0])[3] for d in data['personnel']['departments'] if d.get('total'))
    funds = {r['label']: r['values'] for r in data['personnel']['byFund']['rows']}
    expect('Personnel by department (2025-26 adopted FTE) = Grand Total by fund', round(tot, 2), funds['Grand Total'][3])
    expect('Personnel by fund: Operating + Open Space = Grand Total', round(funds['County Operating Funds Total'][3] + funds['Open Space District Total'][3], 2), funds['Grand Total'][3])
    return out, bad



BASE = 'https://marincountygov.github.io/marin-data/id/'
CONTEXT = 'https://schema.govfresh.com/v1/context.jsonld'
# index in the four year columns -> Budget entity. Estimated is the book's own label; schemaGov has no "estimated" phase, so it is `adjusted`.
BUDGETS = [
    ('fy2023-24-executed', 'executed', '2023-24', 'FY 2023-24 (actual)', '2023-07-01', '2024-06-30'),
    ('fy2024-25-estimated', 'adjusted', '2024-25', 'FY 2024-25 (estimated)', '2024-07-01', '2025-06-30'),
    ('fy2025-26-recommended', 'proposed', '2025-26', 'FY 2025-26 (recommended)', '2025-07-01', '2026-06-30'),
    ('fy2025-26-adopted', 'approved', '2025-26', 'FY 2025-26 (adopted by the Board of Supervisors)', '2025-07-01', '2026-06-30'),
]


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def money(v):
    return {'@type': 'MonetaryAmount', 'value': v, 'currency': 'USD'}


def build_jsonld(data, orgs, funds, book_url):
    """Budget and BudgetLine entities from Schedules 5, 8 and 2, and Fund entities for fund numbers the dataset lacks."""
    S = {s['number']: s for s in data['schedules']}
    unit_org = {}
    for o in orgs:
        for i in o.get('identifier', []):
            if i.get('propertyID') == 'local:marin-budget-department-code':
                unit_org[i['value']] = o['@id']
    fund_ids = {f['@id'].rsplit('/', 1)[1] for f in funds}
    budgets, lines, new_funds, unmapped = [], [], {}, set()
    publisher = {'@id': BASE + 'organization/county-of-marin'}
    about = {'@id': BASE + 'jurisdiction/us-ca-marin'}
    for bid, phase, fy, name, start, end in BUDGETS:
        budgets.append({'@id': BASE + 'budget/' + bid, '@type': 'Budget', 'name': f'County of Marin {name}',
                        'description': f'Figures for fiscal year {fy} as printed in the County of Marin Final Budget FY 2025-26.',
                        **({'url': book_url} if book_url else {}), 'publisher': publisher, 'about': about, 'budgetPhase': phase,
                        'fiscalYear': fy, 'startDate': start, 'endDate': end, 'currency': 'USD', 'budgetLine': []})
    by_id = {b['@id'].rsplit('/', 1)[1]: b for b in budgets}

    def add(bid, lid, name, value, direction, **extra):
        line = {'@id': f'{BASE}budget-line/{bid}/{lid}', '@type': 'BudgetLine', 'name': name,
                'budget': {'@id': BASE + 'budget/' + bid}, 'amount': money(value), 'direction': direction, **extra}
        lines.append(line)
        by_id[bid]['budgetLine'].append({'@id': line['@id']})
        return line

    # Schedule 8: function > activity > budget unit, expenditure, all four year columns
    fn = act = None
    kids = {}
    prev_total = True
    for x in S[8]['items']:
        if 'heading' in x:
            if prev_total:
                fn, act = x['heading'], None
            else:
                act = x['heading']
            prev_total = False
            continue
        if x['label'].startswith('Activty Total:'):
            for k, (bid, *_r) in enumerate(BUDGETS):
                line = add(bid, f'function-{slug(fn)}/activity-{slug(act)}/expenditure', f'{fn}, {act}', x['values'][k], 'expenditure')
                line['hasPart'] = [{'@id': u['@id']} for u in kids.get((bid, act), [])]
                for u in kids.get((bid, act), []):
                    u['isPartOf'] = {'@id': line['@id']}
            continue
        if x['label'].startswith('Function Total:'):
            for k, (bid, *_r) in enumerate(BUDGETS):
                line = add(bid, f'function-{slug(fn)}/expenditure', f'{fn}', x['values'][k], 'expenditure')
                parts = [l for l in lines if l['@id'].startswith(f'{BASE}budget-line/{bid}/function-{slug(fn)}/activity-') and l['@id'].endswith('/expenditure') and 'isPartOf' not in l]
                line['hasPart'] = [{'@id': l['@id']} for l in parts]
                for l in parts:
                    l['isPartOf'] = {'@id': line['@id']}
            prev_total = True
            continue
        if x['code']:
            for k, (bid, *_r) in enumerate(BUDGETS):
                extra = {'identifier': [{'@type': 'PropertyValue', 'propertyID': 'local:budget-unit', 'value': x['code']}]}
                if x['code'] in unit_org:
                    extra['administrativeClassification'] = {'@id': unit_org[x['code']]}
                else:
                    unmapped.add((x['code'], x['label']))
                line = add(bid, f'function-{slug(fn)}/activity-{slug(act)}/unit-{x["code"]}/expenditure', f'{x["label"].title()}, {act}', x['values'][k], 'expenditure', **extra)
                kids.setdefault((bid, act), []).append(line)
    # Schedule 5: countywide additional financing sources by source, revenue, all four year columns (no parent total: the book's own total differs by a dollar from its parts in two years)
    for x in rows(S[5]):
        if x['page'] != 90 or x['label'].startswith('Total'):
            continue
        for k, (bid, *_r) in enumerate(BUDGETS):
            add(bid, f'source-{slug(x["label"])}/revenue', x['label'], x['values'][k], 'revenue')
    # Schedule 2: financing uses and additional financing sources by fund (the adopted budget)
    for x in rows(S[2]):
        if not x['code']:
            continue
        fid = BASE + 'fund/' + x['code']
        if x['code'] not in fund_ids:
            new_funds[x['code']] = {'@id': fid, '@type': 'Fund', 'name': x['label'],
                                    'identifier': [{'@type': 'PropertyValue', 'propertyID': 'local:fund-code', 'value': x['code']}]}
        for col, direction in ((4, 'expenditure'), (2, 'revenue')):
            add('fy2025-26-adopted', f'fund-{x["code"]}/{direction}', x['label'], x['values'][col], direction, fund={'@id': fid})
    # The book rounds each of its own subtotals; where a total differs by a dollar or two from its parts, the link between them is left out
    by = {l['@id']: l for l in lines}
    rounding = []
    for l in lines:
        if 'hasPart' in l:
            total = sum(by[p['@id']]['amount']['value'] for p in l['hasPart'])
            if total != l['amount']['value']:
                rounding.append({'line': l['@id'], 'name': l['name'], 'budget': l['budget']['@id'].rsplit('/', 1)[1], 'printed': l['amount']['value'], 'parts': total})
                for p in l.pop('hasPart'):
                    by[p['@id']].pop('isPartOf', None)
    return budgets, lines, list(new_funds.values()), sorted(unmapped), rounding


def main():
    args = [a for a in sys.argv[1:]]
    cache = None
    if '--cache' in args:
        k = args.index('--cache')
        cache = args[k + 1]
        del args[k:k + 2]
    pdf = args[0]
    out_dir = Path(args[1] if len(args) > 1 else 'output')
    pages = read_pages(pdf, cache)
    plain = read_pages(pdf, cache, 'plain')
    problems, data = build(pages, plain)
    results, bad = checks(data)
    (out_dir / 'budget-2025-26').mkdir(parents=True, exist_ok=True)
    (out_dir / 'qa').mkdir(parents=True, exist_ok=True)
    json.dump(data, open(out_dir / 'budget-2025-26' / 'schedules.json', 'w'), indent=1, ensure_ascii=False)
    json.dump({'checks': results, 'unreadable': problems}, open(out_dir / 'qa' / 'budget-2025-26-checks.json', 'w'), indent=1)
    if problems:
        print(f'{len(problems)} cells printed over each other in the PDF could not be read; see the qa file')
    orgs = json.load(open(out_dir / 'organizations.jsonld'))['@graph']
    funds = json.load(open(out_dir / 'funds.jsonld'))['@graph']
    book_url = json.load(open(out_dir / 'sources.json')).get('budgetBook2025', {}).get('url')
    budgets, lines, new_funds, unmapped, rounding = build_jsonld(data, orgs, funds, book_url)
    for name, graph in (('budgets-2025-26.jsonld', budgets), ('budget-lines-2025-26.jsonld', lines), ('funds-2025-26.jsonld', new_funds)):
        json.dump({'@context': CONTEXT, '@graph': graph}, open(out_dir / name, 'w'), indent=1, ensure_ascii=False)
    json.dump({'budgetUnitsWithoutOrganization': [{'unit': a, 'name': b} for a, b in unmapped], 'totalsThatDifferFromTheirPartsAsPrinted': rounding}, open(out_dir / 'qa' / 'budget-2025-26-unmapped.json', 'w'), indent=1)
    print(f'{len(budgets)} budgets, {len(lines)} lines, {len(new_funds)} new funds; {len(unmapped)} budget units have no organization')
    notes = {
        'notes': [
            'Figures are whole dollars as the book prints them.',
            'The book prints four columns: 2023-24 Actual, 2024-25 Estimated, 2025-26 Recommended and 2025-26 Adopted by the Board of Supervisors.',
            'In the data, Actual is an executed budget, Estimated an adjusted one, Recommended a proposed one and Adopted an approved one; schemaGov has no estimated phase.',
            'These figures are kept apart from the FY 2026-28 book, which also prints FY 2025-26 (as Approved).',
            'Budget lines on this page are the book\'s Schedule 8: each budget unit under the function and activity it is listed in.',
        ],
        'unitsWithoutOrganization': [{'unit': a, 'name': b} for a, b in unmapped],
        'unreadableCells': problems,
        'totalsThatDifferFromTheirParts': [{'line': f"{next(b[3] for b in BUDGETS if b[0] == r['budget'])}: {r['name']}", 'printed': r['printed'], 'parts': r['parts'], 'difference': r['parts'] - r['printed']} for r in rounding],
        'fundsAddedToTheDataset': len(new_funds),
    }
    json.dump(notes, open(out_dir / 'budget-2025-26' / 'notes.json', 'w'), indent=1, ensure_ascii=False)
    n = sum(len(rows(s)) for s in data['schedules'])
    print(f'{n} rows in {len(data["schedules"])} schedules; {len(results) - len(bad)}/{len(results)} checks pass')
    for b in bad:
        print('FAIL', b)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
