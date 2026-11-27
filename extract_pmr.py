from bs4 import BeautifulSoup
from pathlib import Path
import re, json, html, hashlib, sys
from datetime import datetime

import argparse
REPO=Path(__file__).resolve().parent
ap=argparse.ArgumentParser(description='Build the PMR schemaGov JSON-LD from the saved HR page.')
ap.add_argument('--source',type=Path,default=REPO/'source/pmr/All Personnel Management Regulations _ County of Marin Human Resources.html')
ap.add_argument('--out',type=Path,default=REPO/'output/regulations')
ap.add_argument('--check',action='store_true',help='fail if output/regulations/ is not what the saved page makes (needs the page in source/pmr/)')
args=ap.parse_args()
SRC=args.source
OUT=args.out
if args.check:
    import tempfile; WANT=OUT; OUT=Path(tempfile.mkdtemp())
OUT.mkdir(parents=True,exist_ok=True)
soup=BeautifulSoup(SRC.read_text(encoding='utf-8'),'html.parser')
canonical=(soup.find('link',rel='canonical') or {}).get('href','')
BASE='https://marincountygov.github.io/marin-data/id/regulation'
MAN=f'{BASE}/personnel-management-regulations'
JUR='https://marincountygov.github.io/marin-data/id/jurisdiction/us-ca-marin'
HR='https://marincountygov.github.io/marin-data/id/organization/hr'
CTX={'schema':'https://schema.org/','gs':'https://schema.govfresh.com/ns#'}

def clean(t): return re.sub(r'\s+',' ',t).strip()
def iso_date(s):
    s=clean(s)
    for fmt in ('%B %d, %Y','%B %Y','%m/%d/%Y'):
        try:
            d=datetime.strptime(s,fmt)
            return d.date().isoformat() if '%d' in fmt or '%m/' in fmt else d.strftime('%Y-%m')
        except: pass
    return s

def ref(id): return {'@id':id}
def id_slug(x):
    x=x.lower().replace('&',' and ')
    x=re.sub(r'[^a-z0-9.]+','-',x).strip('-')
    return x

# Locate four structural h2s and walk until next structural h2.
section_re=re.compile(r'^Section\s+(\d+)\s*:\s*(.+)$',re.I)
pmr_re=re.compile(r'^(?:Personnel Regulation|PMR)\s+(\d+)\s*:?[ ]*(.*)$',re.I)
prov_re=re.compile(r'^(\d+(?:\.\d+)+)\s+(.+)$')
sections=[]; pmrs=[]; tables=[]; internal_cites=[]
current_sec=None; current_pmr=None; current_prov=None; approval=False; purpose=False
positions={'sec':0,'pmr':{},'prov':{}}

def add_text(node, txt):
    txt='\n'.join(l for l in (clean(x) for x in txt.split('\n')) if l)  # a list or table keeps one line per item or row
    if not txt: return
    if node.get('text'): node['text'] += '\n\n'+txt
    else: node['text']=txt

def add_citations(node, txt):
    found=[]
    for m in re.finditer(r'\bPMR(?:\s+No\.)?\s*(\d+(?:\.\d+)*)(?!\d)', txt, re.I):
        label=m.group(0); num=m.group(1)
        target=f'{BASE}/pmr-{num.split(".")[0]}' + (f'/{num}' if '.' in num else '')
        found.append({'label':label,'target':target})
        internal_cites.append((node['@id'],label,target))
    if found:
        node.setdefault('citation',[])
        existing={(x.get('@id') if isinstance(x,dict) else x) for x in node['citation']}
        for f in found:
            if f['target'] not in existing: node['citation'].append({'@id':f['target']})

