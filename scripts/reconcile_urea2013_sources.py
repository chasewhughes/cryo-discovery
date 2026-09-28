"""Primary-table transcription and graph reconciliation, independent of database labels.

R groups and values transcribed from Yin 2013, Tables 1–5 and Figure 2;
experimental names resolve 12n chain length and 19a absolute stereochemistry.
No potency is used as a structure join key.
"""
import argparse, hashlib, json
from pathlib import Path
from rdkit import Chem

CORE='Nc1ccc(-c2cn[nH]c2)cc1'
def benzyl(subs):
    return 'Cc1'+''.join('c'+('('+subs[i]+')' if i in subs else '') for i in range(2,7))+'1'
def canon(s):
    m=Chem.MolFromSmiles(s)
    if m is None: raise ValueError('Invalid source structure: '+s)
    return Chem.MolToSmiles(m, isomericSmiles=True)
def primary_rows():
    rows=[]
    def add(label,smiles,value,location,relation='=',note=None):
        rows.append(dict(source_compound_number=label,expected_smiles=smiles,expected_canonical_smiles=canon(smiles),primary_value_nM=value,primary_relation=relation,location=location,note=note))
    for label,r,val in [('5a','Nc1ccccc1',304),('5c','NCCc1ccccc1',88),('5d','NCCCc1ccccc1',1017),('5e','OCc1ccccc1',7),('5f','OCCc1ccccc1',55),('5g','CCc1ccccc1',24),('5h','N1CCc2ccccc2C1',280),('5i','NCC1CCCCC1',751)]:
        add(label,'O=C('+r+')'+CORE,val,'Table 1, PDF page 3')
    for label,subs,val in [('5k',{2:'OC',3:'OC'},253),('5l',{2:'OC',4:'OC'},331),('5m',{2:'OC',5:'OC'},570),('5n',{2:'OC',6:'OC'},924),('5o',{3:'OC',4:'OC'},425),('5p',{3:'OC',5:'OC'},281),('5q',{3:'F',4:'OC'},357)]:
        add(label,'O=C(N'+benzyl(subs)+')'+CORE,val,'Table 2, PDF page 4')
    b=benzyl({3:'OC'})
    for label,r,val,rel in [('8a','C',87,'='),('8b','CCO',611,'='),('8c','CCN(C)C',2984,'='),('8d','CCN1CCCC1',20000,'>'),('8e','CCCN(C)C',3324,'=')]:
        add(label,'O=C(N'+b+')N('+r+')c1ccc(-c2cn[nH]c2)cc1',val,'Table 3, PDF page 4',rel)
    for suffix,r,val,rel in [('a','C',1,'='),('b','CC',1,'='),('c','C1CC1',1,'='),('d','C(C)C',3,'='),('e','CCO',1,'='),('f','CCOC',17,'='),('g','CCN',1,'<'),('h','CCN(C)C',1,'='),('i','CCN1CCCC1',3,'='),('j','CCCN1CCCC1',5,'='),('k','CCN1CCOCC1',13,'='),('l','CCCN1CCOCC1',4,'='),('m','CCN1CCCCC1',5,'='),('n','CCCN1CCCCC1',4,'=')]:
        add('12'+suffix,'O=C(N('+b+')'+r+')'+CORE,val,'Table 4, PDF page 5',rel,'12n experimental name confirms 3-(piperidin-1-yl)propyl' if suffix=='n' else None)
    add('12o','O=C(N(CCO)Cc1ccccc1)'+CORE,12,'Table 4, PDF page 5')
    add('12p','O=C(N(CCO)Cc1ccccc1)Nc1ccc(-c2cn[nH]c2)cc1F',14,'Table 4, PDF page 5')
    for suffix,aryl,r,val in [('a','c1cccc(OC)c1','CCO',2),('b','c1cccc(F)c1','CCO',2),('c','c1ccccc1','CCO',1),('d','c1ccccc1','CO',2),('e','c1ccccc1','CCN(C)C',2)]:
        add('14'+suffix,'O=C(NC('+r+')'+aryl+')'+CORE,val,'Table 5, PDF page 5')
    # Absolute S comes from the experimental heading (PDF p11), not the
    # unwedged overview figure. Assign from that named stereochemistry.
    sm='O=C(N(CC)'+b+')Nc1ccc(-c2cn[nH]c2)cc1O[C@H]1CCN(C)C1'
    m=Chem.MolFromSmiles(sm); Chem.AssignStereochemistry(m,force=True,cleanIt=True)
    if [a.GetProp('_CIPCode') for a in m.GetAtoms() if a.HasProp('_CIPCode')]!=['S']:
        sm=sm.replace('[C@H]','[C@@H]')
    add('19a',sm,1,'Figure 2, PDF page 6; (S) experimental name PDF page 11')
    add('19b','O=C(N(CCO)'+b+')Nc1ccc(-c2cn[nH]c2)cc1OCCO',1,'Figure 2, PDF page 6','<')
    add('19c','O=C(N(CCN(C)C)'+b+')Nc1ccc(-c2cn[nH]c2)cc1OCCN(C)C',170,'Figure 2, PDF page 6')
    add('20','O=C(N(CCN(C)C)'+b+')Nc1ccc(-c2cn[nH]c2)cn1',2,'Figure 2, PDF page 6')
    return rows

