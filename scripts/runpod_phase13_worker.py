"""Authenticated, time-bounded single-branch Phase 13 GPU worker."""
import base64, hashlib, hmac, http.server, json, os, subprocess, tarfile, threading, time
from pathlib import Path
import urllib.request

ROOT=Path('/workspace/cryo'); STATUS={'state':'starting','results_ready':False}
INPUT_READY=threading.Event(); INPUT_LOCK=threading.Lock()
REQUIRED={'system.xml','integrator.xml','final-state.xml','topology-final-box.pdb','result.json'}
CODE={'scripts/run_matched_hydration.py','scripts/run_hydration_extension.py','scripts/hydration_descriptor.py','requirements-md-cuda.txt'}

def delete_at_deadline():
    time.sleep(max(0,float(os.environ['CRYO_DEADLINE_EPOCH'])-time.time()))
    for _ in range(20):
        try:
            req=urllib.request.Request('https://rest.runpod.io/v1/pods/'+os.environ['RUNPOD_POD_ID'],method='DELETE',headers={'Authorization':'Bearer '+os.environ['CRYO_RUNPOD_KEY'],'User-Agent':'cryo-research/0.1'})
            with urllib.request.urlopen(req,timeout=20): return
        except Exception: time.sleep(15)

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*_): pass
    def authenticated(self):
        return hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+os.environ['CRYO_TRANSFER_TOKEN'])
    def reply(self,body):
        self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        if not self.authenticated(): self.send_error(401);return
        if self.path=='/status': self.reply(json.dumps(STATUS).encode());return
        if self.path=='/results' and STATUS['results_ready']:
            path=ROOT/'results.tar.gz';self.send_response(200);self.send_header('Content-Length',str(path.stat().st_size));self.end_headers()
            with path.open('rb') as f:
                while chunk:=f.read(1024*1024): self.wfile.write(chunk)
            return
        self.send_error(404)
    def do_POST(self):
        if not self.authenticated(): self.send_error(401);return
        if self.path!='/inputs':self.send_error(404);return
        try: length=int(self.headers.get('Content-Length','0'))
        except ValueError:self.send_error(400);return
        if not 0<length<=10_000_000:self.send_error(413);return
        self.connection.settimeout(30)
        data=self.rfile.read(length)
        if len(data)!=length:self.send_error(400);return
        digest=hashlib.sha256(data).hexdigest()
        if digest!=os.environ['CRYO_ARCHIVE_SHA256']:self.send_error(422);return
        with INPUT_LOCK:
            if not INPUT_READY.is_set():
                path=ROOT/'input.tar.gz';path.write_bytes(data);INPUT_READY.set()
        self.reply(b'{"accepted":true}')

def unpack_parent(archive_path,parent,expected):
    with tarfile.open(archive_path) as archive:
        members=archive.getmembers()
        if len(members)!=5 or {m.name for m in members}!=REQUIRED or any(not m.isfile() for m in members) or sum(m.size for m in members)>10_000_000:
            raise ValueError('Invalid parent archive')
        archive.extractall(parent,filter='data')
    actual={name:hashlib.sha256((parent/name).read_bytes()).hexdigest() for name in REQUIRED}
    if actual!=expected:raise ValueError('Parent hash mismatch')

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    threading.Thread(target=delete_at_deadline,daemon=True).start()
    server=http.server.ThreadingHTTPServer(('0.0.0.0',8080),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    raw=ROOT/'runs';raw.mkdir(exist_ok=True)
    os.environ['TMPDIR']=str(ROOT/'tmp');Path(os.environ['TMPDIR']).mkdir(exist_ok=True)
    try:
        job=json.loads(base64.b64decode(os.environ['CRYO_JOB_B64']))
        code=json.loads(base64.b64decode(os.environ['CRYO_CODE_B64']))
        if set(code)!=CODE:raise ValueError('Unexpected code bundle')
        for name,content in code.items():
            path=ROOT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
        STATUS['state']='installing'
        with (raw/'setup.log').open('w') as log:
            for cmd,timeout in [(['apt-get','update','-qq'],180),(['apt-get','install','-y','--no-install-recommends','libgomp1','ocl-icd-libopencl1'],180),(['python','-m','pip','install','--no-cache-dir','-r',str(ROOT/'requirements-md-cuda.txt')],420)]:
                subprocess.run(cmd,stdout=log,stderr=log,check=True,timeout=timeout)
        with (raw/'gpu.txt').open('w') as log:subprocess.run(['nvidia-smi'],stdout=log,stderr=log,check=True,timeout=20)
        with (raw/'installation-check.log').open('w') as log:subprocess.run(['python','-m','openmm.testInstallation'],stdout=log,stderr=log,check=True,timeout=120)
        if 'CUDA - Successfully computed forces' not in (raw/'installation-check.log').read_text():raise RuntimeError('CUDA force check failed')
        STATUS['state']='awaiting_input'
        if not INPUT_READY.wait(300):raise TimeoutError('Input upload timed out')
        parent=ROOT/'parent';parent.mkdir(exist_ok=True)
        unpack_parent(ROOT/'input.tar.gz',parent,job['parent_sha256'])
        STATUS.update(state='simulating',current=job['id'])
        cmd=['python','scripts/run_matched_hydration.py','--input',str(parent),'--seed',str(job['seed']),'--platform','CUDA','--equilibration-ps','1000','--production-ps','10000','--frames','1000','--max-wall-seconds','1800','--output',str(raw/job['id'])]
        with (raw/(job['id']+'.log')).open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=log,check=True,timeout=1900)
        STATUS['state']='complete'
    except Exception as exc:STATUS.update(state='failed',error_type=type(exc).__name__)
    finally:
        (raw/'status.json').write_text(json.dumps(STATUS,indent=2)+'\n')
        if sum(p.stat().st_size for p in raw.rglob('*') if p.is_file())<=1_000_000_000:
            with tarfile.open(ROOT/'results.tar.gz','w:gz') as archive:archive.add(raw,arcname='runs')
            STATUS['results_ready']=(ROOT/'results.tar.gz').stat().st_size<=600_000_000
            if STATUS['results_ready']:STATUS['archive_sha256']=hashlib.sha256((ROOT/'results.tar.gz').read_bytes()).hexdigest()
        else:STATUS.update(state='failed',error_type='ArchiveLimitExceeded')
    while True:time.sleep(30)

if __name__=='__main__':main()
