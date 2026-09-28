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

def resolve_locations(plan, map_path=None):
    path=Path(map_path or ROOT/'data/phase13/result-locations.json')
    if not path.is_file(): raise ValueError('Explicit result-locations map is required')
    raw=json.loads(path.read_text()); locations=raw.get('locations',raw) if isinstance(raw,dict) else None
    ids={j['id'] for j in plan['jobs']}
    if not isinstance(locations,dict) or set(locations)!=ids: raise ValueError('Result map must contain exactly frozen job IDs')
    base=(ROOT/'data/raw/phase13').resolve(); resolved={}
    for jid,value in locations.items():
        if not isinstance(value,str): raise ValueError('Result map paths must be strings')
        rel=Path(value)
        if rel.is_absolute() or '..' in rel.parts: raise ValueError('Unsafe result map path')
        if rel.parts[:3] == ('data','raw','phase13'): rel=Path(*rel.parts[3:])
        if len(rel.parts)!=4 or rel.parts[1]!=jid or rel.parts[0] not in {'runpod-attempt2','runpod-attempt3'} or rel.parts[-2:] != ('runs',jid): raise ValueError('Result map path must end in allowed attempt/runs/job ID')
        target=(base/rel).resolve()
        if base not in target.parents or not (target/'result.json').is_file(): raise ValueError('Mapped result path missing or escapes raw storage')
        resolved[jid]=target
    return resolved

def check_stereocenters(coords, boxes, centers):
    """Detect tetrahedral inversions relative to independently audited starting states."""
    checks=[]
    lengths=np.diagonal(boxes,axis1=1,axis2=2)[:,None,:]
    for row in centers:
        delta=coords[:,row['neighbors'],:].astype(float)-coords[:,row['center_index'],None,:]
        delta-=lengths*np.rint(delta/lengths)
        volumes=np.linalg.det(delta[:,:3]-delta[:,3,None,:])
        if np.any(np.sign(volumes)!=np.sign(row['signed_volume_nm3'])) or np.min(np.abs(volumes))<1e-6:
            raise ValueError('Stereocenter inverted or became near planar')
        checks.append({'center_index':row['center_index'],'minimum_absolute_volume_nm3':float(np.min(np.abs(volumes))),'all_frames_preserve_starting_handedness':True})
    return checks

def tree_without_rng(path):
    tree=ET.parse(path).getroot()
    def normalize(node):
        attrs={k:v for k,v in node.attrib.items() if k!='randomSeed'}
        return node.tag,sorted(attrs.items()),(node.text or '').strip(),[normalize(c) for c in node]
    return normalize(tree)

def verify_run(path,job):
    parent=ROOT/'data/raw/phase13/prepared'/job['parent_id']
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
        if len(coords)!=1000 or len(wat)!=2070 or len(sol)!=22:raise ValueError('Unmatched particle count or incomplete production')
        audit=json.loads((ROOT/'data/phase13/preparation-identity-audit.json').read_text())
        identity=next(r for r in audit['runs'] if r['job_id']==job['id'])
        if identity['state_sha256']!=sha(parent/'final-state.xml'):raise ValueError('Audited starting state changed')
        stereo=check_stereocenters(coords,boxes,identity['stereocenter_volumes'])
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
        if int(final.attrib['stepCount'])!=5_500_000 or abs(float(final.attrib['time'])-11000)>1e-5:raise ValueError('Unexpected final production clock')
        statebox=np.array([[float(v.attrib[c]) for c in ['x','y','z']] for v in final.find('PeriodicBoxVectors')])
        np.testing.assert_allclose(statebox,boxes[-1],atol=1e-10)
        crystal=next(line for line in (path/'topology-final-box.pdb').read_text().splitlines() if line.startswith('CRYST1'))
        pdbbox=np.array([float(crystal[a:b])/10 for a,b in [(6,15),(15,24),(24,33)]])
        boxerror=float(abs(pdbbox-np.diag(boxes[-1])).max())
        if boxerror>5.01e-5:raise ValueError('PDB box mismatch')
        return {'job_id':job['id'],'frames_checked':len(coords),'max_OH_error_nm':maximum_oh,
                'max_OM_error_nm':maximum_om,'PDB_box_rounding_error_nm':boxerror,'physical_system_and_integrator_unchanged_except_rng':True,
                'stereocenter_checks':stereo}

def main():
    plan=json.loads((ROOT/'data/phase13/sampling-plan.json').read_text());deployment=json.loads((ROOT/'data/phase13/deployment-provenance.json').read_text())
    commit=deployment['deployed_source_commit']
    for name,expected in deployment['source_sha256'].items():
        blob=subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)
        if hashlib.sha256(blob).hexdigest()!=expected:raise ValueError('Pinned source mismatch: '+name)
    retry=json.loads((ROOT/'data/phase13/deployment-provenance-attempt3.json').read_text())
    for name,expected in retry['source_sha256'].items():
        blob=subprocess.check_output(['git','show',retry['deployed_source_commit']+':'+name],cwd=ROOT)
        if hashlib.sha256(blob).hexdigest()!=expected:raise ValueError('Pinned retry source mismatch: '+name)
    locations=resolve_locations(plan); rows=[]
    for job in plan['jobs']:
        path=locations[job['id']]
        attempt=path.parents[2].name
        manifest=retry if attempt=='runpod-attempt3' else deployment
        receipt=json.loads((ROOT/'data/phase13'/(attempt+'-'+job['id']+'-receipt.json')).read_text())
        worker='scripts/runpod_phase13_retry_worker.py' if attempt=='runpod-attempt3' else 'scripts/runpod_phase13_worker.py'
        if receipt.get('deleted') is not True or receipt.get('worker_status',{}).get('state')!='complete':raise ValueError('Successful result lacks completed/deleted receipt')
        if receipt['worker_sha256']!=manifest['source_sha256'][worker] or receipt['input_sha256']!=job['parent_sha256'] or receipt['plan_sha256']!=sha(ROOT/'data/phase13/sampling-plan.json'):raise ValueError('Launch provenance mismatch')
        for name,digest in receipt['code_sha256'].items():
            if digest!=manifest['source_sha256'][name]:raise ValueError('Launched source mismatch')
        result=json.loads((path/'result.json').read_text())
        if sha(path/'core-result.json')!=result['hashes']['core_result']:raise ValueError('Core result checksum mismatch')
        rows.append({**verify_run(path,job),'attempt':attempt,'source_commit':manifest['deployed_source_commit'],'completed_and_deleted_receipt_verified':True})
    models=json.loads((ROOT/'data/phase9/model-reservation.json').read_text())['models']
    for name,row in models.items():
        if sha(ROOT/row['local_path'])!=row['sha256']:raise ValueError('Reserved model changed: '+name)
    result={'status':'Passed artifact and physical-configuration checks; no efficacy validation','frames_checked':sum(r['frames_checked'] for r in rows),'runs':rows,'reserved_models_unchanged':True,'deployed_commit_verified':commit,'retry_commit_verified':retry['deployed_source_commit'],'script_sha256':sha(__file__)}
    write(ROOT/'data/phase13/numerical-verification.json',result)
    print(json.dumps({'frames_checked':result['frames_checked'],'all_checks_passed':True}))
if __name__=='__main__':main()