def reconcile(acts):
    by={}
    for r in acts: by.setdefault(canon(r['canonical_smiles']),[]).append(r)
    reconciled=[]; excluded=[]; matched=set(); audit=[]
    for s in primary_rows():
        found=by.get(s['expected_canonical_smiles'],[])
        if len(found)!=1: raise ValueError(f"{s['source_compound_number']}: expected unique structure match; found {len(found)}")
        r=found[0]; matched.add(r['activity_id'])
        if r['standard_units']!='nM' or r['standard_relation']!=s['primary_relation'] or float(r['standard_value'])!=s['primary_value_nM']:
            raise ValueError('Source/database value disagreement: '+s['source_compound_number'])
        row={**s,'molecule_id':r['molecule_chembl_id'],'activity_id':r['activity_id'],'canonical_smiles':r['canonical_smiles'],'identity_verified':True,'original_value_nM':float(r['standard_value']),'corrected_value_nM':s['primary_value_nM'],'corrected_relation':s['primary_relation']}
        audit.append(row)
        reason=None
        if s['source_compound_number']=='12h':reason='Table 4 gives 1 nM, narrative page 4 gives <1 nM; conflicting exact/censored source, excluded.'
        elif s['primary_relation']!='=':reason='Primary censored value; not an exact concentration.'
        if reason:excluded.append({'activity_id':r['activity_id'],'molecule_id':r['molecule_chembl_id'],'source_compound_number':s['source_compound_number'],'reason':reason})
        else:reconciled.append(row)
    if matched!={r['activity_id'] for r in acts}:raise ValueError('Unreconciled database activities')
    return {'assay_id':'CHEMBL2341182','reconciled_rows':reconciled,'excluded_records':excluded,'all_source_rows':audit,'counts':{'source_rows':len(audit),'eligible_exact':len(reconciled),'excluded_records':len(excluded)},'identity_policy':'Independently transcribed primary R groups / names assembled into SMILES; unique canonical isomeric graph join first, then value/relation comparison. No potency-only matching.','sources':{'doi':'10.1021/jm400062r','article':'data/raw/phase20/urea2013/article.pdf','version':'accepted/proof copy','locations':'Tables1–5 and Figure2; experimental19a(S) and12n names'},'limits':['Primary table means of >=2 experiments; stated errors within30% of mean, no raw replicates available.','5b and5j are cited comparators not present in this ChEMBL assay export.','No values pooled with other ROCK2 readouts.']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--activities',default='data/raw/phase20/inventory/CHEMBL2341182-activities.json');p.add_argument('--output',default='data/phase21/source-table-reconciliation.json');a=p.parse_args()
    raw=Path(a.activities);out=reconcile(json.loads(raw.read_text())['activities'])
    out['input_sha256']={str(raw):hashlib.sha256(raw.read_bytes()).hexdigest(),out['sources']['article']:hashlib.sha256(Path(out['sources']['article']).read_bytes()).hexdigest()}
    Path(a.output).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out['counts']))
if __name__=='__main__':main()
