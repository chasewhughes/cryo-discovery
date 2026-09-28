"""Independent serialized-physics, geometry and source-preservation checks."""
import json,hashlib,subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
try:
    from .calibrate_hydration_sampling import sha,write
except ImportError:
    from calibrate_hydration_sampling import sha,write
ROOT=Path(__file__).resolve().parents[1]

def tree_without_rng(path):
    tree=ET.parse(path).getroot()
    def normalize(node):
        attrs={k:v for k,v in node.attrib.items() if k!='randomSeed'}
        return node.tag,sorted(attrs.items()),(node.text or '').strip(),[normalize(c) for c in node]
    return normalize(tree)

def verify_run(path,job):
    parent=ROOT/'data/raw/phase11/runpod/runs'/job['parent_id']
    for name in ['system.xml','integrator.xml']:
        if tree_without_rng(parent/name)!=tree_without_rng(path/name):raise ValueError('Physical model changed: '+name)
    integrator=ET.parse(path/'integrator.xml').getroot()
    if int(integrator.attrib['randomSeed'])!=job['seed']:raise ValueError('Incorrect thermostat seed')
    system=ET.parse(path/'system.xml').getroot()
    bars=[x for x in system.iter('Force') if x.attrib.get('type')=='MonteCarloBarostat']
    if len(bars)!=(1 if job['ensemble']=='NPT' else 0):raise ValueError('Wrong barostat count')
    if bars and int(bars[0].attrib['randomSeed'])!=job['seed']+100000:raise ValueError('Incorrect barostat seed')
    with np.load(path/'trajectory.npz') as d:
        coords=d['positions_nm'];boxes=d['boxes_nm'];wat=d['water_oxygen_indices'];sol=d['solute_indices']
        if not np.all(np.diff(wat)==4):raise ValueError('Unexpected water topology ordering')
        maximum_oh=maximum_om=0.
        for start in range(0,len(coords),100):
            xyz=coords[start:start+100].astype(float);lengths=np.diagonal(boxes[start:start+100],axis1=1,axis2=2)[:,None,:]
            for offset,expected in [(1,.09572),(2,.09572),(3,.01577)]:
                delta=xyz[:,wat+offset]-xyz[:,wat];delta-=lengths*np.rint(delta/lengths)
                error=float(np.abs(np.linalg.norm(delta,axis=2)-expected).max())
                if offset==3:maximum_om=max(maximum_om,error)
                else:maximum_oh=max(maximum_oh,error)
        if maximum_oh>5e-6 or maximum_om>5e-6:raise ValueError('Rigid water geometry failed')
        final=ET.parse(path/'final-state.xml').getroot()
        if int(final.attrib['stepCount'])!=5_050_000 or abs(float(final.attrib['time'])-10100)>1e-5:raise ValueError('Unexpected final production clock')
        statebox=np.array([[float(v.attrib[c]) for c in ['x','y','z']] for v in final.find('PeriodicBoxVectors')])
        np.testing.assert_allclose(statebox,boxes[-1],atol=1e-10)
        crystal=next(line for line in (path/'topology-final-box.pdb').read_text().splitlines() if line.startswith('CRYST1'))
        pdbbox=np.array([float(crystal[a:b])/10 for a,b in [(6,15),(15,24),(24,33)]])
        boxerror=float(abs(pdbbox-np.diag(boxes[-1])).max())
        if boxerror>5.01e-5:raise ValueError('PDB box mismatch')
        return {'job_id':job['id'],'frames_checked':len(coords),'max_OH_error_nm':maximum_oh,
                'max_OM_error_nm':maximum_om,'PDB_box_rounding_error_nm':boxerror,'physical_system_and_integrator_unchanged_except_rng':True}

def main():
    plan=json.loads((ROOT/'data/phase12/sampling-plan.json').read_text());deployment=json.loads((ROOT/'data/phase12/deployment-provenance.json').read_text())
    commit=deployment['deployed_source_commit']
    for name,expected in deployment['source_sha256'].items():
        blob=subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)
        if hashlib.sha256(blob).hexdigest()!=expected:raise ValueError('Pinned source mismatch: '+name)
    rows=[]
    for job in plan['jobs']:
        path=ROOT/'data/raw/phase12/runpod-attempt2'/job['id']/'runs'/job['id']
        rows.append(verify_run(path,job))
    models=json.loads((ROOT/'data/phase9/model-reservation.json').read_text())['models']
    for name,row in models.items():
        if sha(ROOT/row['local_path'])!=row['sha256']:raise ValueError('Reserved model changed: '+name)
    result={'status':'Passed artifact and physical-configuration checks; no efficacy validation','frames_checked':sum(r['frames_checked'] for r in rows),'runs':rows,'reserved_models_unchanged':True,'deployed_commit_verified':commit,'script_sha256':sha(__file__)}
    write(ROOT/'data/phase12/numerical-verification.json',result)
    print(json.dumps({'frames_checked':result['frames_checked'],'all_checks_passed':True}))
if __name__=='__main__':main()
