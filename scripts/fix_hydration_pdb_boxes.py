"""Write corrected final-box PDB copies; preserve original cloud outputs."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def corrected_pdb(text, box_nm):
    box=np.asarray(box_nm)
    if box.shape!=(3,3) or not np.allclose(box,np.diag(np.diag(box))) or np.any(np.diag(box)<=0):
        raise ValueError('Expected positive orthorhombic box')
    lines=text.splitlines(keepends=True)
    indices=[i for i,line in enumerate(lines) if line.startswith('CRYST1')]
    if len(indices)!=1: raise ValueError('Expected exactly one CRYST1 record')
    i=indices[0]; a,b,c=np.diag(box)*10
    lines[i]=f'CRYST1{a:9.3f}{b:9.3f}{c:9.3f}{90:7.2f}{90:7.2f}{90:7.2f}'+lines[i][54:]
    return ''.join(lines)


def main():
    plan=json.loads((ROOT/'data/phase11/stability-plan.json').read_text()); rows=[]
    for job in plan['jobs']:
        name=f"{job['compound']}-{job['ensemble']}-{job['seed']}"
        directory=ROOT/'data/raw/phase11/runpod/runs'/name
        original=directory/'topology.pdb'
        with np.load(directory/'trajectory.npz') as d: box=d['boxes_nm'][-1]
        updated=directory/'topology-final-box.pdb'
        updated.write_text(corrected_pdb(original.read_text(),box))
        rows.append({'run':name,'original_pdb_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
            'corrected_pdb_sha256':hashlib.sha256(updated.read_bytes()).hexdigest(),
            'final_box_nm':box.tolist(),'path':str(updated.relative_to(ROOT))})
    result={'status':'Corrected companion PDB CRYST1 metadata only; original files preserved',
        'cause':'Cloud runner wrote original topology box with final coordinates; NPT trajectory and state boxes were already correct.',
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'runs':rows}
    (ROOT/'data/phase11/pdb-box-corrections.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'Wrote {len(rows)} corrected PDB copies; no trajectory changes')


if __name__=='__main__':main()
