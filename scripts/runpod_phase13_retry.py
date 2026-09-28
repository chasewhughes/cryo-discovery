"""Launch, inspect, collect, or clean up the three failed-setup jobs in Phase 13."""
import argparse, base64, hashlib, json, math, os, secrets, subprocess, sys, tarfile, time
from datetime import datetime
from pathlib import Path
import urllib.error, urllib.request

ROOT=Path(__file__).resolve().parents[1]; LOCAL=ROOT/'data/raw/phase13/runpod-attempt3'; PLAN=ROOT/'data/phase13/sampling-plan.json'
MAX_RATE=.8; MAX_LIFETIME=3600; MARGIN=.6; JOB_IDS=[f'{c}-NPT-{s}' for c,seeds in [('leu',[20261011,20261012,20261013]),('ile',[20261021,20261022,20261023])] for s in seeds]

RETRY_IDS=['leu-NPT-20261011','leu-NPT-20261012','ile-NPT-20261023']

def key(): return subprocess.check_output(['security','find-generic-password','-s','cryo.runpod.api-key','-w'],text=True).strip()
def api(method, endpoint, payload=None):
    data=None if payload is None else json.dumps(payload).encode(); req=urllib.request.Request('https://rest.runpod.io/v1/'+endpoint,data=data,method=method,headers={'Authorization':'Bearer '+key(),'Content-Type':'application/json','User-Agent':'cryo-research/0.1'})
    try:
        with urllib.request.urlopen(req,timeout=40) as r:
            body=r.read(); return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        # Preserve provider error text without request payloads or credentials.
        if method=='POST' and endpoint=='pods':
            body=exc.read(10000).decode(errors='replace')
            secrets_to_remove=[key()]+[p.read_text().strip() for p in LOCAL.glob('*/transfer-token')]
            for secret in secrets_to_remove:
                if secret:body=body.replace(secret,'[redacted]')
            write_json(LOCAL/'last-provider-error.json',{'http_status':exc.code,'response':body})
        raise
def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+secrets.token_hex(4)+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');os.replace(temporary,path)

def receipts():
    out=[]
    for p in (ROOT/'data').glob('phase*/runpod*receipt.json'):
        try: out.append(json.loads(p.read_text()))
        except Exception as e: raise ValueError('invalid receipt: '+str(p)) from e
    return out
def check_budget(previous=None, reconciliation=None):
    rows=receipts() if previous is None else previous; seen={}
    for r in rows:
        ident=str(r.get('id') or r.get('pod_id') or '')
        if not ident or 'estimated_gpu_cost_usd' not in r: raise ValueError('receipt missing identity or cost')
        cost=float(r['estimated_gpu_cost_usd'])
        if not math.isfinite(cost) or cost<0: raise ValueError('invalid receipt cost')
        if ident in seen and (seen[ident].get('deleted') != r.get('deleted') or seen[ident]['cost'] != cost): raise ValueError('conflicting duplicate receipt')
        seen[ident]={'deleted':r.get('deleted') is True,'cost':cost}
    if any(not r['deleted'] for r in seen.values()): raise ValueError('prior pod lacks confirmed deletion')
    rec=Path(reconciliation or ROOT/'data/phase13/billing-reconciliation.json')
    if not rec.is_file(): raise ValueError('fresh billing reconciliation is required')
    d=json.loads(rec.read_text()); stamp=d.get('verified_at')
    try:
      parsed=datetime.fromisoformat(str(stamp).replace('Z','+00:00'))
      if parsed.tzinfo is None: raise ValueError('timezone required')
      age=time.time()-parsed.timestamp()
    except Exception: age=10**9
    if not 0<=age<86400 or d.get('all_prior_research_pods_absent') is not True: raise ValueError('billing reconciliation is stale or incomplete')
    reserve=float(d.get('prior_gpu_reserve_usd',-1))
    if not math.isfinite(reserve) or reserve<0: raise ValueError('invalid reconciliation reserve')
    prior=max(sum(x['cost'] for x in seen.values()),reserve)
    if not math.isfinite(prior) or prior<0 or prior+6*MAX_RATE+MARGIN>10: raise ValueError('cumulative GPU budget would be exceeded')
