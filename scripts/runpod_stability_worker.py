"""Bounded Phase 11 worker; inputs are supplied by the launcher."""
import base64, hmac, http.server, json, os, subprocess, tarfile, threading, time
from pathlib import Path
import urllib.request

ROOT=Path('/workspace/cryo'); STATUS={'state':'starting'}

def deadline_delete():
    time.sleep(max(0,float(os.environ['CRYO_DEADLINE_EPOCH'])-time.time()))
    for _ in range(20):
        try:
            req=urllib.request.Request('https://rest.runpod.io/v1/pods/'+os.environ['RUNPOD_POD_ID'],method='DELETE',headers={'Authorization':'Bearer '+os.environ['CRYO_RUNPOD_KEY'],'User-Agent':'cryo-research/0.1'})
            with urllib.request.urlopen(req,timeout=20): return
        except Exception: time.sleep(15)

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+os.environ['CRYO_TRANSFER_TOKEN']): self.send_error(401); return
        if self.path=='/status':
            body=json.dumps(STATUS).encode(); self.send_response(200); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        elif self.path=='/results' and (ROOT/'results.tar.gz').is_file():
            path=ROOT/'results.tar.gz'; self.send_response(200); self.send_header('Content-Length',str(path.stat().st_size)); self.end_headers()
            with path.open('rb') as f:
                while chunk:=f.read(1024*1024): self.wfile.write(chunk)
        else: self.send_error(404)

def main():
    ROOT.mkdir(parents=True,exist_ok=True); threading.Thread(target=deadline_delete,daemon=True).start()
    server=http.server.ThreadingHTTPServer(('0.0.0.0',8080),Handler); threading.Thread(target=server.serve_forever,daemon=True).start()
    inputs=json.loads(base64.b64decode(os.environ['CRYO_INPUTS_B64']))
    allowed={'scripts/run_hydration_stability.py','scripts/run_hydration_pilot.py','scripts/hydration_descriptor.py','simulation/tip4p-ice.xml','requirements-md-cuda.txt','data/phase11/stability-plan.json'}
    if set(inputs)!=allowed: raise ValueError('unexpected input bundle')
    for name,content in inputs.items(): path=ROOT/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content)
    raw=ROOT/'runs'; raw.mkdir(exist_ok=True); os.environ['TMPDIR']=str(ROOT/'tmp'); Path(os.environ['TMPDIR']).mkdir(exist_ok=True)
    try:
        STATUS['state']='installing'
        with (raw/'setup.log').open('w') as log:
            subprocess.run(['apt-get','update','-qq'],stdout=log,stderr=log,check=True,timeout=180)
            subprocess.run(['apt-get','install','-y','--no-install-recommends','libgomp1','ocl-icd-libopencl1'],stdout=log,stderr=log,check=True,timeout=180)
            subprocess.run(['python','-m','pip','install','--no-cache-dir','-r',str(ROOT/'requirements-md-cuda.txt')],stdout=log,stderr=log,check=True,timeout=420)
        with (raw/'gpu.txt').open('w') as log: subprocess.run(['nvidia-smi'],stdout=log,stderr=log,check=True,timeout=20)
        with (raw/'installation-check.log').open('w') as log: subprocess.run(['python','-m','openmm.testInstallation'],stdout=log,stderr=log,check=True,timeout=120)
        if 'CUDA - Successfully computed forces' not in (raw/'installation-check.log').read_text(): raise RuntimeError('CUDA force check failed')
        jobs=json.loads((ROOT/'data/phase11/stability-plan.json').read_text())['jobs']; finished=[]
        for job in jobs:
            compound,seed,ensemble=job['compound'],job['seed'],job['ensemble']; name=f'{compound}-{ensemble}-{seed}'
            STATUS.update(state='simulating',current=name,completed=finished.copy())
            with (raw/(name+'.log')).open('w') as log:
                subprocess.run(['python','scripts/run_hydration_stability.py','--compound',compound,'--seed',str(seed),'--ensemble',ensemble,'--platform','CUDA','--equilibration-ps',str(job['equilibration_ps']),'--production-ps',str(job['production_ps']),'--frames',str(job['frames']),'--max-wall-seconds','1450','--output',str(raw/name)],cwd=ROOT,stdout=log,stderr=log,check=True,timeout=1500)
            finished.append(name)
        STATUS.update(state='complete',completed=finished)
    except Exception as exc: STATUS.update(state='failed',error_type=type(exc).__name__)
    finally:
        (raw/'status.json').write_text(json.dumps(STATUS,indent=2)+'\n')
        members=list(raw.rglob('*')); expanded=sum(p.stat().st_size for p in members if p.is_file())
        if expanded>1_000_000_000:
            STATUS.update(state='failed',error_type='ArchiveLimitExceeded',results_ready=False)
        else:
            with tarfile.open(ROOT/'results.tar.gz','w:gz') as archive: archive.add(raw,arcname='runs')
            STATUS['results_ready']=(ROOT/'results.tar.gz').stat().st_size<=600_000_000
            if not STATUS['results_ready']: STATUS.update(state='failed',error_type='ArchiveLimitExceeded')
    while True: time.sleep(30)

if __name__=='__main__': main()