for tag in soup.find_all(['h2','h3','h4','p','ol','ul','table']):
    txt=clean(tag.get_text(' ',strip=True))
    sm=section_re.match(txt) if tag.name=='h2' else None
    if sm:
        positions['sec']+=1; num,title=sm.groups()
        current_sec={'@id':f'{MAN}/part-{num}','@type':'Legislation','legislationIdentifier':f'Section {num}','name':title,'codificationLevel':'part','position':positions['sec'],'isPartOf':ref(MAN),'hasPart':[]}
        sections.append(current_sec); current_pmr=current_prov=None; approval=purpose=False; continue
    if not current_sec: continue
    pm=pmr_re.match(txt) if tag.name=='h3' else None
    if pm:
        num,title=pm.groups(); title=clean(title)
        positions['pmr'][current_sec['@id']]=positions['pmr'].get(current_sec['@id'],0)+1
        current_pmr={'@id':f'{BASE}/pmr-{num}','@type':'Legislation','legislationIdentifier':f'PMR {num}','codificationLevel':'chapter','legislationType':'regulation','position':positions['pmr'][current_sec['@id']],'isPartOf':ref(current_sec['@id']),'hasPart':[]}
        if title: current_pmr['name']=title
        pmrs.append(current_pmr); current_sec['hasPart'].append(ref(current_pmr['@id']))
        current_prov=None; approval=purpose=False; continue
    if not current_pmr: continue
    pr=prov_re.match(txt) if tag.name in ('h3','h4') else None
    if pr:
        ident,title=pr.groups(); depth=ident.count('.')
        level='section' if depth==1 else ('subsection' if depth==2 else 'paragraph')
        # The id follows the PMR the provision sits in, so a provision numbered by mistake (35's "25.3") cannot take another's id. The number stays as written.
        pid=f"{current_pmr['@id']}/{ident}"
        positions['prov'][current_pmr['@id']]=positions['prov'].get(current_pmr['@id'],0)+1
        current_prov={'@id':pid,'@type':'Legislation','legislationIdentifier':ident,'name':clean(title),'codificationLevel':level,'position':positions['prov'][current_pmr['@id']],'isPartOf':ref(current_pmr['@id'])}
        current_pmr['hasPart'].append(ref(pid)); current_pmr.setdefault('_provisions',[]).append(current_prov)
        approval=purpose=False; continue
    if tag.name in ('h3','h4'):
        low=txt.lower()
        if low=='approval': approval=True; purpose=False; current_prov=None; continue
        if 'applicability' in low and 'purpose' in low: purpose=True; approval=False; current_prov=None; continue
    if tag.name=='p' and approval:
        # parse approval block line-aware using br separators
        raw=str(tag)
        parts=[clean(BeautifulSoup(x,'html.parser').get_text(' ',strip=True)) for x in re.split(r'<br\s*/?>',raw,flags=re.I)]
        for part in parts:
            part=re.sub(r'^<p>|</p>$','',part)
            if ':' not in part: continue
            k,v=part.split(':',1); k=clean(k).lower(); v=clean(v)
            if 'effective date' in k: current_pmr['legislationDateOfApplicability']=iso_date(v)
            elif 'amended date' in k or 'revision date' in k: current_pmr['legislationDateVersion']=iso_date(v)
            elif 'revision' in k and ('no' in k or 'number' in k): current_pmr['version']=v
            elif 'prepared by' in k: current_pmr['creator']=v
            elif 'approved' in k: current_pmr['legislationCountersignedBy']=v
        approval=False; continue
    if tag.name=='p' and purpose:
        current_pmr['description']=txt; purpose=False; add_citations(current_pmr,txt); continue
    target=current_prov or current_pmr
    if tag.name=='p':
        add_text(target,txt); add_citations(target,txt)
    elif tag.name in ('ol','ul'):
        # Only top-level list tags; nested list text is kept in parent list item text.
        if tag.find_parent(['ol','ul']): continue
        items=[]
        for li in tag.find_all('li',recursive=False): items.append(clean(li.get_text(' ',strip=True)))
        if items:
            block='\n'.join(f'{i+1}. {v}' if tag.name=='ol' else f'- {v}' for i,v in enumerate(items))
            add_text(target,block); add_citations(target,block)
    elif tag.name=='table':
        rows=[]
        for tr in tag.find_all('tr'):
            cells=[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['th','td'])]
            if cells: rows.append(cells)
        if rows:
            tables.append({'container':target['@id'],'rows':rows})
            add_text(target,'\n'.join(' | '.join(r) for r in rows))

# Flatten provisions and remove helper
reg_graph=[]
for p in pmrs:
    provs=p.pop('_provisions',[])
    reg_graph.append(p); reg_graph.extend(provs)

# Add source citation to manual only, plus LegislationObject rendering.
manual={'@id':MAN,'@type':'Legislation','legislationIdentifier':'PMR','name':'Personnel Management Regulations','codificationLevel':'code','legislationType':'regulation','legislationJurisdiction':ref(JUR),'publisher':ref(HR),'citation':[canonical],'hasPart':[ref(s['@id']) for s in sections]}
source_obj={'@id':MAN+'/source-html','@type':'LegislationObject','name':'All Personnel Management Regulations | County of Marin Human Resources','encodingFormat':'text/html','url':canonical,'contentUrl':canonical,'legislationLegalValue':'OfficialLegalValue'}

# Definitions from PMR 2, section 2.1 text paragraphs pattern letter + term + definition.
defs=[]; termset_id='https://marincountygov.github.io/marin-data/id/term-set/personnel-management-regulations'
# Reparse between 2.1 and next heading to preserve term boundaries.
h21=None
for h in soup.find_all(['h3','h4']):
    if clean(h.get_text(' ',strip=True)).startswith('2.1 Definitions'): h21=h; break
