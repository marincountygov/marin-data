#!/usr/bin/env python3
"""Extracts the County of Marin FY 2026-28 Budget Book into schemaGov JSON-LD.

    python3 extract_budget.py BOOK.pdf [OUTPUT_DIR] [--cache PAGES.pkl]

Layers built so far (each is checked against the totals the book prints):
  1. Service-area overview tables: FY 2024-25 actuals, FY 2025-26 approved, FY 2026-27 (one row per
     department or division, one total per service area).
  2. Department pages: revenues and expenditures by type for FY 2025-26 and FY 2026-27.
  0. Countywide sources and uses and the all funds summary for FY 2025-26 and FY 2026-27 (printed pages 20-21).
  3. Program Overview: per program and fund group, expenditures and revenues for FY 2025-26 and FY 2026-27.

Writes budgets.jsonld, budget-lines.jsonld, source/budget-display.json and qa/*.json in OUTPUT_DIR
(default: ./output). Existing organizations.jsonld in OUTPUT_DIR supplies the @ids; nothing is invented.
Planned (FY 2027-28) columns are not read. Amounts are whole dollars. Revenues are printed in brackets;
they are stored as positive amounts with direction "revenue".
"""
import json
import pickle
import re
import sys
from datetime import date
from pathlib import Path

BASE = 'https://marincountygov.github.io/marin-data/id/'
CONTEXT = 'https://schema.govfresh.com/v1/context.jsonld'
BOOK_URL = None  # read from sources.json
OFFSET = 2  # printed page number = PDF page number - 2

# The book's name for a department -> its budget department code, where the names differ between sections.
ALIASES = {
    'FINANCE': '320', 'RETIREMENT': '380', 'AGRICULTURE, WEIGHTS AND MEASURES': '500',
    'MARIN COUNTY SHERIFF CORONER’S OFFICE': '260', 'INFORMATION SERVICES AND TECHNOLOGY': '360',
    'ELECTIONS': '390',
}
# Rows in the Health and Human Services service-area table are its divisions.
DIVISIONS = {
    'BEHAVIORAL HEALTH AND RECOVERY SERVICES': 'hhs-bhrs',
    'GENERAL ADMINISTRATION': 'hhs-general-administration',
    'HOMELESSNESS & COORDINATED CARE': 'hhs-homelessness-and-coordinated-care',
    'PUBLIC HEALTH SERVICES': 'hhs-public-health',
    'SOCIAL SERVICES': 'hhs-social-services',
}
AREAS = {
    'HEALTH AND HUMAN SERVICES': 'service-area-health-and-human-services',
    'PUBLIC SAFETY': 'service-area-public-safety',
    'ADMINISTRATION AND FINANCE': 'service-area-administration-and-finance',
    'COMMUNITY DEVELOPMENT AND PUBLIC WORKS': 'service-area-community-development-and-public-works',
    'COMMUNITY SERVICES': 'service-area-community-services',
}
BUDGETS = [  # key, fiscal year label, phase, start, end, name suffix
    ('fy2024-25-executed', '2024-25', 'executed', '2024-07-01', '2025-06-30', 'actual'),
    ('fy2025-26-approved', '2025-26', 'approved', '2025-07-01', '2026-06-30', 'approved'),
    ('fy2026-27-approved', '2026-27', 'approved', '2026-07-01', '2027-06-30', 'final'),
]
BUDGET_KEY = {b[0].split('-')[0][2:] + '-' + b[0].split('-')[1]: b[0] for b in BUDGETS}  # '2024-25' -> key
NUM = re.compile(r'^\(?-?[\d,]+(?:\.\d+)?\)?$')


def read_pages(pdf, cache):
    if cache and Path(cache).exists():
        return pickle.load(open(cache, 'rb'))
    from pypdf import PdfReader
    pages = {}
    for i, p in enumerate(PdfReader(pdf).pages, 1):
        try:
            pages[i] = p.extract_text(extraction_mode='layout')
        except Exception:
            pages[i] = ''
    if cache:
        pickle.dump(pages, open(cache, 'wb'))
    return pages


