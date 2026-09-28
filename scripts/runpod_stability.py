"""Bounded Phase 11 RunPod launcher and collector."""
import argparse, base64, hashlib, json, math, os, secrets, subprocess, sys, tarfile, time
from datetime import datetime, timezone
from pathlib import Path
import urllib.error, urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'data/raw/phase11/runpod'
PLAN = ROOT / 'data/phase11/stability-plan.json'
RECEIPT = ROOT / 'data/phase11/runpod-receipt.json'
MAX_RATE, MAX_LIFETIME, PHASE_RESERVE, MARGIN = .8, 10800, 3.0, .3

def key():
    return subprocess.check_output(['security','find-generic-password','-s','cryo.runpod.api-key','-w'], text=True).strip()

def api(method, endpoint, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request('https://rest.runpod.io/v1/'+endpoint, data=data, method=method,
        headers={'Authorization':'Bearer '+key(), 'Content-Type':'application/json', 'User-Agent':'cryo-research/0.1'})
    with urllib.request.urlopen(req, timeout=40) as response:
        body = response.read(); return json.loads(body) if body else None

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, indent=2)+'\n')

def prior_receipts():
    receipts = []
    for path in (ROOT/'data').glob('phase*/runpod*receipt.json'):
        try: receipt = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc: raise ValueError(f'invalid receipt: {path}') from exc
        ident = receipt.get('id') or receipt.get('pod_id')
        if not ident: raise ValueError(f'receipt missing pod id: {path}')
        receipts.append(receipt)
    return receipts

def check_budget(receipts=None, reconciliation=None, plan=None):
    receipts = prior_receipts() if receipts is None else receipts
    unique = {}
    for receipt in receipts:
        ident = receipt.get('id') or receipt.get('pod_id')
        if not ident: raise ValueError('receipt missing pod id')
        try: cost=float(receipt['estimated_gpu_cost_usd'])
        except (KeyError, TypeError, ValueError): raise ValueError('invalid receipt cost')
        if cost < 0 or not math.isfinite(cost): raise ValueError('invalid receipt cost')
        old=unique.get(str(ident))
        unique[str(ident)] = {**receipt, 'deleted':receipt.get('deleted') is True and (old is None or old['deleted']),
            'estimated_gpu_cost_usd':max(cost,old['estimated_gpu_cost_usd'] if old else 0)}
    receipts = list(unique.values())
    costs=[]
    for r in receipts:
        try: cost=float(r.get('estimated_gpu_cost_usd', 0))
        except (TypeError, ValueError): raise ValueError('invalid receipt cost')
        if cost < 0 or not __import__('math').isfinite(cost): raise ValueError('invalid receipt cost')
        costs.append(cost)
    if any(not r.get('deleted') for r in receipts):
        raise ValueError('a prior research pod lacks confirmed deletion')
    reconciliation = ROOT/'data/phase11/billing-reconciliation.json' if reconciliation is None else Path(reconciliation)
    if not reconciliation.is_file(): raise ValueError('billing reconciliation is required')
    rec = json.loads(reconciliation.read_text())
    verified = rec.get('verified_at')
    try:
        stamp=datetime.fromisoformat(str(verified).replace('Z','+00:00'))
        if stamp.tzinfo is None: raise ValueError('timezone required')
        age=time.time()-stamp.timestamp(); stale=age < 0 or age >= 86400
    except (TypeError, ValueError, OverflowError): stale = True
    if stale or rec.get('all_prior_research_pods_absent') is not True: raise ValueError('billing reconciliation is stale or incomplete')
    spent = sum(costs)
    try: reserve = float(rec.get('prior_gpu_reserve_usd'))
    except (TypeError, ValueError): raise ValueError('invalid prior reserve')
    if reserve < 0 or not __import__('math').isfinite(reserve): raise ValueError('invalid prior reserve')
    if max(spent, reserve) + MAX_RATE*3 + MARGIN > 10: raise ValueError('cumulative GPU budget would be exceeded')
    if MAX_RATE*3 + MARGIN > PHASE_RESERVE: raise ValueError('Phase 11 reserve exceeds phase limit')

def check_quote():
    quote=json.loads((ROOT/'data/phase11/gpu-quote.json').read_text())
    stamp=datetime.fromisoformat(quote['checked_at'].replace('Z','+00:00'))
    rows=quote['response']['data']['gpuTypes']
    if len(rows)!=1 or rows[0]['id']!='NVIDIA GeForce RTX 4090': raise ValueError('Wrong GPU quote')
    rate=float(rows[0]['securePrice'])
    if stamp.tzinfo is None or not 0 <= time.time()-stamp.timestamp() <= 3600 or not 0 < rate <= MAX_RATE:
        raise ValueError('GPU quote stale or outside limit')
    return rate