def check_retry_reservation():
    old=json.loads((ROOT/'data/raw/phase13/runpod-attempt2/batch-state.json').read_text())
    if set(old)!=set(JOB_IDS):raise ValueError('Incomplete previous batch state')
    rows={str(r.get('id') or r.get('pod_id')):r for r in receipts()}
    for jid in RETRY_IDS:
        r=rows.get(old[jid]['pod_id'],{})
        if r.get('deleted') is not True or r.get('worker_status',{}).get('state')!='failed' or r.get('worker_status',{}).get('current'):
            raise ValueError('Retry requires deleted pre-simulation failure')
    outstanding={s['pod_id']:s for j,s in old.items() if j not in RETRY_IDS and s['pod_id'] not in rows}
    for s in outstanding.values():
        rate=float(s['cost_per_hour']);life=float(s['deadline_epoch'])-float(s['created_epoch'])
        if not math.isfinite(rate) or not 0<rate<=MAX_RATE or not 0<life<=MAX_LIFETIME:raise ValueError('Outstanding reservation outside bounds')
    pods=api('GET','pods')
    for pod in pods:
        if pod.get('name','').startswith('cryo-'):
            if pod['id'] not in outstanding:raise ValueError('Unreserved or already receipted research Pod remains active')
            s=outstanding[pod['id']]
            if pod.get('name')!=s['name'] or float(pod['costPerHr'])!=s['cost_per_hour']:raise ValueError('Outstanding Pod identity/rate changed')
    prior=max(sum(float(r['estimated_gpu_cost_usd']) for r in rows.values()),json.loads((ROOT/'data/phase13/billing-reconciliation.json').read_text())['prior_gpu_reserve_usd'])
    write_json(ROOT/'data/phase13/retry-reservation.json',{'checked_epoch':time.time(),'completed_gpu_reserve_usd':prior,'outstanding_pod_ids':list(outstanding),'outstanding_full_lifetime_reserve_usd':len(outstanding)*MAX_RATE,'retry_full_lifetime_reserve_usd':len(RETRY_IDS)*MAX_RATE,'margin_usd':MARGIN,'conservative_total_bound_usd':prior+6*MAX_RATE+MARGIN,'limit_usd':10,'note':'Full six-Pod reservation covers at most three outstanding original runs and three replacement runs; completed failures are additionally charged.'})

def quote():
    q=json.loads((ROOT/'data/phase13/gpu-quote.json').read_text()); stamp=datetime.fromisoformat(q['checked_at'].replace('Z','+00:00')); rows=q['response']['data']['gpuTypes']
    if stamp.tzinfo is None or not 0<=time.time()-stamp.timestamp()<=3600 or len(rows)!=1 or rows[0]['id']!='NVIDIA GeForce RTX 4090': raise ValueError('GPU quote stale or wrong GPU')
    rate=float(rows[0]['securePrice']);
    if not 0<rate<=MAX_RATE: raise ValueError('GPU quote exceeds limit')
    return rate
def plan_jobs():
    document=json.loads(PLAN.read_text()); cloud=document.get('cloud', document); jobs=document.get('jobs',[])
    if float(cloud.get('max_rate_usd_per_hour', -1)) != MAX_RATE or int(cloud.get('max_lifetime_seconds', -1)) != MAX_LIFETIME or int(cloud.get('per_run_timeout_seconds', -1)) != 1900: raise ValueError('plan cloud bounds do not match launcher')
    if float(cloud.get('batch_reserve_usd', -1)) != 6*MAX_RATE+MARGIN: raise ValueError('plan batch reserve exceeds launcher reserve')
    if len(jobs)!=6 or {j.get('id') for j in jobs} != set(JOB_IDS): raise ValueError('Phase 13 plan must contain exactly six required jobs')
    if any(not j.get('parent_id') for j in jobs): raise ValueError('each job must reference a parent_id')
    for j in jobs:
        if j.get('equilibration_ps')!=1000 or j.get('production_ps')!=10000 or j.get('frames')!=1000 or not isinstance(j.get('seed'),int): raise ValueError('invalid Phase 13 job bounds')
    if any(j['seed']!=j['parent_seed']+1000 or j['ensemble']!='NPT' for j in jobs): raise ValueError('Unexpected RNG mapping or ensemble')
    if {j['seed'] for j in jobs} != {20262011,20262012,20262013,20262021,20262022,20262023}: raise ValueError('invalid Phase 13 seeds')
    return {j['id']:j for j in jobs}
