"""Authenticated Phase 19 orthogonal ROCK2 worker; independent deletion deadline starts at boot."""
import base64
import hashlib
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
STATUS = {'state': 'starting', 'results_ready': False}
READY = threading.Event()
LOCK = threading.Lock()


def validate_gpu_info(info):
    """Allow driver/ECC reservations on a nominal 24-GB RTX 4090."""
    if info.get('available') is not True or info.get('count') != 1:
        raise ValueError('Expected one CUDA device')
    device = info['devices'][0]
    if '4090' not in device['name'] or device['bytes'] < 20*1024**3:
        raise ValueError('Expected RTX 4090 with at least 20 GiB exposed')


def deletion_deadline():
    time.sleep(max(0, float(os.environ['CRYO_DEADLINE_EPOCH'])-time.time()))
    while True:
        try:
            req = urllib.request.Request('https://rest.runpod.io/v1/pods/'+os.environ['RUNPOD_POD_ID'],
                    method='DELETE', headers={'Authorization': 'Bearer '+os.environ['CRYO_RUNPOD_KEY'], 'User-Agent': 'cryo-research/0.1'})
            with urllib.request.urlopen(req, timeout=15):
                return
        except Exception:
            time.sleep(10)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def auth(self):
        return hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer '+os.environ['CRYO_TRANSFER_TOKEN'])

    def reply(self, body):
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.auth():
            self.send_error(401)
            return
        if self.path == '/status':
            progress = ROOT/'runs/summary.json'
            extra = {}
            if progress.exists():
                try:
                    extra['progress'] = json.loads(progress.read_text())
                except ValueError:
                    pass
            self.reply(json.dumps({**STATUS, **extra}).encode())
        elif self.path == '/log':
            logs = sorted((ROOT/'runs').rglob('*.log'), key=lambda p: p.stat().st_mtime)
            chunks = []
            for p in logs[-3:]:
                with p.open('rb') as f:
                    f.seek(max(0, p.stat().st_size-5000))
                    chunks.append(p.name+'\n'+f.read().decode(errors='replace'))
            self.reply('\n'.join(chunks).encode())
        elif self.path == '/results' and STATUS['results_ready']:
            self.reply((ROOT/'results.tar.gz').read_bytes())
        else:
            self.send_error(404)

    def do_POST(self):
        if not self.auth():
            self.send_error(401)
            return
        if self.path != '/inputs':
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 10_000_000:
                raise ValueError()
        except ValueError:
            self.send_error(413)
            return
        self.connection.settimeout(30)
        data = self.rfile.read(length)
        if len(data) != length or hashlib.sha256(data).hexdigest() != os.environ['CRYO_ARCHIVE_SHA256']:
            self.send_error(422)
            return
        with LOCK:
            if not READY.is_set():
                (ROOT/'input.tar.gz').write_bytes(data)
                READY.set()
        self.reply(b'{"accepted":true}')