def delete_pod(state):
    try: current = api('GET','pods/'+state['id'])
    except urllib.error.HTTPError as exc:
        if exc.code == 404: return True
        raise
    if current.get('name') != state['name']: raise ValueError('Pod identity changed')
    try: api('DELETE','pods/'+state['id'])
    except urllib.error.HTTPError as exc:
        if exc.code != 404: raise
    try: api('GET','pods/'+state['id'])
    except urllib.error.HTTPError as exc:
        if exc.code == 404: return True
        raise
    return False

def stop_watchdog(state):
    pid = state.get('watchdog_pid')
    if not pid: return False
    try:
        result=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True,check=False)
        argv=result.stdout.strip()
        if str(Path(__file__).resolve()) not in argv or 'watchdog' not in argv: return False
        os.kill(pid, 15); return True
    except (OSError, UnicodeDecodeError): return False

def watchdog(state):
    while time.time() < state['deadline_epoch']: time.sleep(min(30, state['deadline_epoch']-time.time()))
    for _ in range(20):
        try:
            if delete_pod(state): write_json(LOCAL/'watchdog-result.json', {'pod_id':state['id'],'deleted':True}); return
        except Exception: pass
        time.sleep(15)
    write_json(LOCAL/'watchdog-result.json', {'pod_id':state['id'],'deleted':False,'requires_followup':True})

def launch():
    LOCAL.mkdir(parents=True, exist_ok=True)
    if (LOCAL/'state.json').exists(): raise ValueError('Phase 11 already has a state record')
    plan = json.loads(PLAN.read_text()); check_budget(plan=plan)
    cloud=plan.get('cloud',plan)
    if float(cloud.get('max_rate_usd_per_hour',-1)) != MAX_RATE or int(cloud.get('max_lifetime_seconds',-1)) != MAX_LIFETIME or int(cloud.get('per_run_timeout_seconds',-1)) != 1500: raise ValueError('plan cloud bounds do not match launcher')
    if len(plan.get('jobs',[]))!=12: raise ValueError('Expected 12 planned jobs')
    for job in plan['jobs']:
        if job.get('compound') not in ('gly','phe') or job.get('ensemble') not in ('NVT','NPT') or job.get('equilibration_ps')!=500 or job.get('production_ps')!=3000 or job.get('frames')!=300 or job.get('seed') not in (20260916,20260917,20260918): raise ValueError('invalid job bounds')
    check_quote()
    token = secrets.token_urlsafe(32); fd=os.open(LOCAL/'transfer-token',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f: f.write(token)
    names = ['scripts/run_hydration_stability.py','scripts/run_hydration_pilot.py','scripts/hydration_descriptor.py','simulation/tip4p-ice.xml','requirements-md-cuda.txt','data/phase11/stability-plan.json']
    inputs = {p:(ROOT/p).read_text() for p in names}; worker=(ROOT/'scripts/runpod_stability_worker.py').read_bytes()
    deadline=time.time()+MAX_LIFETIME
    bootstrap="import os,base64;exec(compile(base64.b64decode(os.environ['CRYO_WORKER_B64']),'<cryo-worker>','exec'))"
    name='cryo-stability-phase11-'+secrets.token_hex(3)
    payload={'name':name,'cloudType':'SECURE','computeType':'GPU','gpuTypeIds':['NVIDIA GeForce RTX 4090'],'gpuCount':1,'gpuTypePriority':'custom','allowedCudaVersions':['12.4','12.5','12.6','12.7','12.8','12.9','13.0'],'imageName':'python:3.13-slim','containerDiskInGb':10,'volumeInGb':0,'minRAMPerGPU':8,'minVCPUPerGPU':2,'interruptible':False,'ports':['8080/http'],'dockerEntrypoint':['python','-u','-c'],'dockerStartCmd':[bootstrap],'env':{'CRYO_WORKER_B64':base64.b64encode(worker).decode(),'CRYO_INPUTS_B64':base64.b64encode(json.dumps(inputs).encode()).decode(),'CRYO_TRANSFER_TOKEN':token,'CRYO_RUNPOD_KEY':key(),'CRYO_DEADLINE_EPOCH':str(deadline)}}
    pod=None; requested_at=time.time()
    try:
        pod=api('POST','pods',payload); rate=float(pod.get('costPerHr') or 999)
        state={'id':pod['id'],'name':name,'created_epoch':requested_at,'deadline_epoch':deadline,'cost_per_hour':rate,'input_sha256':{p:hashlib.sha256(v.encode()).hexdigest() for p,v in inputs.items()},'worker_sha256':hashlib.sha256(worker).hexdigest()}
        write_json(LOCAL/'state.json',state)
        proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'watchdog'],cwd=ROOT,stdout=(LOCAL/'watchdog.log').open('w'),stderr=subprocess.STDOUT,start_new_session=True)
        state['watchdog_pid']=proc.pid; write_json(LOCAL/'state.json',state)
        if rate > MAX_RATE:
            confirmed=delete_pod(state); raise ValueError(f'quoted GPU rate exceeds limit; deletion confirmed={confirmed}')
        print(json.dumps({'pod_id':state['id'],'gpu_rate_usd_per_hour':rate,'maximum_lifetime_seconds':MAX_LIFETIME,'status':'launched'}))
    except Exception as exc:
        if pod:
            cleanup_state=state if 'state' in locals() else {'id':pod.get('id'),'name':name}
            try:
                confirmed=delete_pod(cleanup_state)
                if not confirmed: raise RuntimeError('cleanup deletion unconfirmed')
                ended=time.time()
                write_json(RECEIPT, {**cleanup_state, 'deleted':True, 'ended_epoch':ended,
                    'estimated_gpu_cost_usd':(ended-requested_at)/3600*float(pod.get('costPerHr') or MAX_RATE), 'failure':type(exc).__name__})
                stop_watchdog(cleanup_state)
            except Exception as cleanup_exc: raise RuntimeError(f'launch failed and cleanup failed: {cleanup_exc}') from exc
        raise