def parent_dir(job):
    value=job.get('parent_path') or job.get('input_path') or ('data/raw/phase13/prepared/'+job['parent_id'])
    p=(ROOT/value).resolve(); required=['system.xml','integrator.xml','final-state.xml','topology-final-box.pdb','result.json']
    if not all((p/x).is_file() for x in required): raise ValueError('parent input missing required state files: '+str(p))
    return p
def archive_parent(p):
    import io
    b=io.BytesIO()
    with tarfile.open(fileobj=b,mode='w:gz') as a: [a.add(p/x,arcname=x) for x in ['system.xml','integrator.xml','final-state.xml','topology-final-box.pdb','result.json']]
    data=b.getvalue()
    if len(data)>10_000_000: raise ValueError('compressed parent input exceeds 10 MB')
    return data
def delete_pod(s):
    try: cur=api('GET','pods/'+s['pod_id'])
    except urllib.error.HTTPError as e:
        if e.code==404:return True
        raise
    if cur.get('name')!=s['name']: raise ValueError('pod identity changed')
    try: api('DELETE','pods/'+s['pod_id'])
    except urllib.error.HTTPError as e:
        if e.code!=404: raise
    try: api('GET','pods/'+s['pod_id'])
    except urllib.error.HTTPError as e:
        if e.code==404:return True
        raise
    return False
def receipt_path(s):return ROOT/'data/phase13'/('runpod-attempt3-'+s['job_id']+'-receipt.json')

def finish(s,extra=None):
    confirmed=delete_pod(s);ended=time.time()
    record={**s,'deleted':confirmed,'ended_epoch':ended,'elapsed_hours':(ended-s['created_epoch'])/3600,
            'estimated_gpu_cost_usd':(ended-s['created_epoch'])/3600*s['cost_per_hour'],**(extra or {})}
    write_json(receipt_path(s),record)
    if confirmed:stop_watchdog(s)
    return record

def watchdog(state_path):
    s=json.loads(Path(state_path).read_text())
    while time.time()<s['deadline_epoch']:time.sleep(min(30,max(0,s['deadline_epoch']-time.time())))
    for _ in range(20):
        try:
            if delete_pod(s):
                ended=time.time()
                write_json(receipt_path(s),{**s,'deleted':True,'ended_epoch':ended,'estimated_gpu_cost_usd':(ended-s['created_epoch'])/3600*s['cost_per_hour'],'failure':'deadline watchdog'})
                return
        except Exception:pass
        time.sleep(15)
    write_json(Path(state_path).with_name('watchdog-failure.json'),{'pod_id':s['pod_id'],'deleted':False})

def stop_watchdog(s):
    pid=s.get('watchdog_pid')
    if not pid or pid==os.getpid():return False
    try:
        argv=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
        if str(Path(__file__).resolve()) not in argv or 'watchdog' not in argv:return False
        os.kill(int(pid),15);return True
    except OSError:return False

def worker_request(s,path,data=None,timeout=20):
    headers={'Authorization':'Bearer '+(LOCAL/s['job_id']/'transfer-token').read_text(),'User-Agent':'cryo-research/0.1'}
    if data is not None:headers['Content-Type']='application/gzip'
    return urllib.request.Request(f"https://{s['pod_id']}-8080.proxy.runpod.net/{path}",data=data,headers=headers)

def upload_input(s,packed):
    for _ in range(40):
        try:
            with urllib.request.urlopen(worker_request(s,'inputs',packed),timeout=20) as response:return json.load(response)
        except Exception as exc:
            if time.time()>s['deadline_epoch']-600:raise RuntimeError('Insufficient lifetime for input upload') from exc
            time.sleep(10)
    raise RuntimeError('Worker input upload failed')

def prepare():
    jobs=plan_jobs();check_budget();check_retry_reservation();quote();bundles={}
    for jid in RETRY_IDS:
        parent=parent_dir(jobs[jid]);packed=archive_parent(parent)
        hashes={name:hashlib.sha256((parent/name).read_bytes()).hexdigest() for name in ['system.xml','integrator.xml','final-state.xml','topology-final-box.pdb','result.json']}
        if jobs[jid]['parent_id']!=jid or hashes!=jobs[jid]['parent_sha256']:raise ValueError('Invalid parent identity/hashes')
        compound,ensemble,seed=jid.split('-')
        if (jobs[jid]['compound'],jobs[jid]['ensemble'],jobs[jid]['parent_seed'])!=(compound,ensemble,int(seed)):raise ValueError('Invalid parent metadata')
        bundles[jid]=(packed,hashes)
    code={name:(ROOT/name).read_text() for name in ['scripts/run_matched_hydration.py','scripts/run_hydration_extension.py','scripts/hydration_descriptor.py','requirements-md-cuda.txt']}
    deployment=json.loads((ROOT/'data/phase13/deployment-provenance.json').read_text())
    for name,value in code.items():
        if hashlib.sha256(value.encode()).hexdigest()!=deployment['source_sha256'][name]:raise ValueError('Source differs from frozen deployment')
    return jobs,bundles,code

