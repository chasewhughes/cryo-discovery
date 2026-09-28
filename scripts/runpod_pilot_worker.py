"""One-purpose cloud worker: run the reviewed pilot and serve authenticated results.

Only the launcher supplies the input files. The API credential is used solely
to delete this worker's own Pod at the deadline; it is never written to disk.
"""
import base64
import hmac
import http.server
import json
import os
from pathlib import Path
import subprocess
import tarfile
import threading
import time
import urllib.request

ROOT = Path('/workspace/cryo')
STATUS = {'state': 'starting'}


def deadline_delete():
    delay = max(0, float(os.environ['CRYO_DEADLINE_EPOCH'])-time.time())
    time.sleep(delay)
    for attempt in range(20):
        try:
            pod_id = os.environ['RUNPOD_POD_ID']
            req = urllib.request.Request('https://rest.runpod.io/v1/pods/'+pod_id,
                    method='DELETE', headers={'Authorization': 'Bearer '+os.environ['CRYO_RUNPOD_KEY']})
            with urllib.request.urlopen(req, timeout=20):
                return
        except Exception:
            time.sleep(15)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        expected = 'Bearer '+os.environ['CRYO_TRANSFER_TOKEN']
        if not hmac.compare_digest(self.headers.get('Authorization',''), expected):
            self.send_error(401); return
        if self.path == '/status':
            body = json.dumps(STATUS).encode()
            self.send_response(200); self.send_header('Content-Length',str(len(body)))
            self.end_headers(); self.wfile.write(body)
        elif self.path == '/results' and (ROOT/'results.tar.gz').is_file():
            path = ROOT/'results.tar.gz'
            self.send_response(200); self.send_header('Content-Length',str(path.stat().st_size))
            self.end_headers()
            with path.open('rb') as handle:
                while chunk := handle.read(1024*1024): self.wfile.write(chunk)
        else:
            self.send_error(404)


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    threading.Thread(target=deadline_delete,daemon=True).start()
    server = http.server.ThreadingHTTPServer(('0.0.0.0',8080), Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    inputs = json.loads(base64.b64decode(os.environ['CRYO_INPUTS_B64']))
    allowed = {'scripts/run_hydration_pilot.py', 'simulation/tip4p-ice.xml', 'requirements-md-cuda.txt'}
    if set(inputs) != allowed: raise ValueError('Unexpected input bundle')
    for name, content in inputs.items():
        path = ROOT/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content)
    os.environ['TMPDIR'] = str(ROOT/'tmp'); Path(os.environ['TMPDIR']).mkdir(exist_ok=True)
    raw = ROOT/'runs'; raw.mkdir(exist_ok=True)
    try:
        STATUS.update(state='installing')
        with (raw/'setup.log').open('w') as log:
            subprocess.run(['apt-get','update','-qq'],stdout=log,stderr=log,check=True,timeout=180)
            subprocess.run(['apt-get','install','-y','--no-install-recommends','libgomp1','ocl-icd-libopencl1'],stdout=log,stderr=log,check=True,timeout=180)
            subprocess.run(['python','-m','pip','install','--no-cache-dir','-r',str(ROOT/'requirements-md-cuda.txt')],stdout=log,stderr=log,check=True,timeout=420)
        with (raw/'gpu.txt').open('w') as log:
            subprocess.run(['nvidia-smi'],stdout=log,stderr=log,timeout=20,check=True)
        with (raw/'installation-check.log').open('w') as log:
            subprocess.run(['python','-m','openmm.testInstallation'],stdout=log,stderr=log,timeout=120,check=True)
        if 'CUDA - Successfully computed forces' not in (raw/'installation-check.log').read_text():
            raise RuntimeError('CUDA force check failed despite installation command exit status')
        finished = []
        for seed in [20260906,20260907,20260908]:
            for compound in ['gly','phe']:
                name = f'{compound}-{seed}'
                STATUS.update(state='simulating',current=name,completed=finished.copy())
                with (raw/(name+'.log')).open('w') as log:
                    subprocess.run(['python','scripts/run_hydration_pilot.py','--compound',compound,
                        '--seed',str(seed),'--platform','CUDA','--equilibration-ps','100',
                        '--production-ps','1000','--frames','100','--max-wall-seconds','600',
                        '--output',str(raw/name)],cwd=ROOT,stdout=log,stderr=log,check=True,timeout=650)
                finished.append(name)
        STATUS.update(state='complete',completed=finished)
    except Exception as exc:
        STATUS.update(state='failed',error_type=type(exc).__name__)
    finally:
        (raw/'status.json').write_text(json.dumps(STATUS,indent=2)+'\n')
        with tarfile.open(ROOT/'results.tar.gz','w:gz') as archive:
            archive.add(raw,arcname='runs')
        STATUS['results_ready'] = True
    # Keep results reachable until the local client retrieves and deletes the Pod.
    while True: time.sleep(30)


if __name__ == '__main__': main()