def status(state):
    pod=api('GET','pods/'+state['id']); print(json.dumps({'pod_status':pod.get('desiredStatus'),'rate':pod.get('costPerHr')}))
    req=urllib.request.Request(f"https://{state['id']}-8080.proxy.runpod.net/status",headers={'Authorization':'Bearer '+(LOCAL/'transfer-token').read_text(),'User-Agent':'cryo-research/0.1'})
    try:
        with urllib.request.urlopen(req,timeout=20) as response: result=json.load(response)
        print(json.dumps(result)); return result
    except urllib.error.HTTPError as exc: print(json.dumps({'worker_http_status':exc.code})); return None

def collect(state):
    result=status(state)
    if not result or not result.get('results_ready'): raise ValueError('results are not ready')
    req=urllib.request.Request(f"https://{state['id']}-8080.proxy.runpod.net/results",headers={'Authorization':'Bearer '+(LOCAL/'transfer-token').read_text(),'User-Agent':'cryo-research/0.1'})
    path=LOCAL/'results.tar.gz'; total=0
    with urllib.request.urlopen(req,timeout=60) as response, path.open('wb') as handle:
        while chunk:=response.read(1024*1024):
            total+=len(chunk)
            if total>600_000_000: raise ValueError('compressed result exceeds 600 MB')
            handle.write(chunk)
    with tarfile.open(path) as archive:
        members=archive.getmembers()
        if sum(m.size for m in members)>1_000_000_000: raise ValueError('expanded result exceeds 1 GB')
        for m in members:
            if not (m.isfile() or m.isdir()) or not (m.name=='runs' or m.name.startswith('runs/')): raise ValueError('unexpected archive member')
        archive.extractall(LOCAL,filter='data')
    confirmed=delete_pod(state)
    if confirmed: stop_watchdog(state)
    ended=time.time()
    receipt={**state,'deleted':confirmed,'ended_epoch':ended,'elapsed_hours':(ended-state['created_epoch'])/3600,'estimated_gpu_cost_usd':(ended-state['created_epoch'])/3600*state['cost_per_hour'],'result_archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'result_archive_bytes':total,'worker_status':result}
    write_json(RECEIPT,receipt); print(json.dumps({'results_bytes':total,'deletion_confirmed':confirmed,'estimated_gpu_cost_usd':receipt['estimated_gpu_cost_usd']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['launch','status','collect','watchdog','delete']); a=p.parse_args().action
    if a=='launch': launch()
    else:
        s=json.loads((LOCAL/'state.json').read_text())
        if a=='watchdog': watchdog(s)
        elif a=='status': status(s)
        elif a=='collect': collect(s)
        else: print(json.dumps({'deletion_confirmed':delete_pod(s)}))
