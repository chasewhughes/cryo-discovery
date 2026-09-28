"""Independently validate serialized preparation identity and stereochemistry."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors
try:
    from .calibrate_hydration_sampling import sha,write
except ImportError:
    from calibrate_hydration_sampling import sha,write
ROOT=Path(__file__).resolve().parents[1]

def main():
    plan=json.loads((ROOT/'data/phase13/sampling-plan.json').read_text());rows=[]
    for job in plan['jobs']:
        directory=ROOT/'data/raw/phase13/prepared'/job['id'];r=json.loads((directory/'result.json').read_text())
        state=ET.parse(directory/'final-state.xml').getroot()
        xyz=np.array([[float(a.attrib[k]) for k in 'xyz'] for a in state.find('Positions')])
        box=np.array([[float(a.attrib[k]) for k in 'xyz'] for a in state.find('PeriodicBoxVectors')]);lengths=np.diag(box)
        mol=Chem.AddHs(Chem.MolFromSmiles(r['source_smiles']));Chem.RemoveStereochemistry(mol)
        conformer=Chem.Conformer(mol.GetNumAtoms())
        # Reconstruct each solute atom relative to atom zero under the periodic box.
        positions=xyz[:mol.GetNumAtoms()]-xyz[0];positions-=lengths*np.rint(positions/lengths)
        for i,p in enumerate(positions):conformer.SetAtomPosition(i,p*10)
        mol.AddConformer(conformer);Chem.AssignAtomChiralTagsFromStructure(mol,replaceExistingTags=True);Chem.AssignStereochemistry(mol,cleanIt=True,force=True)
        centers=Chem.FindMolChiralCenters(mol,includeUnassigned=True,includeCIP=True)
        if len(centers)!=(1 if job['compound']=='leu' else 2) or any(c!='S' for _,c in centers):raise ValueError('Minimized 3D stereo mismatch')
        if rdMolDescriptors.CalcMolFormula(mol)!='C6H13NO2' or mol.GetNumAtoms()!=22:raise ValueError('Formula/size mismatch')
        system=ET.parse(directory/'system.xml').getroot();forces=[f for f in system.iter('Force') if f.attrib.get('type')=='NonbondedForce']
        if len(forces)!=1:raise ValueError('Unexpected nonbonded force count')
        charge=sum(float(a.attrib['q']) for a in list(forces[0].find('Particles'))[:22])
        if abs(charge)>1e-8:raise ValueError('Solute charge mismatch')
        volumes=[]
        for center,_ in centers:
            neighbors=sorted(a.GetIdx() for a in mol.GetAtomWithIdx(center).GetNeighbors())
            if len(neighbors)!=4:raise ValueError('Unexpected tetrahedral center')
            delta=xyz[neighbors]-xyz[center];delta-=lengths*np.rint(delta/lengths)
            volume=float(np.linalg.det(delta[:3]-delta[3]))
            if abs(volume)<1e-6:raise ValueError('Near-planar stereocenter')
            volumes.append({'center_index':center,'neighbors':neighbors,'signed_volume_nm3':volume})
        rows.append({'job_id':job['id'],'formula':'C6H13NO2','solute_atoms':22,'stereochemistry_from_minimized_coordinates':centers,
            'serialized_solute_charge_e':charge,'stereocenter_volumes':volumes,'state_sha256':sha(directory/'final-state.xml')})
    write(ROOT/'data/phase13/preparation-identity-audit.json',{'runs':rows,'all_six_passed':True,'script_sha256':sha(__file__)})
    print('All six serialized states: same formula, neutral charge, correct minimized 3D stereochemistry')
if __name__=='__main__':main()
