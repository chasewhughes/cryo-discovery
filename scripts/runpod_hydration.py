"""Launch or collect this bounded cryo pilot using a locally stored RunPod key.

Creates at most one new, named Pod; never acts on unrelated account resources.
The worker deadline and local watchdog delete only that Pod. No API key is
saved in repository files, process arguments, logs, or returned result bundles.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT/'data/raw/phase10/runpod'


def key():
    return subprocess.check_output(['security','find-generic-password','-s','cryo.runpod.api-key','-w'],text=True).strip()


def api(method, endpoint, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request('https://rest.runpod.io/v1/'+endpoint, data=data,
          method=method, headers={'Authorization':'Bearer '+key(),'Content-Type':'application/json','User-Agent':'cryo-research/0.1'})
    with urllib.request.urlopen(req, timeout=40) as response:
        body = response.read()
        return json.loads(body) if body else None


def write_json(path, data):
    path.write_text(json.dumps(data,indent=2)+'\n')


def check_budget(receipts):
    if any(not r.get('deleted') for r in receipts):
        raise ValueError('A previous attempt lacks confirmed deletion')
    spent = sum(float(r['estimated_gpu_cost_usd']) for r in receipts)
    # Reserve the maximum 90-minute quote plus a conservative disk allowance.
    if spent + .8*1.5 + .1 > 3:
        raise ValueError('Phase 10 pilot budget would be exceeded')


def delete_pod(state):
    try:
        p = api('GET','pods/'+state['id'])
        if p.get('name') != state['name']: raise ValueError('Pod identity changed')
        api('DELETE','pods/'+state['id'])
    except urllib.error.HTTPError as exc:
        if exc.code != 404: raise
    try:
        api('GET','pods/'+state['id'])
    except urllib.error.HTTPError as exc:
        if exc.code == 404: return True
        raise
    return False


def watchdog(state):
    # Independent process survives interruption of the interactive client.
    while time.time() < state['deadline_epoch']: time.sleep(min(30,state['deadline_epoch']-time.time()))
    for attempt in range(20):
        try:
            if delete_pod(state):
                write_json(LOCAL/'watchdog-result.json',{'pod_id':state['id'],'deleted':True,'epoch':time.time()})
                return
        except Exception:
            pass
        time.sleep(15)
    write_json(LOCAL/'watchdog-result.json',{'pod_id':state['id'],'deleted':False,'requires_followup':True})


def launch():
    LOCAL.mkdir(parents=True,exist_ok=True)
    if (LOCAL/'state.json').exists(): raise ValueError('Pilot already has a state record; inspect/collect it before any new rental')
    check_budget([json.loads(p.read_text()) for p in (ROOT/'data/phase10').glob('runpod*receipt.json')])
    token = secrets.token_urlsafe(32)
    token_path = LOCAL/'transfer-token'
    fd = os.open(token_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as handle: handle.write(token)
    worker = (ROOT/'scripts/runpod_pilot_worker.py').read_bytes()
    inputs = {p:(ROOT/p).read_text() for p in ['scripts/run_hydration_pilot.py','simulation/tip4p-ice.xml','requirements-md-cuda.txt']}
    deadline = time.time()+5400
    bootstrap = "import os,base64;exec(compile(base64.b64decode(os.environ['CRYO_WORKER_B64']),'<cryo-worker>','exec'))"
    name = 'cryo-hydration-phase10-'+secrets.token_hex(3)
    payload = {'name':name,'cloudType':'SECURE','computeType':'GPU',
      'gpuTypeIds':['NVIDIA GeForce RTX 4090'],'gpuCount':1,'gpuTypePriority':'custom',
      'allowedCudaVersions':['12.4','12.5','12.6','12.7','12.8','12.9','13.0'],
      'imageName':'python:3.13-slim','containerDiskInGb':10,'volumeInGb':0,
      'minRAMPerGPU':8,'minVCPUPerGPU':2,'interruptible':False,
      'ports':['8080/http'],'dockerEntrypoint':['python','-u','-c'], 'dockerStartCmd':[bootstrap],
      'env':{'CRYO_WORKER_B64':base64.b64encode(worker).decode(),
             'CRYO_INPUTS_B64':base64.b64encode(json.dumps(inputs).encode()).decode(),
             'CRYO_TRANSFER_TOKEN':token,'CRYO_RUNPOD_KEY':key(),'CRYO_DEADLINE_EPOCH':str(deadline)}}
    # Do not persist payload: it contains ephemeral and account credentials.
    pod = api('POST','pods',payload)
    state = {'id':pod['id'],'name':name,'created_epoch':time.time(),'deadline_epoch':deadline,
             'cost_per_hour':float(pod.get('costPerHr') or 999),'container_disk_gb':10,'volume_gb':0,
             'input_sha256':{p:hashlib.sha256(v.encode()).hexdigest() for p,v in inputs.items()},
             'worker_sha256':hashlib.sha256(worker).hexdigest()}
    write_json(LOCAL/'state.json',state)
    with (LOCAL/'watchdog.log').open('w') as log:
        proc = subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'watchdog'],cwd=ROOT,
                   stdout=log,stderr=log,start_new_session=True)
    state['watchdog_pid'] = proc.pid; write_json(LOCAL/'state.json',state)
    if state['cost_per_hour'] > .8:
        removed = delete_pod(state)
        raise ValueError(f'Quoted GPU rate exceeds pilot limit; deletion confirmed={removed}')
    print(json.dumps({'pod_id':state['id'],'gpu_rate_usd_per_hour':state['cost_per_hour'],
                      'maximum_lifetime_minutes':90,'status':'launched'}))


def status(state):
    pod = api('GET','pods/'+state['id'])
    print(json.dumps({'pod_status':pod.get('desiredStatus'),'rate':pod.get('costPerHr')}))
    req = urllib.request.Request(f'https://{state["id"]}-8080.proxy.runpod.net/status',
                headers={'Authorization':'Bearer '+(LOCAL/'transfer-token').read_text(),'User-Agent':'cryo-research/0.1'})
    try:
        with urllib.request.urlopen(req,timeout=20) as response: result=json.load(response)
        print(json.dumps(result)); return result
    except urllib.error.HTTPError as exc:
        print(json.dumps({'worker_http_status':exc.code})); return None


def collect(state):
    result = status(state)
    if not result or not result.get('results_ready'): raise ValueError('Results are not ready')
    req = urllib.request.Request(f'https://{state["id"]}-8080.proxy.runpod.net/results',
            headers={'Authorization':'Bearer '+(LOCAL/'transfer-token').read_text(),'User-Agent':'cryo-research/0.1'})
    path = LOCAL/'results.tar.gz'
    total = 0
    with urllib.request.urlopen(req,timeout=60) as response, path.open('wb') as handle:
        while chunk := response.read(1024*1024):
            total += len(chunk)
            if total > 250_000_000: raise ValueError('Unexpected result size')
            handle.write(chunk)
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        if sum(m.size for m in members)>500_000_000: raise ValueError('Unexpected expanded size')
        for m in members:
            if not (m.isfile() or m.isdir()) or not m.name.startswith('runs/') and m.name!='runs':
                raise ValueError('Unexpected archive member')
        archive.extractall(LOCAL,filter='data')
    confirmed = delete_pod(state)
    ended = time.time()
    receipt = {**state,'deleted':confirmed,'ended_epoch':ended,
        'elapsed_hours':(ended-state['created_epoch'])/3600,
        'estimated_gpu_cost_usd':(ended-state['created_epoch'])/3600*state['cost_per_hour'],
        'cost_note':'Elapsed time times quoted GPU rate; not the final provider invoice. Container disk billing may be additional.',
        'result_archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'result_archive_bytes':total,
        'worker_status':result}
    write_json(ROOT/'data/phase10/runpod-receipt.json',receipt)
    print(json.dumps({'results_bytes':total,'deletion_confirmed':confirmed,'estimated_gpu_cost_usd':receipt['estimated_gpu_cost_usd']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['launch','status','collect','watchdog','delete'])
    action = parser.parse_args().action
    if action == 'launch': launch()
    else:
        state = json.loads((LOCAL/'state.json').read_text())
        if action == 'watchdog': watchdog(state)
        elif action == 'status': status(state)
        elif action == 'collect': collect(state)
        else: print(json.dumps({'deletion_confirmed':delete_pod(state)}))
