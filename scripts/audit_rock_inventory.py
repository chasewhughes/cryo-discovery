"""Audit identity overlap and frozen scaffold splits for Phase 20 ROCK2 inventory."""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold

ROOT=Path(__file__).resolve().parents[1]
INVENTORY=ROOT/'data/phase20/orthogonal-source-inventory.json'
PRIOR=[ROOT/'data/phase15/rock-benchmark.json',ROOT/'data/phase18/external-dataset.json']

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def identity(smiles):
    m=Chem.MolFromSmiles(smiles)
    if m is None or not 0<m.GetNumHeavyAtoms()<=128 or len(Chem.GetMolFrags(m))!=1: raise ValueError('invalid ligand')
    return Chem.MolToSmiles(m,isomericSmiles=True), Chem.MolToSmiles(m,isomericSmiles=False), m

def split_rows(rows):
    groups={}
    for r in rows: groups.setdefault(r['scaffold'],[]).append(r['molecule_id'])
    ordered=sorted(groups,key=lambda s:hashlib.sha256(('cryo-phase19-split-1900:'+s).encode()).hexdigest())
    cal=[]
    for s in ordered:
        if len(cal)>=math.ceil(len(rows)/3): break
        cal.extend(groups[s])
    cal=set(cal); test=sorted(set(r['molecule_id'] for r in rows)-cal)
    cal_sc={r['scaffold'] for r in rows if r['molecule_id'] in cal}; test_sc={r['scaffold'] for r in rows if r['molecule_id'] in test}
    ok=len(cal)>=6 and len(test)>=10 and len(test_sc)>=2 and not cal_sc.intersection(test_sc)
    return {'pass':ok,'calibration_n':len(cal),'test_n':len(test),'calibration_scaffolds':len(cal_sc),'test_scaffolds':len(test_sc),'scaffold_count':len(groups),'calibration_ids':sorted(cal),'test_ids':test,'method':'Sort achiral Murcko scaffold strings by SHA256(cryo-phase19-split-1900: + scaffold), fill calibration with whole groups until at least ceil(n/3); remaining groups test.'}

def main(out):
    inv=json.loads(INVENTORY.read_text())
    prior_rows=[r for p in PRIOR for r in json.loads(p.read_text())['exact_compounds']]
    old_ids={r['molecule_id'] for r in prior_rows}; old_iso=set(); old_ach=set()
    for r in prior_rows:
        iso,ach,_=identity(r['canonical_smiles']); old_iso.add(iso); old_ach.add(ach)
    results=[]
    for c in inv['candidates']:
        if c.get('provisional_exact_n',0)<20: continue
        raw=ROOT/c['raw_path']; records=json.loads(raw.read_text())['activities']
        exact=[r for r in records if r.get('assay_chembl_id')==c['assay_id'] and r.get('standard_type')=='IC50' and r.get('standard_relation')=='=' and r.get('standard_units')=='nM' and not r.get('data_validity_comment') and r.get('standard_value') is not None and math.isfinite(float(r['standard_value'])) and 0<float(r['standard_value'])<=10000]
        by_iso={}; conflicts=[]; overlaps=[]; included=[]
        for r in exact:
            iso,ach,m=identity(r['canonical_smiles']); val=float(r['standard_value'])
            if r['molecule_chembl_id'] in old_ids or iso in old_iso or ach in old_ach:
                overlaps.append({'molecule_id':r['molecule_chembl_id'],'activity_id':r['activity_id'],'overlap_id':r['molecule_chembl_id'] in old_ids,'overlap_isomeric':iso in old_iso,'overlap_achiral':ach in old_ach}); continue
            by_iso.setdefault(iso,[]).append((r,val,ach,m))
        clean={}
        for iso, group in by_iso.items():
            values={v for _,v,_,_ in group}
            if len(values)>1:
                conflicts.append({'isomeric_smiles':iso,'molecule_ids':[r['molecule_chembl_id'] for r,_,_,_ in group],'values_nM':sorted(values)})
                continue
            r,val,ach,m=group[0]
            clean[iso]={'molecule_id':r['molecule_chembl_id'],'canonical_smiles':r['canonical_smiles'],'isomeric_smiles':iso,'achiral_smiles':ach,'scaffold':MurckoScaffold.MurckoScaffoldSmiles(mol=m),'observed_nM':val,'activity_ids':[r['activity_id'] for r,_,_,_ in group]}
        by_iso=clean
        included=sorted(by_iso.values(),key=lambda x:x['molecule_id'])
        source_status='verified_primary' if c['assay_id']=='CHEMBL4379076' else 'partial_primary_audit' if c['assay_id']=='CHEMBL2341182' else 'metadata_only_unverified'
        partition=split_rows(included) if len(included)>=20 else {'pass':False,'reason':'fewer than 20 eligible exact non-overlapping compounds'}
        results.append({'assay_id':c['assay_id'],'document_id':c.get('document_id'),'description':c.get('description'),'source_status':source_status,'raw_path':c['raw_path'],'raw_sha256':sha(raw),'inventory_provisional_exact_n':c.get('provisional_exact_n'),'raw_exact_qualified_record_n':len(exact),'raw_exact_unique_molecule_n':len({r['molecule_chembl_id'] for r in exact}),'overlap_n':len(overlaps),'overlaps':overlaps,'conflicting_structural_duplicates_n':len(conflicts),'conflicting_structural_duplicates':conflicts,'eligible_exact_unique_n':len(included),'scaffold_count':len({r['scaffold'] for r in included}),'partition':partition})
    doc={'schema_version':'phase20-rock-inventory-identity-audit-v1','scope':'Identity, duplicate, overlap and frozen scaffold-split audit only. ChEMBL assay descriptions are not treated as primary-source eligibility; source status is reported separately.','inventory_path':'data/phase20/orthogonal-source-inventory.json','inventory_sha256':sha(INVENTORY),'prior_identity_sources':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in PRIOR],'identity_policy':'Reuse Phase 19 identity rule: molecule ID, canonical isomeric SMILES, and achiral SMILES overlap exclusions; collapse identical isomeric structures only when exact values agree; enforce 1-128 heavy atoms and one fragment. Conflicting duplicate groups are excluded in full.','split_policy':'Reuse Phase 19 split seed cryo-phase19-split-1900 with whole achiral Murcko scaffold groups; no potency-based selection.','candidate_count_with_provisional_exact_records_ge20':len(results),'candidate_count_with_provisional_unique_molecules_ge20':sum(c.get('raw_exact_unique_molecule_n',0)>=20 for c in results),'candidates':results,'notes':['Only CHEMBL4379076 has a complete primary audit in Phase 20; CHEMBL2341182 has a partial primary audit. Other rows remain metadata-only and are not source-eligible.','No model outputs, predictions, or GPU operations performed.']}
    out=ROOT/out; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(doc,indent=2,allow_nan=False)+'\n'); print(json.dumps({'candidates':len(results),'output':str(out)}))
if __name__=='__main__':
 p=argparse.ArgumentParser(); p.add_argument('--output',default='data/phase20/inventory-identity-audit.json'); main(p.parse_args().output)
