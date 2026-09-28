"""Match author-supplied structures and ROCK-II values to the ChEMBL snapshot."""
import csv, hashlib, json, math
from pathlib import Path
from rdkit import Chem
ROOT=Path(__file__).resolve().parents[1]
def canonical(s):
    m=Chem.MolFromSmiles(s)
    if m is None: raise ValueError('Invalid structure')
    return Chem.MolToSmiles(m,isomericSmiles=True)
def reconcile(source, records):
    if source[0] != ['Compound_ID','SMILES','ROCK Ⅰ IC50 (um)','ROCK Ⅱ IC50 (um)','PKA IC50 (um)']:
        raise ValueError('Unexpected source columns: do not confuse ROCK-I and ROCK-II')
    by_structure={}
    for r in records:
        key=canonical(r['canonical_smiles'])
        if key in by_structure: raise ValueError('Duplicate ChEMBL structure needs adjudication')
        by_structure[key]=r
    result=[]; seen=set()
    for row in source[1:]:
        key=canonical(row[1])
        if key in seen: raise ValueError('Duplicate author structure needs adjudication')
        seen.add(key); r=by_structure[key]
        val=row[3].strip(); relation='>' if val.startswith('>') else '='
        value=float(val.lstrip('>'))*1000
        if not math.isclose(value,float(r['standard_value']),rel_tol=1e-10) or relation!=r['standard_relation']:
            raise ValueError('Primary source and ChEMBL disagree; explicit adjudication required')
        if r['standard_units']!='nM' or r['standard_type']!='IC50': raise ValueError('Endpoint mismatch')
        result.append({'activity_id':r['activity_id'],'molecule_id':r['molecule_chembl_id'],
            'source_compound_number':row[0],'source_smiles':row[1],'canonical_smiles':r['canonical_smiles'],
            'identity_verified':True,'identity_method':'RDKit canonical isomeric identity, author CSV versus ChEMBL',
            'original_value_nM':float(r['standard_value']),'corrected_value_nM':value,'corrected_relation':relation,
            'source_reported_value_uM':val,'source_location':'jm9b01143_si_002.csv, compound '+row[0]+', ROCK Ⅱ column'})
    if seen!=set(by_structure): raise ValueError('Unmatched records')
    return result
if __name__=='__main__':
    paths=['data/raw/phase20/jm9b01143_si_002.csv','data/raw/phase20/inventory/CHEMBL4379076-activities.json']
    source=list(csv.reader((ROOT/paths[0]).read_bytes().decode('gb18030').splitlines()))
    rows=reconcile(source,json.loads((ROOT/paths[1]).read_text())['activities'])
    output={'assay_id':'CHEMBL4379076','primary_doi':'10.1021/acs.jmedchem.9b01143','encoding':'GB18030; preserves distinct Roman I and II headers',
        'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
        'reconciled_rows':rows,'excluded_records':[], 'unit_conversion':'Author µM multiplied by 1000 to nM; all values and relations agree.',
        'counts':{'total':len(rows),'exact':sum(r['corrected_relation']=='=' for r in rows),'censored':sum(r['corrected_relation']!='=' for r in rows)}}
    with (ROOT/'data/phase20/source-table-reconciliation.json').open('x') as f: json.dump(output,f,indent=2);f.write('\n')
    print(output['counts'])
