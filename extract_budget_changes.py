#!/usr/bin/env python3
"""Extracts each department's "DESCRIPTION OF BUDGET CHANGES" from the County of Marin FY 2026-28 Budget Book.

    python3 extract_budget_changes.py BOOK.pdf [OUTPUT_DIR] [--cache PAGES.pkl]

Reads output/source/budget-display.json (written by extract_budget.py) for each department's printed page,
then takes the text under the heading on that page and on the pages that continue it. The text is the book's own,
unchanged apart from joining wrapped lines. Writes output/source/budget-changes.json:

    { "<organization @id>": { "pages": [printed page numbers], "paragraphs": ["...", ...] } }

and output/qa/budget-changes-checks.json (departments with no description, and the text kept per department).
Printed page number = PDF page number - 2.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_budget import read_pages, OFFSET  # noqa: E402

HEADING = re.compile(r'D\s*E\s*S\s*C\s*R\s*I\s*P\s*T\s*I\s*O\s*N\s+O\s*F\s+B\s*U\s*D\s*G\s*E\s*T\s+C\s*H\s*A\s*N\s*G\s*E\s*S')
NET_COST = re.compile(r'^\s*Net County Cost\b.*$', re.M)
FOOTER = re.compile(r'PROPOSED BUDGET FY 2026-28\s*\|\s*\d+|^\s*\d+\s*\|\s*PROPOSED BUDGET FY 2026-28')
RUNNING = ('Two Year Budget',)
SECTION = re.compile(r'^[A-Z][A-Z0-9 ,&()/\-–—:\']{5,}$')  # a heading in capitals, e.g. PRIORITIES
NUMBERED = re.compile(r'^\d+\.\s{2,}')


def content_lines(text):
    """The page's lines without the running header, the footer and blank lines."""
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line in RUNNING or line.startswith('DEPARTMENT BUDGET -') or FOOTER.search(line):
            continue
        out.append(line)
    return out


def paragraphs(lines):
    """Wrapped lines -> paragraphs. A paragraph ends where a line ends a sentence and the next word would have fit on it."""
    if not lines:
        return []
    width = max(len(l) for l in lines)
    out, current = [], ''
    for i, line in enumerate(lines):
        # A word split at the end of a line keeps its hyphen and loses the space ("cost-" + "covered").
        joiner = '' if current.endswith('-') and line[:1].islower() else ' '
        current = (current + joiner + line).strip() if current else line
        nxt = lines[i + 1].split(' ', 1)[0] if i + 1 < len(lines) else ''
        if line.endswith(('.', '!', '?', '.”')) and nxt and len(line) + 1 + len(nxt) <= width:
            out.append(current)
            current = ''
    if current:
        out.append(current)
    return [re.sub(r'\s+', ' ', p) for p in out]


def description(pages, pdf_page):
    """Lines under the heading on pdf_page and on the pages that continue it, and the pages used."""
    text = pages.get(pdf_page, '')
    found = HEADING.search(text)
    if found:
        head = text[found.end():]
    else:
        # The heading did not survive the PDF's text layer: the description follows the last Net County Cost row.
        rows = list(NET_COST.finditer(text))
        if not rows:
            return None, [], False
        head = text[rows[-1].end():]
    lines = [l for l in content_lines(head) if not re.match(r'^[\d,()\s.\-]+$', l)]
    used = [pdf_page]
    dept = re.search(r'DEPARTMENT BUDGET - ([^\n]+)', text)
    nxt = pdf_page + 1
    while dept and nxt in pages:
        t = pages[nxt]
        m = re.search(r'DEPARTMENT BUDGET - ([^\n]+)', t)
        if not m or m.group(1).strip() != dept.group(1).strip():
            break
        more = content_lines(t)
        if not more or SECTION.match(more[0]) or NUMBERED.match(more[0]) or HEADING.search(t):
            break
        # Lines up to the first heading in capitals belong to the description.
        keep = []
        for l in more:
            if SECTION.match(l) or NUMBERED.match(l):
                break
            keep.append(l)
        lines += keep
        used.append(nxt)
        if len(keep) < len(more):
            break
        nxt += 1
    return lines, used, bool(found)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    cache = sys.argv[sys.argv.index('--cache') + 1] if '--cache' in sys.argv else None
    if cache in args:
        args.remove(cache)
    pdf = args[0]
    out = Path(args[1] if len(args) > 1 else 'output')
    pages = read_pages(pdf, cache)
    display = json.loads((out / 'source' / 'budget-display.json').read_text())
    result, missing, unheaded = {}, [], []
    for org, info in display['organizations'].items():
        dept = info.get('department')
        if not dept or dept.get('page') is None:
            continue
        lines, used, headed = description(pages, dept['page'] + OFFSET)
        if not lines:
            missing.append(org)
            continue
        result[org] = {'pages': [p - OFFSET for p in used], 'paragraphs': paragraphs(lines)}
        if not headed:
            unheaded.append(org)
    (out / 'source' / 'budget-changes.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    qa = {'departments': len(result), 'withoutDescription': missing, 'headingNotFoundTextTakenAfterNetCountyCostRow': unheaded,
          'paragraphs': {org: len(v['paragraphs']) for org, v in result.items()}}
    (out / 'qa').mkdir(exist_ok=True)
    (out / 'qa' / 'budget-changes-checks.json').write_text(json.dumps(qa, indent=2) + '\n')
    print(f'Wrote budget-changes.json: {len(result)} departments; none found for {len(missing)}.')


if __name__ == '__main__':
    main()