def unpack(path, expected):
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        if {m.name for m in members} != set(expected) or len(members) != len(expected):
            raise ValueError('Unexpected bundle members')
        if sum(m.size for m in members) > 10_000_000:
            raise ValueError('Bundle too large')
        for member in members:
            if not member.isfile() or Path(member.name).is_absolute() or '..' in Path(member.name).parts:
                raise ValueError('Unsafe input member')
        archive.extractall(ROOT, filter='data')
    for name, digest in expected.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError('Bundle hash mismatch')


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=deletion_deadline, daemon=True).start()
    server = http.server.ThreadingHTTPServer(('0.0.0.0', 8080), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    raw = ROOT/'runs'
    raw.mkdir(exist_ok=True)
    deadline = float(os.environ['CRYO_DEADLINE_EPOCH'])
    try:
        # Runpod documents this injected variable; the host watchdog is independent.
        if not os.environ.get('RUNPOD_POD_ID'):
            raise RuntimeError('Missing provider Pod identity')
        expected = json.loads(base64.b64decode(os.environ['CRYO_FILES_B64']))
        STATUS['state'] = 'awaiting_inputs'
        if not READY.wait(min(600, max(0, deadline-time.time()-300))):
            raise TimeoutError('Input deadline')
        unpack(ROOT/'input.tar.gz', expected)
        child_env = {k: v for k, v in os.environ.items() if not k.startswith('CRYO_') and k != 'RUNPOD_API_KEY'}
        for key, suffix in [('TMPDIR', 'tmp'), ('XDG_CACHE_HOME', 'cache'), ('BOLTZ_CACHE', 'cache/boltz'), ('HF_HOME', 'cache/huggingface')]:
            child_env[key] = str(ROOT/suffix)
            Path(child_env[key]).mkdir(parents=True, exist_ok=True)
        child_env['OMP_NUM_THREADS'] = '4'
        # Print every diagnostic before asserting, preserving the reason for failure.
        diagnostic = '''import json, torch, os
d={"torch":torch.__version__,"cuda_build":torch.version.cuda,"available":torch.cuda.is_available(),"count":torch.cuda.device_count(),"cuda_visible":os.environ.get("CUDA_VISIBLE_DEVICES"),"nvidia_visible":os.environ.get("NVIDIA_VISIBLE_DEVICES")}
d["devices"]=[{"name":torch.cuda.get_device_name(i),"bytes":torch.cuda.get_device_properties(i).total_memory} for i in range(torch.cuda.device_count())]
print(json.dumps(d),flush=True)
if d["available"]: print((torch.ones(8,device="cuda")*2).sum().item(),flush=True)
'''
        with (raw/'gpu-before-setup.log').open('w') as log:
            subprocess.run(['nvidia-smi'], env=child_env, stdout=log, stderr=log, timeout=20, check=False)
            result = subprocess.run(['python', '-c', diagnostic], env=child_env, capture_output=True, text=True, timeout=40, check=False)
            log.write(result.stdout+result.stderr)
            result.check_returncode()
            validate_gpu_info(json.loads(result.stdout.splitlines()[0]))
        STATUS['state'] = 'installing'
        commands = [(['apt-get', 'update', '-qq'], 180),
                    (['apt-get', 'install', '-y', '--no-install-recommends', 'libgomp1', 'libxrender1', 'libxext6', 'libsm6'], 180),
                    (['python', '-m', 'pip', 'install', '--no-cache-dir', '-r', str(ROOT/'requirements-boltz.txt')], 900)]
        with (raw/'setup.log').open('w') as log:
            for cmd, limit in commands:
                remaining = deadline-time.time()-300
                if remaining <= 0:
                    raise TimeoutError('Setup deadline')
                subprocess.run(cmd, env=child_env, stdout=log, stderr=log, check=True, timeout=min(limit, remaining))
        with (raw/'gpu-check.log').open('w') as log:
            result = subprocess.run(['python', '-c', diagnostic],
                           env=child_env, capture_output=True, text=True, check=False, timeout=30)
            log.write(result.stdout+result.stderr)
            result.check_returncode()
            validate_gpu_info(json.loads(result.stdout.splitlines()[0]))
        STATUS['state'] = 'inference'
        cmd = ['python', 'scripts/boltz_orthogonal_inference.py', '--input-dir', 'data/phase19/boltz-inputs',
               '--output', str(raw/'summary.json'), '--cache', str(ROOT/'cache/boltz'), '--deadline-epoch', str(deadline),
               '--collection-reserve-seconds', '300']
        with (raw/'inference.log').open('w') as log:
            subprocess.run(cmd, cwd=ROOT, env=child_env, stdout=log, stderr=log, check=True,
                           timeout=max(1, deadline-time.time()-120))
        STATUS['state'] = 'complete'
    except Exception as exc:
        STATUS.update(state='failed', error_type=type(exc).__name__, error=str(exc)[:1000])
    finally:
        (raw/'status.json').write_text(json.dumps(STATUS, indent=2)+'\n')
        # Models and caches are deliberately outside runs and never returned.
        if sum(p.stat().st_size for p in raw.rglob('*') if p.is_file()) <= 1_000_000_000:
            with tarfile.open(ROOT/'results.tar.gz', 'w:gz') as archive:
                archive.add(raw, arcname='runs')
            archive_path = ROOT/'results.tar.gz'
            STATUS['results_ready'] = archive_path.stat().st_size <= 500_000_000
            STATUS['archive_sha256'] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        else:
            STATUS.update(state='failed', error_type='OutputSizeLimit')
    while True:
        time.sleep(15)


if __name__ == '__main__':
    main()