def launch():
    from concurrent.futures import ThreadPoolExecutor
    jobs,bundles,code=prepare();LOCAL.mkdir(parents=True,exist_ok=True)
    lock=LOCAL/'batch-state.json'
    fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as handle:handle.write('{}\n')
    worker=(ROOT/'scripts/runpod_phase13_retry_worker.py').read_bytes();states={}
    try:
        for jid in RETRY_IDS:
            directory=LOCAL/jid;directory.mkdir(exist_ok=False)
            token=secrets.token_urlsafe(32)
            fd=os.open(directory/'transfer-token',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as handle:handle.write(token)
            packed,hashes=bundles[jid];requested=time.time();deadline=requested+MAX_LIFETIME
            name='cryo-phase13-'+jid+'-'+secrets.token_hex(3)
            write_json(directory/'intent.json',{'name':name,'job_id':jid,'requested_epoch':requested,'deadline_epoch':deadline})
            boot="import os,base64;exec(compile(base64.b64decode(os.environ['CRYO_WORKER_B64']),'<worker>','exec'))"
            payload={'name':name,'cloudType':'SECURE','computeType':'GPU','gpuTypeIds':['NVIDIA GeForce RTX 4090'],'gpuCount':1,'gpuTypePriority':'custom','allowedCudaVersions':['12.4','12.5','12.6','12.7','12.8','12.9','13.0'],'imageName':'python:3.13-slim','containerDiskInGb':10,'volumeInGb':0,'minRAMPerGPU':8,'minVCPUPerGPU':2,'interruptible':False,'ports':['8080/http'],'dockerEntrypoint':['python','-u','-c'],'dockerStartCmd':[boot],
                     'env':{'CRYO_WORKER_B64':base64.b64encode(worker).decode(),'CRYO_CODE_B64':base64.b64encode(json.dumps(code).encode()).decode(),'CRYO_JOB_B64':base64.b64encode(json.dumps(jobs[jid]).encode()).decode(),'CRYO_TRANSFER_TOKEN':token,'CRYO_RUNPOD_KEY':key(),'CRYO_DEADLINE_EPOCH':str(deadline),'CRYO_ARCHIVE_SHA256':hashlib.sha256(packed).hexdigest()}}
            if any(len(v.encode())>100_000 for v in payload['env'].values()):raise ValueError('Environment item exceeds launch bound')
            try:pod=api('POST','pods',payload)
            except Exception:
                # A timed-out POST can still have created a Pod. Never blindly retry POST.
                found=[]
                for _ in range(3):
                    found=[p for p in api('GET','pods') if p.get('name')==name]
                    if found:break
                    time.sleep(3)
                if len(found)!=1:raise
                pod=found[0]
            rate_value=pod.get('costPerHr')
            try:actual=float(rate_value)
            except (ValueError,TypeError):actual=MAX_RATE
            valid_rate=rate_value is not None and math.isfinite(actual) and 0<actual<=MAX_RATE
            if not math.isfinite(actual) or actual<=0:actual=MAX_RATE
            s={'job_id':jid,'pod_id':pod['id'],'name':name,'created_epoch':requested,'deadline_epoch':deadline,
               'cost_per_hour':actual,'input_sha256':hashes,'worker_sha256':hashlib.sha256(worker).hexdigest(),
               'code_sha256':{n:hashlib.sha256(v.encode()).hexdigest() for n,v in code.items()},'plan_sha256':hashlib.sha256(PLAN.read_bytes()).hexdigest()}
            states[jid]=s;write_json(directory/'state.json',s);write_json(lock,states)
            with (directory/'watchdog.log').open('w') as log:
                proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'watchdog',str(directory/'state.json')],stdout=log,stderr=log,start_new_session=True)
            s['watchdog_pid']=proc.pid;write_json(directory/'state.json',s);write_json(lock,states)
            if not valid_rate:raise ValueError('Provider rate invalid/outside limit')
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures=[pool.submit(upload_input,states[jid],bundles[jid][0]) for jid in RETRY_IDS]
            for future in futures:future.result()
    except BaseException:
        failures=[]
        for s in states.values():
            try:
                if not finish(s,{'failure':'launch'})['deleted']:failures.append(s['pod_id'])
            except Exception:failures.append(s['pod_id'])
        if failures:print(json.dumps({'cleanup_unconfirmed':failures}),flush=True)
        raise
    print(json.dumps({'status':'launched','pods':{j:s['pod_id'] for j,s in states.items()},'reserved_usd':6*MAX_RATE+MARGIN}),flush=True)

