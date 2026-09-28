"""Bounded assay inventory; database annotations do not establish primary eligibility."""
import json,hashlib,urllib.request,datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'data/raw/phase20';OUT=ROOT/'data/phase20'
def fetch(url,path):
 if not path.exists():
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'cryo-research/0.1'}),timeout=60) as r:b=r.read()
  path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b)
 return json.loads(path.read_bytes())
def work(a):
 aid=a['assay_chembl_id'];did=a['document_chembl_id']
 try:
  ap=RAW/f'inventory/{aid}-activities.json';d=fetch(f'https://www.ebi.ac.uk/chembl/api/data/activity.json?assay_chembl_id={aid}&limit=1000',ap)
  rows=d['activities'];exact=[r for r in rows if r['standard_type']=='IC50' and r['standard_units']=='nM' and r['standard_relation']=='=' and r['standard_value'] is not None and 0<float(r['standard_value'])<=10000 and not r.get('data_validity_comment')]
  item={'assay_id':aid,'document_id':did,'description':a['description'],'confidence_score':a['confidence_score'],'assay_organism':a['assay_organism'],'total_records':d['page_meta']['total_count'],'download_complete':d['page_meta']['next'] is None,'provisional_exact_n':len(exact),'unique_molecules':len({r['molecule_chembl_id'] for r in exact}),'raw_path':str(ap.relative_to(ROOT)),'sha256':hashlib.sha256(ap.read_bytes()).hexdigest()}
  if len(exact)>=20:
   doc=fetch(f'https://www.ebi.ac.uk/chembl/api/data/document/{did}.json',RAW/f'inventory/{did}-document.json');item['document']={k:doc.get(k) for k in ['title','doi','year','pubmed_id','patent_id','journal']}
  return item
 except Exception as e:return {'assay_id':aid,'error':str(e)}
def main():
 assays=json.loads((RAW/'rock2-assays.json').read_text())
 terms=['htrf','radiometric','caliper','mobility','filter binding','fluorescence polarization','immobilized metal']
 selected=[a for a in assays['assays'] if any(t in a['description'].lower() for t in terms) and a['src_id']==1]
 with ThreadPoolExecutor(max_workers=3) as pool:result=list(pool.map(work,selected))
 OUT.mkdir(parents=True,exist_ok=True);out={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'assays_total':assays['page_meta']['total_count'],'assay_inventory_complete':assays['page_meta']['next'] is None,'query_policy':'All ChEMBL source1 literature assays with nonluciferase method keywords; per-assay first1000 records, pagination explicitly reported. No prediction-based selection. Exact values preliminary and not primary-reconciled.','method_keywords':terms,'assays_queried':len(selected),'candidates':result}
 (OUT/'orthogonal-source-inventory.json').write_text(json.dumps(out,indent=2)+'\n')
 for a in result:
  if a.get('provisional_exact_n',0)>=20:print(json.dumps(a))
 print('queried',len(result),'errors',sum('error' in a for a in result))
if __name__=='__main__':main()