if h21:
    pos=0
    for sib in h21.find_all_next():
        if sib is not h21 and sib.name in ('h3','h4'):
            break
        if sib.name!='p': continue
        t=clean(sib.get_text(' ',strip=True))
        m=re.match(r'^([A-Z])\.\s*[“\"]?(.+?)[.”\"]?\s+(.*)$',t)
        if m:
            letter,term,desc=m.groups(); term=term.strip(' .“”"'); desc=clean(desc)
            # Term is usually first sentence fragment; span markup helps refine.
            sp=sib.find('span')
            if sp:
                st=clean(sp.get_text(' ',strip=True)).strip(' .“”"')
                st=re.sub(r'^[A-Z]\.\s*','',st)
                if st and len(st)<100:
                    term=st
                    body=re.sub(r'^[A-Z]\.\s*','',t)
                    body=re.sub(r'^[“\"]?'+re.escape(term)+r'[.”\"]?\s*','',body,flags=re.I)
                    desc=clean(body)
            pos+=1
            defs.append({'@id':f'https://marincountygov.github.io/marin-data/id/term/pmr/{id_slug(term)}','@type':'DefinedTerm','name':term,'description':desc,'position':pos,'inDefinedTermSet':ref(termset_id),'subjectOf':ref(f'{BASE}/pmr-2/2.1')})
termset={'@id':termset_id,'@type':'DefinedTermSet','name':'Personnel Management Regulations definitions','hasDefinedTerm':[ref(d['@id']) for d in defs]}

# Integrity targets across manual/sections/regulations/provisions/defs
all_nodes=[manual,source_obj]+sections+reg_graph+[termset]+defs
ids={n['@id'] for n in all_nodes}
broken=[]
for n in all_nodes:
    for key in ('hasPart','isPartOf'):
        vals=n.get(key,[]); vals=vals if isinstance(vals,list) else [vals]
        for v in vals:
            if isinstance(v,dict) and v.get('@id') and v['@id'] not in ids: broken.append((n['@id'],key,v['@id']))
# Internal citation resolution report only if target exists.
resolved=sum(1 for _,_,t in internal_cites if t in ids); unresolved=len(internal_cites)-resolved
# A citation whose target is not in the data stays text, as written. It must not point at an identifier that does not exist.
as_written={(i,t):l for i,l,t in internal_cites}
for n in reg_graph+sections:
    if n.get('citation'):
        n['citation']=[(as_written.get((n['@id'],c['@id']),c['@id']) if isinstance(c,dict) and c['@id'] not in ids else c) for c in n['citation']]

# Fit the schemaGov policy profile without changing a value of the source.
# - Every Legislation node carries legislationType, so a provision carries its document's type.
# - subjectOf is a list.
# - A date that is not a whole date (the source says "2005-01"), and a preparer or approver named only as text (no entity to point at),
#   cannot go in a date or reference property. They stay, as written, in a local identifier. Each is listed as a schema gap in the README.
import re as _re
def local(node, prop, value):
    node.setdefault('identifier', []).append({'@type': 'PropertyValue', 'propertyID': prop, 'value': value})
for n in reg_graph+sections:
    if n.get('@type') == 'Legislation':
        n.setdefault('legislationType', 'regulation')
    if 'subjectOf' in n and not isinstance(n['subjectOf'], list):
        n['subjectOf'] = [n['subjectOf']]
    d = n.get('legislationDateOfApplicability')
    if d is not None and not _re.fullmatch(r'\d{4}-\d{2}-\d{2}', d):
        local(n, 'local:pmr-effective-date-as-written', n.pop('legislationDateOfApplicability'))
    if isinstance(n.get('creator'), str):
        local(n, 'local:pmr-prepared-by-as-written', n.pop('creator'))
    if isinstance(n.get('legislationCountersignedBy'), str):
        local(n, 'local:pmr-approved-by-as-written', n.pop('legislationCountersignedBy'))
for n in defs:
    if 'subjectOf' in n and not isinstance(n['subjectOf'], list):
        n['subjectOf'] = [n['subjectOf']]

manual_doc={'@context':CTX,'@graph':[manual,source_obj]+sections}
regs_doc={'@context':CTX,'@graph':reg_graph}
defs_doc={'@context':CTX,'@graph':[termset]+defs}
for name,obj in [('manual.jsonld',manual_doc),('regulations.jsonld',regs_doc),('definitions.jsonld',defs_doc)]:
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
qa={'source_file':SRC.name,'canonical_url':canonical,'major_groups':len(sections),'pmrs':len(pmrs),'provisions':sum(1 for n in reg_graph if n.get('codificationLevel') in ('section','subsection','paragraph')),'definitions':len(defs),'tables':len(tables),'internal_pmr_citations':len(internal_cites),'internal_pmr_citations_resolved':resolved,'internal_pmr_citations_unresolved':unresolved,'broken_hierarchy_refs':broken,'pmr_identifiers':[p['legislationIdentifier'] for p in pmrs]}
(OUT/'qa.json').write_text(json.dumps(qa,indent=2)+'\n')
if args.check:
    stale=[f.name for f in sorted(OUT.iterdir()) if not (WANT/f.name).exists() or (WANT/f.name).read_bytes()!=f.read_bytes()]
    if stale: sys.exit(f'{", ".join(stale)} in output/regulations/ is out of date. Run: python3 extract_pmr.py')
    print('ok: output/regulations/ is current')
else:
    print(json.dumps(qa,indent=2))