def status_one(s):
    if receipt_path(s).exists():
        receipt=json.loads(receipt_path(s).read_text())
        if receipt.get('deleted') is True:return {'job_id':s['job_id'],'deleted':True,'worker':receipt.get('worker_status')}
    try:pod=api('GET','pods/'+s['pod_id'])
    except urllib.error.HTTPError as exc:
        if exc.code==404:return {'job_id':s['job_id'],'absent':True,'worker':None}
        raise
    try:
        with urllib.request.urlopen(worker_request(s,'status'),timeout=20) as response:worker=json.load(response)
    except Exception:worker=None
    return {'job_id':s['job_id'],'pod_status':pod.get('desiredStatus'),'worker':worker}

def extract_results(path,destination):
    with tarfile.open(path) as archive:
        members=archive.getmembers()
        if sum(m.size for m in members)>1_000_000_000:raise ValueError('Expanded archive exceeds 1 GB')
        for member in members:
            parts=Path(member.name).parts
            if not parts or parts[0]!='runs' or '..' in parts or not (member.isfile() or member.isdir()):raise ValueError('Unsafe result archive member')
        archive.extractall(destination,filter='data')

def collect_one(s):
    existing=receipt_path(s)
    if existing.exists():
        receipt=json.loads(existing.read_text())
        if receipt.get('deleted') is True and receipt.get('result_archive_sha256'):
            extract_results(LOCAL/s['job_id']/'results.tar.gz',LOCAL/s['job_id'])
            return {'job_id':s['job_id'],'already_collected':True}
    result=status_one(s).get('worker')
    if not result or not result.get('results_ready'):return {'job_id':s['job_id'],'ready':False}
    archive=LOCAL/s['job_id']/'results.tar.gz';total=0;digest=hashlib.sha256()
    with urllib.request.urlopen(worker_request(s,'results'),timeout=60) as response,archive.open('wb') as handle:
        while chunk:=response.read(1024*1024):
            total+=len(chunk)
            if total>600_000_000:raise ValueError('Compressed archive exceeds 600 MB')
            digest.update(chunk);handle.write(chunk)
    if digest.hexdigest()!=result['archive_sha256']:raise ValueError('Transfer checksum mismatch')
    extract_results(archive,LOCAL/s['job_id'])
    receipt=finish(s,{'result_archive_sha256':digest.hexdigest(),'result_archive_bytes':total,'worker_status':result})
    return {'job_id':s['job_id'],'deleted':receipt['deleted'],'estimated_gpu_cost_usd':receipt['estimated_gpu_cost_usd'],'worker_state':result['state']}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['launch','status','collect','cleanup','watchdog']);parser.add_argument('state_path',nargs='?');args=parser.parse_args()
    if args.action=='watchdog':return watchdog(args.state_path)
    if args.action=='launch':return launch()
    states=json.loads((LOCAL/'batch-state.json').read_text());errors=[]
    for s in states.values():
        try:
            if args.action=='status':result=status_one(s)
            elif args.action=='collect':result=collect_one(s)
            else:
                old=json.loads(receipt_path(s).read_text()) if receipt_path(s).exists() else {}
                if old.get('deleted') is True:result={'job_id':s['job_id'],'deleted':True}
                else:result={'job_id':s['job_id'],'deleted':finish(s,{'failure':'manual cleanup'})['deleted']}
            print(json.dumps(result),flush=True)
        except Exception as exc:errors.append({'job_id':s['job_id'],'error_type':type(exc).__name__})
    if errors:raise RuntimeError(str(errors))

if __name__=='__main__':main()
