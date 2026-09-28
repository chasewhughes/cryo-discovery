"""Reconcile author ROCK2 CSV structures/units; six explicit tautomer matches retained."""
import csv,hashlib,json,math
from pathlib import Path
from rdkit import Chem
from rdkit.Chem.MolStandardize import rdMolStandardize
ROOT=Path(__file__).resolve().parents[1]
def canon(s,taut=False):
 m=Chem.MolFromSmiles(s)
 if m is None:raise ValueError('Invalid structure')
 if taut:m=rdMolStandardize.TautomerEnumerator().Canonicalize(m)
 return Chem.MolToSmiles(m,isomericSmiles=True)
def reconcile(source,records):
 if source[0][:4]!=['Compound_ID','SMILES','GRK2 IC50 (nM)','ROCK2 IC50 (nM)']:raise ValueError('Unexpected ROCK2 endpoint/header')
 rows=[];missing=[];seen=set()
 for row in source[1:]:
  label,sm,value=row[0],row[1],row[3].strip()
  if not value:missing.append({'source_compound_number':label,'reason':'No ROCK2 measurement'});continue
  matches=[r for r in records if canon(sm)==canon(r['canonical_smiles'])];method='Canonical isomeric SMILES identity'
  if not matches:
   matches=[r for r in records if canon(sm,True)==canon(r['canonical_smiles'],True)];method='Unique RDKit canonical tautomer equivalence; both source and database SMILES preserved'
  if not matches and value.startswith('>'):
   missing.append({'source_compound_number':label,'source_smiles':sm,'source_reported_value_nM':value,'reason':'Censored source row absent from ChEMBL assay snapshot; not scored'});continue
  if len(matches)!=1:raise ValueError('Nonunique or missing structure identity: '+label)
  r=matches[0]
  if r['activity_id'] in seen:raise ValueError('Duplicate activity mapping')
  seen.add(r['activity_id']);rel='>' if value.startswith('>') else '=';v=float(value.lstrip('>'))
  if not math.isclose(v,float(r['standard_value']),rel_tol=1e-10) or rel!=r['standard_relation'] or r['standard_units']!='nM' or r['standard_type']!='IC50':raise ValueError('Source label/endpoint mismatch: '+label)
  rows.append({'activity_id':r['activity_id'],'molecule_id':r['molecule_chembl_id'],'source_compound_number':label,'source_smiles':sm,'canonical_smiles':r['canonical_smiles'],'identity_verified':True,'identity_method':method,'source_value_nM':value,'original_value_nM':float(r['standard_value']),'corrected_value_nM':v,'corrected_relation':rel,'source_location':'jm7b00443_si_001.csv, '+label+', ROCK2 IC50 (nM)'})
 if seen!={r['activity_id'] for r in records}:raise ValueError('Unreconciled ChEMBL records')
 return rows,missing
if __name__=='__main__':
 paths=['data/raw/phase21/grk2017/jm7b00443_si_001.csv','data/raw/phase20/inventory/CHEMBL4040374-activities.json']
 source=list(csv.reader((ROOT/paths[0]).read_bytes().decode('cp932').splitlines()));raw=json.loads((ROOT/paths[1]).read_text())['activities'];rows,missing=reconcile(source,raw)
 result={'assay_id':'CHEMBL4040374','doi':'10.1021/acs.jmedchem.7b00443','source_encoding':'CP932','source_paths':paths,'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},'reconciled_rows':rows,'excluded_records':[],'unmatched_source_rows':missing,'counts':{'author_rows':len(source)-1,'chembl_rows':len(raw),'matched_rows':len(rows),'exact':sum(r['corrected_relation']=='=' for r in rows),'matched_censored':sum(r['corrected_relation']!='=' for r in rows),'tautomer_matches':sum('tautomer' in r['identity_method'] for r in rows)},'interpretation':'ROCK2 off-target biochemical IC50, not GRK2 efficacy. Six source/database proton-placement tautomer differences explicitly reconciled before outputs; model input retains database SMILES as in earlier phases. No tautomer optimization against potency. Primary methods review separate.'}
 p=ROOT/'data/phase21/grk2017-source-reconciliation.json'
 with p.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(result['counts'])
