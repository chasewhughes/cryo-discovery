"""Reproduce provisional identity overlap and fixed scaffold-split eligibility."""
import json
from pathlib import Path
from rdkit.Chem.Scaffolds import MurckoScaffold
from scripts.prepare_rock_orthogonal import identity,split_rows,sha
ROOT=Path(__file__).resolve().parents[1]
def main():
    old=json.loads((ROOT/'data/phase15/rock-benchmark.json').read_text())['exact_compounds']+json.loads((ROOT/'data/phase18/external-dataset.json').read_text())['exact_compounds']
    ids={r['molecule_id'] for r in old};structures={identity(r['canonical_smiles'])[1] for r in old};result=[]
    for assay in ['CHEMBL1686688','CHEMBL1219161']:
        path=ROOT/f'data/raw/phase17/external-review/{assay}-activities.json'
        records=json.loads(path.read_text())['activities'];rows=[];overlap=[]
        for r in records:
            if r['standard_relation']!='=' or r['standard_type']!='IC50' or r['standard_units']!='nM' or r.get('data_validity_comment'):continue
            sm,achiral,mol=identity(r['canonical_smiles'])
            if r['molecule_chembl_id'] in ids or achiral in structures:overlap.append(r['molecule_chembl_id']);continue
            rows.append({'molecule_id':r['molecule_chembl_id'],'scaffold':MurckoScaffold.MurckoScaffoldSmiles(mol=mol)})
        info={'assay_id':assay,'source_path':str(path.relative_to(ROOT)),'source_sha256':sha(path),'provisional_exact_n':len(rows),'overlap_ids':overlap,'scaffold_n':len({r['scaffold'] for r in rows}),'source_labels_reconciled':False}
        try:
            s=split_rows(rows);info.update(split_viable=True,calibration_n=len(s['calibration_ids']),test_n=len(s['test_ids']),split=s)
        except ValueError as e:info.update(split_viable=False,reason=str(e))
        result.append(info)
    out={'scope':'Provisional database identity/split audit only; primary source eligibility remains separate.','selection_policy_sha256':sha(ROOT/'data/phase19/selection-policy.json'),'candidates':result}
    (ROOT/'data/phase19/candidate-identity-audit.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