def num(token):
    t = token.strip()
    if t == '-':
        return 0
    neg = t.startswith('(') or t.startswith('-')
    v = float(t.strip('()-').replace(',', ''))
    v = int(v) if v == int(v) and '.' not in t else v
    return -v if neg else v


def rows(text):
    """Lines of 'label  n  n  n ...' as (label, [numbers]). Wrapped labels are not joined."""
    out = []
    for line in text.split('\n'):
        parts = [p for p in re.split(r'\s{2,}', line.strip()) if p]
        if len(parts) < 2:
            continue
        nums = []
        label = []
        for p in parts:
            if NUM.match(p) or p == '-':
                nums.append(p)
            elif not nums:
                label.append(p)
            else:  # text after numbers: not a data row
                nums = None
                break
        if nums and label:
            out.append((' '.join(label), [num(n) for n in nums]))
    return out


def norm(s):
    return re.sub(r'[^A-Z0-9 ]', '', s.upper().replace('-', ' ')).strip()


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')



def program_overview(pages):
    """Rows of the Program Overview (printed pages 238-263): department, fund group, program, six figures.

    Each program row is (department title, fund group, label, [approved expenditures, approved revenues, approved NCC,
    proposed expenditures, proposed revenues, proposed NCC], PDF page). A department's pages also carry 'Total <group>'
    and 'Total All Funds' rows, returned separately so the extractor can check them.
    """
    SERVICE_AREAS = {'HEALTH AND HUMAN SERVICES', 'PUBLIC SAFETY', 'ADMINISTRATION AND FINANCE', 'COMMUNITY DEVELOPMENT AND PUBLIC WORKS', 'COMMUNITY SERVICES', 'NON DEPARTMENTAL'}
    programs, totals, repeated = [], [], []
    dept = group = None
    previous_rows = None
    in_table = False
    pending = None
    for n in range(240, 270):
        text = pages.get(n, '')
        if 'Program Overview' not in text:
            continue
        titles = []
        first_program, first_total = len(programs), len(totals)
        for raw in text.split('\n'):
            line = re.sub(r'\s{2,}', '  ', raw.strip())
            if not line or line == 'Program Overview':
                continue
            if re.match(r'^(PROPOSED BUDGET|\d+\s+\|)', line) or '| PROPOSED BUDGET' in line:
                continue
            if line.startswith('FY 2025-26 Approved Budget'):
                names = [re.sub(r'\s+\d+/\d+$', '', t) for t in titles]
                if len(names) >= 2 or (names and names[-1] not in SERVICE_AREAS):
                    dept, group = names[-1], None
                titles, in_table, pending = [], True, None
                continue
            if line.startswith(('Approved  Approved', 'Program Services')):
                continue
            parts = [p for p in re.split(r'\s{2,}', line) if p]
            nums = [p for p in parts[1:] if NUM.match(p) or p == '-']
            label = parts[0]
            if len(parts) > 1 and len(nums) == len(parts) - 1 and not NUM.match(label):
                vals = [num(x) for x in nums]
                if len(vals) != 6:
                    continue
                if label in ('General Fund', 'Other Funds', 'HHS Operations Fund'):
                    group = label                  # the group's own heading, printed with zeros
                    continue
                if label.startswith('Total '):
                    totals.append((dept, label[6:], vals, n))
                    if label == 'Total All Funds':
                        in_table = False
                else:
                    programs.append((dept, group, (pending + ' ' + label) if pending else label, vals, n))
                pending = None
                continue
            if len(parts) == 1 and not re.search(r'\d', line) and not line.startswith('%'):
                if not in_table:
                    titles.append(line)            # a department's title, between two tables
                elif line.upper() == line:
                    pending = line                 # the first half of a program name that wraps
                else:
                    group, pending = line, None    # a fund group: General Fund, Other Funds...
            elif not in_table and line.upper() == line and not re.search(r'\d{2,}', line):
                titles.append(line)
        # The book prints the second Health and Human Services page again under the Public Safety heading;
        # a page that repeats the one before it figure for figure is read once.
        page_rows = [(p[2], p[3]) for p in programs[first_program:]]
        if page_rows and page_rows == previous_rows:
            del programs[first_program:], totals[first_total:]
            repeated.append(n)
        else:
            previous_rows = page_rows
    return programs, totals, repeated


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    cache = sys.argv[sys.argv.index('--cache') + 1] if '--cache' in sys.argv else None
    if cache in args:
        args.remove(cache)
    pdf = args[0]
    out = Path(args[1] if len(args) > 1 else 'output')
    pages = read_pages(pdf, cache)
    orgs = {o['@id']: o for o in json.load(open(out / 'organizations.jsonld'))['@graph']}
    sources = json.load(open(out / 'sources.json'))['budgetBook']
    by_slug = {i.rsplit('/', 1)[1]: i for i in orgs}
    by_code = {}
    for oid, o in orgs.items():
        for ident in o.get('identifier', []):
            if ident['propertyID'] == 'local:marin-budget-department-code':
                by_code[ident['value']] = oid

    # Department name (as the FTE section prints it) -> code
    name_code = {}
    for n in range(268, 295):
        for m in re.finditer(r'^\s*(\d{3})\s{2,}([A-Z][A-Z &/,.\-\'’]+?)\s{2,}FTE', pages[n], re.M):
            name_code[norm(m.group(2))] = m.group(1)
    for k, v in ALIASES.items():
        name_code[norm(k)] = v

    qa = {'unmatched': [], 'sums': [], 'unsupported': []}
    lines, display = {}, {}
    page_of = {}

    def org_for(label):
        key = norm(label)
        if key in {norm(d) for d in DIVISIONS}:
            slug_ = [v for k, v in DIVISIONS.items() if norm(k) == key][0]
            return by_slug[slug_]
        code = name_code.get(key)
        return by_code.get(code) if code else None

    def line_id(bkey, oslug, tail):
        return f'{BASE}budget-line/{bkey}/{oslug}/{tail}'

    def add(bkey, oid, oslug, tail, name, value, direction, pdf_page, parent=None):
        lid = line_id(bkey, oslug, tail)
        assert lid not in lines, lid
        line = {'@id': lid, '@type': 'BudgetLine', 'name': name, 'budget': {'@id': f'{BASE}budget/{bkey}'},
                'amount': {'@type': 'MonetaryAmount', 'value': value, 'currency': 'USD'}, 'direction': direction}
        if oid:
            line['administrativeClassification'] = {'@id': oid}
        if parent:
            line['isPartOf'] = {'@id': parent}
            lines[parent].setdefault('hasPart', []).append({'@id': lid})
        lines[lid] = line
        page_of[lid] = pdf_page - OFFSET
        return lid

    # ---- Layer 1: service-area overview tables --------------------------------------------
    sa_rows = {}  # (area slug, bkey) -> {label: value}
    for n in sorted(pages):
        t = pages[n]
        if 'Service Area Total' not in t:
            continue
        m = re.search(r'SERVICE AREA OVERVIEW - ([A-Z ,&]+)', t)
        area = AREAS[m.group(1).strip()]
        table = [r for r in rows(t) if len(r[1]) == 5]
        total = [r for r in table if r[0] == 'Service Area Total'][0]
        body = [r for r in table if r[0] != 'Service Area Total']
        area_org = by_slug[area]
        aname = orgs[area_org]['name']
        for col, bkey in enumerate(['fy2024-25-executed', 'fy2025-26-approved', 'fy2026-27-approved']):
            tot_id = add(bkey, area_org, area.replace('service-area-', 'sa-'), 'expenditure-total',
                         f'Service area total: {aname}', total[1][col], 'expenditure', n)
            s = 0
            for label, vals in body:
                oid = org_for(label)
                oslug = oid.rsplit('/', 1)[1] if oid else 'row-' + slug(label)
                if not oid:
                    qa['unmatched'].append({'source': f'Service Area Overview, {aname}', 'row': label, 'page': n - OFFSET,
                                            'reason': 'No organization in organizations.jsonld for this row; the line has no administrativeClassification'})
                add(bkey, oid, oslug, 'expenditure-total', label, vals[col], 'expenditure', n, parent=tot_id)
                s += vals[col]
            qa['sums'].append({'check': 'service-area rows add to total', 'area': aname, 'budget': bkey,
                               'total': total[1][col], 'sum': s, 'difference': total[1][col] - s, 'page': n - OFFSET})
        for label, vals in body + [total]:
            oid = org_for(label) if label != 'Service Area Total' else area_org
            key = oid or label
            display.setdefault(key, {})['sa'] = {'area': aname, 'row': label, 'page': n - OFFSET,
                                                 'change_fy2026_27': vals[3], 'fte_fy2026_27': vals[4]}
        sa_rows[area] = {r[0]: r[1] for r in body}

    # ---- Layer 2: department pages ---------------------------------------------------------
    for n in sorted(pages):
        t = pages[n]
        m = re.search(r'DEPARTMENT BUDGET - ([^\n]+)', t)
        if not m or 'REVENUES AND EXPENDITURES BY TYPE' not in t:
            continue
        dname = m.group(1).strip()
        code = name_code.get(norm(dname))
        oid = by_code.get(code) if code else None
        if not oid:
            qa['unmatched'].append({'source': 'Department Budget', 'row': dname, 'page': n - OFFSET, 'reason': 'No budget code match'})
            continue
        oslug = oid.rsplit('/', 1)[1]
        table = [r for r in rows(t) if len(r[1]) == 5]
        labels = [r[0] for r in table]
        i_rev, i_exp = labels.index('Total Revenues'), labels.index('Total Expenditures')
        revenue = [r for r in table[:i_rev + 1]]
        expend = [r for r in table[i_rev + 1:i_exp + 1]]
        for col, bkey in ((0, 'fy2025-26-approved'), (1, 'fy2026-27-approved')):
            # the department's expenditure total: the service-area row line, or (HHS) its own line
            tail = f'{BASE}budget-line/{bkey}/{oslug}/expenditure-total'
            total_val = expend[-1][1][col]
            sa_line = lines.get(tail)
            if sa_line:
                if sa_line['amount']['value'] != total_val:
                    # The book disagrees with itself. Keep both figures as printed: the types go under a
                    # line of their own, so neither total is changed to fit the other.
                    qa['sums'].append({'check': 'department page total equals service-area row', 'department': dname, 'budget': bkey,
                                       'service_area_row': sa_line['amount']['value'], 'department_page': total_val,
                                       'difference': sa_line['amount']['value'] - total_val, 'page': n - OFFSET,
                                       'handling': 'Both kept. The department page figure is a separate line with the cost types under it.'})
                    exp_parent = add(bkey, oid, oslug, 'expenditure-total-department-page',
                                     f'Total expenditures (department page): {orgs[oid]["name"]}', total_val, 'expenditure', n)
                else:
                    exp_parent = tail
            else:
                exp_parent = add(bkey, oid, oslug, 'expenditure-total', f'Total expenditures: {orgs[oid]["name"]}', total_val, 'expenditure', n)
                sa_total = [l for k, l in lines.items() if k.startswith(f'{BASE}budget-line/{bkey}/sa-') and l['amount']['value'] == total_val and l['name'].startswith('Service area total')]
                qa['sums'].append({'check': 'department total matches its service-area total', 'department': dname, 'budget': bkey,
                                   'matches': [l['name'] for l in sa_total], 'value': total_val, 'page': n - OFFSET})
            s = 0
            for label, vals in expend[:-1]:
                if vals[col] == 0:
                    continue
                add(bkey, oid, oslug, 'expenditure/' + slug(label), f'{label}: {orgs[oid]["name"]}', vals[col], 'expenditure', n, parent=exp_parent)
                s += vals[col]
            qa['sums'].append({'check': 'expenditure types add to total', 'department': dname, 'budget': bkey, 'total': total_val, 'sum': s,
                               'difference': total_val - s, 'page': n - OFFSET})
            rev_total = -revenue[-1][1][col]
            if rev_total:
                rid = add(bkey, oid, oslug, 'revenue-total', f'Total revenues: {orgs[oid]["name"]}', rev_total, 'revenue', n)
                s = 0
                for label, vals in revenue[:-1]:
                    if vals[col] == 0:
                        continue
                    add(bkey, oid, oslug, 'revenue/' + slug(label), f'{label}: {orgs[oid]["name"]}', -vals[col], 'revenue', n, parent=rid)
                    s += -vals[col]
                qa['sums'].append({'check': 'revenue types add to total', 'department': dname, 'budget': bkey, 'total': rev_total, 'sum': s,
                                   'difference': rev_total - s, 'page': n - OFFSET})
        for label, vals in table:
            if label in ('Transfers In', 'Transfers Out', 'Total Transfers', 'Net County Cost'):
                display.setdefault(oid, {}).setdefault('department', {'page': n - OFFSET})[label] = {'fy2025_26': vals[0], 'fy2026_27': vals[1]}



    # ---- Countywide: sources and uses, and the all funds summary (printed pages 20-21) ------------
    county_org = by_slug['county-of-marin']
    t22, t23 = pages[22], pages[23]
    all_funds = {l: v for l, v in rows(t22[t22.index('Countywide All Funds'):]) if len(v) == 5}
    gen_hhs = {l: v for l, v in rows(t22[t22.index('General Fund and HHS Operating Fund'):t22.index('Countywide All Funds')]) if len(v) == 5}
    summary = [(l, v) for l, v in rows(t23) if len(v) == 5]
    labels23 = [l for l, _ in summary]
    rev_rows = summary[:labels23.index('Total Revenues') + 1]
    exp_rows = summary[labels23.index('Total Revenues') + 1:labels23.index('Total Expenditures') + 1]
    for col, bkey in ((0, 'fy2025-26-approved'), (1, 'fy2026-27-approved')):
        for direction, table_rows, total_label, sign in (('revenue', rev_rows, 'Total Revenues', -1), ('expenditure', exp_rows, 'Total Expenditures', 1)):
            total = sign * table_rows[-1][1][col]
            tid = add(bkey, county_org, 'county-of-marin', f'{direction}-total', f'{"Total revenues" if direction == "revenue" else "Total expenditures"}: County of Marin', total, direction, 23)
            part = 0
            for label, vals in table_rows[:-1]:
                if vals[col] == 0:
                    continue
                add(bkey, county_org, 'county-of-marin', f'{direction}/{slug(label)}', f'{label}: County of Marin', sign * vals[col], direction, 23, parent=tid)
                part += sign * vals[col]
            qa['sums'].append({'check': f'countywide {direction} types add to total', 'budget': bkey, 'total': total, 'sum': part, 'difference': total - part, 'page': 21})
        uses = all_funds['Total All Fund Uses'][col]
        exp_total = lines[f'{BASE}budget-line/{bkey}/county-of-marin/expenditure-total']['amount']['value']
        qa['sums'].append({'check': 'countywide total uses equal total expenditures', 'budget': bkey, 'total': uses, 'sum': exp_total, 'difference': uses - exp_total, 'page': 20})
    display['countywide'] = {
        'pages': {'sourcesAndUses': 20, 'allFunds': 21},
        'allFunds': {k: {'fy2025_26': v[0], 'fy2026_27': v[1]} for k, v in all_funds.items()},
        'generalAndHhsFunds': {k: {'fy2025_26': v[0], 'fy2026_27': v[1]} for k, v in gen_hhs.items()},
        'transfers': {k: {'fy2025_26': v[0], 'fy2026_27': v[1]} for k, v in summary if k in ('Transfers In', 'Transfers Out', 'Total Transfers', 'Use of Fund Balance')},
    }
    country_display = display.pop('countywide')

    # ---- Layer 3: the Program Overview -------------------------------------------------------
    # One line per program row, fund group, direction and year (FY 2025-26 approved, FY 2026-27). A row that is the same
    # program as one in programs.jsonld (by name within its department, or by program-aliases.json) also carries
    # `program`; every row carries the book's own label as programClassification and its fund group as fundSource.
    # Only the General Fund group is a Fund in funds.jsonld. Net County cost is derived and goes to the display file.
    overview, overview_totals, repeated_pages = program_overview(pages)
    programs_ld = json.load(open(out / 'programs.jsonld'))['@graph']
    funds_ld = json.load(open(out / 'funds.jsonld'))['@graph']
    general_fund = next((f for f in funds_ld if f['name'].lower() == 'general fund'), None)
    aliases = json.load(open(Path(__file__).with_name('program-aliases.json')))
    county_id = by_slug['county-of-marin']
    children = {}
    for oid, o in orgs.items():
        if o.get('parentOrganization'):
            children.setdefault(o['parentOrganization']['@id'], []).append(oid)

    def descendants(oid):
        found = {oid}
        for c in children.get(oid, []):
            found |= descendants(c)
        return found

    def admin(p):
        a = p['administeredBy']
        return (a[0] if isinstance(a, list) else a)['@id']

    def pnorm(t):
        return re.sub(r'[^A-Z0-9 ]', '', t.upper().replace('&', ' AND ').replace('/', ' ').replace('-', ' ')).strip()

    qa['ambiguous'] = []
    qa['matches'] = []
    qa['unmatched_programs'] = []
    qa['unmatched_funds'] = []
    qa['notes'] = []
    if repeated_pages:
        qa['notes'].append({'note': 'The book prints the second Health and Human Services Program Overview page again under the Public Safety heading; the repeat is read once.', 'pages': [n - OFFSET for n in repeated_pages]})
    program_rows = []
    used_programs = set()
    seen_ids = {}
    dept_totals = {}  # (department org, year) -> expenditures, to check against the department pages
    for dept, group, label, vals, n in overview:
        key = norm(dept)
        if dept == 'NON DEPARTMENTAL':
            dept_org, pool = county_id, [p for p in programs_ld if admin(p) == county_id]
        else:
            code = name_code.get(key) or ('520' if key.startswith('MARIN COUNTY PARKS') else None)
            dept_org = by_code.get(code) if code else None
            if not dept_org:
                qa['unmatched'].append({'source': 'Program Overview', 'row': dept, 'page': n - OFFSET, 'reason': 'No budget code match for the department'})
                continue
            pool = [p for x in descendants(dept_org) for p in programs_ld if admin(p) == x]
        match, how = None, None
        exact = [p for p in pool if pnorm(p['name']) == pnorm(label)]
        if len(exact) == 1:
            match, how = exact[0], 'name'
        elif len(exact) > 1:
            qa['ambiguous'].append({'department': dept, 'row': label, 'page': n - OFFSET, 'candidates': [p['@id'] for p in exact]})
        else:
            alias = (aliases.get(dept) or {}).get(label)
            if alias:
                hit = [p for p in pool if p['name'] == alias[0] and orgs[admin(p)]['name'] == alias[1]]
                if len(hit) == 1:
                    match, how = hit[0], 'alias'
        if not match:
            elsewhere = [p for p in programs_ld if pnorm(p['name']) == pnorm(label) and p not in pool]
            if elsewhere:
                qa['ambiguous'].append({'department': dept, 'row': label, 'page': n - OFFSET, 'candidates': [p['@id'] for p in elsewhere],
                                        'reason': 'A program of that name exists, but it is administered by another organization'})
            qa['unmatched_programs'].append({'department': dept, 'row': label, 'fund group': group, 'page': n - OFFSET})
        else:
            used_programs.add(match['@id'])
            qa['matches'].append({'department': dept, 'row': label, 'program': match['@id'], 'by': how, 'page': n - OFFSET})
        org_id = admin(match) if match else dept_org
        oslug = org_id.rsplit('/', 1)[1]
        pslug = match['@id'].rsplit('/', 1)[1] if match else slug(label)
        gslug = slug(group)
        fund = general_fund if group == 'General Fund' else None
        if group != 'General Fund' and group not in {f['fund group'] for f in qa['unmatched_funds']}:
            qa['unmatched_funds'].append({'fund group': group, 'reason': 'A group of funds in the book, not one fund in funds.jsonld; kept as fundSource text'})
        shown = match['name'] if match else label.title().replace('’S', '’s')
        program_rows.append({'department': dept_org, 'organization': org_id, 'program': match['@id'] if match else None, 'label': label, 'fundGroup': group, 'page': n - OFFSET,
                                       'exp_fy2025_26': vals[0], 'rev_fy2025_26': -vals[1], 'ncc_fy2025_26': vals[2],
                                       'exp_fy2026_27': vals[3], 'rev_fy2026_27': -vals[4], 'ncc_fy2026_27': vals[5]})
        for bkey, e_i, r_i in (('fy2025-26-approved', 0, 1), ('fy2026-27-approved', 3, 4)):
            dept_totals[(dept_org, bkey)] = dept_totals.get((dept_org, bkey), 0) + vals[e_i]
            for direction, value in (('expenditure', vals[e_i]), ('revenue', -vals[r_i])):
                if value == 0:
                    continue
                if value < 0:
                    qa['unsupported'].append({'field': 'Negative revenue or expenditure', 'source': f'Program Overview, {dept}, {label}, {group}', 'page': n - OFFSET, 'reason': 'A negative amount has no direction in schemaGov; the row is left out', 'recommendation': 'Keep in the book'})
                    continue
                tail = f'program/{pslug}/{gslug}/{direction}'
                lid = f'{BASE}budget-line/{bkey}/{oslug}/{tail}'
                if lid in lines:
                    seen_ids[lid] = seen_ids.get(lid, 1) + 1
                    lid = f'{lid}-{seen_ids[lid]}'
                line = {'@id': lid, '@type': 'BudgetLine', 'name': f'{shown}, {group}', 'budget': {'@id': f'{BASE}budget/{bkey}'},
                        'amount': {'@type': 'MonetaryAmount', 'value': value, 'currency': 'USD'}, 'direction': direction,
                        'administrativeClassification': {'@id': org_id}, 'programClassification': label, 'fundSource': group}
                if match:
                    line['program'] = {'@id': match['@id']}
                if fund:
                    line['fund'] = {'@id': fund['@id']}
                lines[lid] = line
                page_of[lid] = n - OFFSET
    # The programs of a department add up to its expenditures.
    for (org_id, bkey), total in sorted(dept_totals.items()):
        if org_id == county_id:
            # Non Departmental is what the five service areas leave of the countywide total.
            area_sum = sum(l['amount']['value'] for l in lines.values() if f'/{bkey}/sa-' in l['@id'] and l['@id'].endswith('/expenditure-total'))
            rest = lines[f'{BASE}budget-line/{bkey}/county-of-marin/expenditure-total']['amount']['value'] - area_sum
            qa['sums'].append({'check': 'Non Departmental programs equal the countywide total less the five service areas', 'budget': bkey, 'total': rest, 'sum': total, 'difference': rest - total})
            continue
        mine = lines.get(f'{BASE}budget-line/{bkey}/{org_id.rsplit("/", 1)[1]}/expenditure-total-department-page') or lines.get(f'{BASE}budget-line/{bkey}/{org_id.rsplit("/", 1)[1]}/expenditure-total')
        if mine is not None:
            qa['sums'].append({'check': 'program rows add to the department total', 'department': orgs[org_id]['name'], 'budget': bkey, 'total': mine['amount']['value'], 'sum': total, 'difference': mine['amount']['value'] - total})
    for p in programs_ld:
        if p['@id'] not in used_programs:
            qa['unmatched_programs'].append({'program': p['@id'], 'name': p['name'], 'reason': 'No Program Overview row matched this program'})

    # ---- Budgets ------------------------------------------------------------------------
    budgets = []
    for key, fy, phase, start, end, suffix in BUDGETS:
        ids = [l['@id'] for l in lines.values() if l['budget']['@id'].endswith('/' + key)]
        budgets.append({
            '@id': f'{BASE}budget/{key}', '@type': 'Budget',
            'name': f'County of Marin FY {fy} budget ({suffix})',
            'description': f'Figures for fiscal year {fy} as printed in the {sources["title"]}. {sources["edition"]}.',
            'url': sources['url'],
            'publisher': {'@id': by_slug['county-of-marin']},
            'about': {'@id': BASE + 'jurisdiction/us-ca-marin'},
            'budgetPhase': phase, 'fiscalYear': fy, 'startDate': start, 'endDate': end, 'currency': 'USD',
            'dateModified': date.today().isoformat(),
            'budgetLine': [{'@id': i} for i in ids],
        })

    wrap = lambda g: {'@context': CONTEXT, '@graph': g}
    (out / 'source').mkdir(exist_ok=True)
    (out / 'qa').mkdir(exist_ok=True)
    dump = lambda p, x: (out / p).write_text(json.dumps(x, indent=2, ensure_ascii=False) + '\n')
    dump('budgets.jsonld', wrap(budgets))
    dump('budget-lines.jsonld', wrap(list(lines.values())))
    dump('source/budget-display.json', {'note': 'Printed values schemaGov has no property for (change, FTE, transfers, net County cost) and the printed page of each line.',
                                        'book': sources['title'], 'url': sources['url'], 'organizations': display, 'countywide': country_display, 'programRows': program_rows, 'linePages': page_of})
    bad = [s for s in qa['sums'] if s.get('difference')]
    qa['unsupported'] = [
        {'field': 'FTE', 'source': 'Service area overview; FTE by department', 'reason': 'No supported schemaGov property or model', 'recommendation': 'Preserve in source/budget-display.json for a future workforce profile'},
        {'field': 'Net County Cost, Change columns, Transfers', 'source': 'Department pages', 'reason': 'Derived values or movements between funds, not lines', 'recommendation': 'Kept in source/budget-display.json'},
        {'field': 'Source page number', 'source': 'All tables', 'reason': 'No provenance property below Budget', 'recommendation': 'Kept in source/budget-display.json linePages'},
        {'field': 'Net County cost by program', 'source': 'Program Overview', 'reason': 'Derived value', 'recommendation': 'Kept in source/budget-display.json programRows'},
        {'field': 'FY 2027-28 planned', 'source': 'All tables', 'reason': 'No planned phase; decision not to add', 'recommendation': 'Not extracted'},
    ]
    dump('qa/budget-matches.json', qa['matches'])
    dump('qa/unmatched-programs.json', qa['unmatched_programs'])
    dump('qa/unmatched-funds.json', qa['unmatched_funds'])
    dump('qa/ambiguous-matches.json', qa['ambiguous'] + qa['notes'])
    dump('qa/unmatched-organizations.json', qa['unmatched'])
    dump('qa/sum-check.json', qa['sums'])
    dump('qa/unsupported-source-fields.json', qa['unsupported'])
    print(f'{len(budgets)} budgets, {len(lines)} lines, {len(qa["unmatched"])} unmatched, {len(qa["sums"])} checks, {len(bad)} with a difference')
    for b in bad:
        print('  DIFF', b)


if __name__ == '__main__':
    main()
