"""Bounded Phase 20 validation ROCK2 launcher with persistent intent and two watchdogs."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import fcntl
import io
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request

try:
    from .runpod_phase13 import key, write_json
except ImportError:
    from runpod_phase13 import key, write_json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'data/phase20'
LOCAL = ROOT/'data/raw/phase20'
MAX_RATE = .80
LIFETIME = 10800
MARGIN = .30
GPU = 'NVIDIA GeForce RTX 4090'
IMAGE = 'pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime'
PLAN = OUT/'validation-plan.json'



def api(method, endpoint, payload=None):
    req = urllib.request.Request('https://rest.runpod.io/v1/'+endpoint,
            data=None if payload is None else json.dumps(payload).encode(), method=method,
            headers={'Authorization': 'Bearer '+key(), 'Content-Type': 'application/json', 'User-Agent': 'cryo-research/0.1'})
    try:
        with urllib.request.urlopen(req, timeout=40) as response:
            body = response.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        if method == 'POST' and endpoint == 'pods':
            body = exc.read(10000).decode(errors='replace')
            for secret in [key(), *((payload or {}).get('env', {}).values())]:
                if isinstance(secret, str) and secret:
                    body = body.replace(secret, '[redacted]')
            write_json(LOCAL/'provider-errors'/((payload or {})['name']+'.json'),
                       {'http_status': exc.code, 'response': body[:2000], 'recorded_epoch': time.time()})
        raise


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def receipt_path(state):
    return OUT/f"runpod-attempt{state['attempt']}-receipt.json"


def reserve_batch(attempt):
    """Record the reservation before POST; launch.lock serializes updates."""
    path = OUT/'panel-batch-state.json'
    current = load(path) if path.exists() else {'phase': 20, 'attempts': {}}
    if any(load(p).get('worker_state') == 'complete' for p in OUT.glob('runpod-attempt*-receipt.json')):
        raise ValueError('This frozen panel already completed; a new experiment requires a new plan')
    active = current.get('active_attempt')
    if active is not None:
        active_receipt = receipt_path({'attempt': active})
        resolution_path = LOCAL/f'attempt{active}'/'intent-reconciliation.json'
        resolution = load(resolution_path) if resolution_path.exists() else {}
        resolved_empty = resolution.get('definitive_rejection') or resolution.get('no_matching_pod_at_deadline')
        if not resolved_empty and (not active_receipt.exists() or not load(active_receipt).get('deleted')):
            raise ValueError('An active Phase 20 reservation already exists')
    prior_receipt = receipt_path({'attempt': attempt})
    if prior_receipt.exists() and load(prior_receipt).get('worker_state') == 'complete':
        raise ValueError('A completed Phase 20 attempt cannot be rerun')
    current['active_attempt'] = attempt
    current.setdefault('attempts', {})[str(attempt)] = {'state': 'reserved', 'reserved_epoch': time.time()}
    write_json(path, current)


def release_batch(state, outcome):
    path = OUT/'panel-batch-state.json'
    if not path.exists():
        return
    current = load(path)
    if current.get('active_attempt') == state.get('attempt') and (outcome.get('deleted') is True or outcome.get('definitive_no_allocation') is True):
        current['active_attempt'] = None
    current.setdefault('attempts', {}).setdefault(str(state.get('attempt')), {}).update(outcome)
    write_json(path, current)


def validate_budget(rec, quote):
    stamp = datetime.fromisoformat(rec['verified_at']).timestamp()
    if not 0 <= time.time()-stamp < 3600 or not rec['all_prior_research_pods_absent']:
        raise ValueError('Fresh complete reconciliation required')
    prior = float(rec['prior_gpu_reserve_usd'])
    if not math.isfinite(prior) or prior < 0 or prior+MAX_RATE*LIFETIME/3600+MARGIN > 10:
        raise ValueError('Cumulative budget exceeded')
    stamp = datetime.fromisoformat(quote['checked_at']).timestamp()
    selected = [q for q in quote['quotes'] if q['id'] == GPU]
    if not 0 <= time.time()-stamp < 3600 or len(selected) != 1:
        raise ValueError('Fresh matching quote required')
    rate = float(selected[0]['securePrice'])
    if not math.isfinite(rate) or not 0 < rate <= MAX_RATE:
        raise ValueError('Quote exceeds maximum rate')
    return prior


def pending_reserve():
    total = 0.
    # Include unresolved intents from every phase in the cumulative guard.
    for p in (ROOT/'data'/'raw').glob('phase*/attempt*/intent.json'):
        intent = load(p)
        phase = p.parents[1].name
        receipt_files = list((ROOT/'data'/phase).glob('runpod*-receipt.json'))
        matched = []
        for receipt_file in receipt_files:
            try:
                receipt = load(receipt_file)
            except (OSError, ValueError):
                continue
            if receipt.get('name') == intent.get('name') and receipt.get('deleted') is True:
                matched.append(receipt)
        if matched:
            continue
        reconciliation = load(p.with_name('intent-reconciliation.json')) if p.with_name('intent-reconciliation.json').exists() else {}
        if reconciliation.get('definitive_rejection') or reconciliation.get('no_matching_pod_at_deadline'):
            continue
        reserved = intent.get('reserved_usd', MAX_RATE*LIFETIME/3600+MARGIN)
        try:
            reserved = float(reserved)
        except (TypeError, ValueError):
            reserved = float('nan')
        if not math.isfinite(reserved) or reserved <= 0:
            reserved = MAX_RATE*LIFETIME/3600+MARGIN
        total += reserved
    return total


def plan_path(attempt):
    return PLAN


def verify_plan(attempt=1):
    plan = load(plan_path(attempt))
    if plan['cloud'] != {'gpu': GPU, 'image': IMAGE, 'max_rate_usd_hour': MAX_RATE, 'max_lifetime_seconds': LIFETIME, 'margin_usd': MARGIN}:
        raise ValueError('Cloud settings differ from frozen plan')
    for path, digest in {**plan['source_sha256'], **plan.get('provenance_sha256', {})}.items():
        if sha(ROOT/path) != digest:
            raise ValueError('Changed frozen source '+path)
    bundle_files = plan.get('bundle_files', [])
    if set(plan['source_sha256']) != set(bundle_files + ['scripts/runpod_boltz_validation.py', 'scripts/runpod_boltz_validation_worker.py']):
        raise ValueError('Incomplete frozen source set')
    return plan


def bundle():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as archive:
        for name in load(PLAN)['bundle_files']:
            archive.add(ROOT/name, arcname=name)
    data = buf.getvalue()
    if len(data) > 10_000_000:
        raise ValueError('Input bundle too large')
    return data


def remove(state):
    try:
        pod = api('GET', 'pods/'+state['pod_id'])
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return True
        raise
    if pod.get('name') != state['name']:
        raise ValueError('Refusing to remove mismatched Pod')
    try:
        api('DELETE', 'pods/'+state['pod_id'])
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    try:
        api('GET', 'pods/'+state['pod_id'])
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return True
        raise
    return False


def finish(state, extra=None):
    directory = LOCAL/f"attempt{state['attempt']}"
    with (directory/'receipt.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return finish_locked(state, extra)


def finish_locked(state, extra=None):
    old = load(receipt_path(state)) if receipt_path(state).exists() else {}
    if old.get('deleted') is True:
        receipt = {**old, **(extra or {})}
        write_json(receipt_path(state), receipt)
        return receipt
    deleted = remove(state)
    ended = time.time()
    receipt = {**state, **old, **(extra or {}), 'deleted': deleted,
               'ended_epoch': old.get('ended_epoch', ended),
               'estimated_gpu_cost_usd': old.get('estimated_gpu_cost_usd', (ended-state['created_epoch'])/3600*state['cost_per_hour'])}
    write_json(receipt_path(state), receipt)
    release_batch(state, {'state': 'finished', 'finished_epoch': ended, 'deleted': deleted})
    return receipt


def watchdog(path):
    intent = load(path)
    while time.time() < intent['deadline_epoch']:
        time.sleep(min(15, intent['deadline_epoch']-time.time()))
    state_path = path.with_name('state.json')
    for _ in range(30):
        try:
            if state_path.exists():
                state = load(state_path)
                if finish(state, {'deadline_watchdog_checked': True})['deleted']:
                    return
            else:
                # An ambiguous POST is never retried; resolve by unique intent name.
                found = [p for p in api('GET', 'pods') if p.get('name') == intent['name']]
                if len(found) == 1:
                    state = {**intent, 'pod_id': found[0]['id'], 'cost_per_hour': MAX_RATE}
                    write_json(state_path, state)
                    if finish(state, {'failure': 'ambiguous launch deadline'})['deleted']:
                        return
                elif not found:
                    write_json(path.with_name('intent-reconciliation.json'), {'no_matching_pod_at_deadline': True, 'checked_epoch': time.time()})
                    return
        except Exception:
            pass
        time.sleep(10)
    write_json(path.with_name('cleanup-unconfirmed.json'), {'name': intent['name'], 'deleted': False})


def request(state, endpoint, data=None):
    token = (LOCAL/f"attempt{state['attempt']}"/'transfer-token').read_text()
    return urllib.request.Request(f"https://{state['pod_id']}-8080.proxy.runpod.net/{endpoint}",
                                  data=data, headers={'Authorization': 'Bearer '+token, 'User-Agent': 'cryo-research/0.1'})


def launch(attempt):
    plan = verify_plan(attempt)
    prior = validate_budget(load(OUT/'billing-reconciliation.json'), load(OUT/'gpu-quote.json'))
    pending = pending_reserve()
    if prior+pending+MAX_RATE*LIFETIME/3600+MARGIN > 10:
        raise ValueError('Pending launch reservations exhaust cumulative budget')
    # Count new receipts since reconciliation, and reject any unresolved attempt.
    rec = load(OUT/'billing-reconciliation.json')
    rec_ids = {r['pod_id'] for r in rec['billing_queries']}
    for p in (ROOT/'data').glob('phase*/runpod*-receipt.json'):
        r = load(p)
        if not r.get('deleted') or (r.get('pod_id') or r.get('id')) not in rec_ids:
            raise ValueError('Reconcile every previous pilot attempt first')
    for p in LOCAL.glob('attempt*/intent.json'):
        a = load(p)['attempt']
        if not (OUT/f'runpod-attempt{a}-receipt.json').exists() and not p.with_name('intent-reconciliation.json').exists():
            raise ValueError('Unresolved prior launch intent')
    pods = api('GET', 'pods')
    if any(p.get('name', '').startswith('cryo-') for p in pods):
        raise ValueError('An untracked research Pod exists')
    directory = LOCAL/f'attempt{attempt}'
    directory.mkdir(parents=True, exist_ok=False)
    reserve_batch(attempt)
    packed = bundle()
    (directory/'input.tar.gz').write_bytes(packed)
    token = secrets.token_urlsafe(32)
    fd = os.open(directory/'transfer-token', os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(token)
    created = time.time()
    state = None
    intent = {'attempt': attempt, 'name': f'cryo-phase20-validation-{attempt}-'+secrets.token_hex(4),
              'created_epoch': created, 'deadline_epoch': created+LIFETIME,
              'reserved_usd': MAX_RATE*LIFETIME/3600+MARGIN, 'prior_reserve_usd': prior,
              'other_pending_reserve_usd': pending,
              'plan_sha256': sha(plan_path(attempt))}
    write_json(directory/'intent.json', intent)
    with (directory/'watchdog.log').open('w') as log:
        guard = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'watchdog', '--intent', str(directory/'intent.json')], stdout=log, stderr=log, start_new_session=True)
    intent['watchdog_pid'] = guard.pid
    write_json(directory/'intent.json', intent)
    boot = "import os,base64;exec(compile(base64.b64decode(os.environ['CRYO_WORKER_B64']),'<worker>','exec'))"
    payload = {'name': intent['name'], 'cloudType': 'SECURE', 'computeType': 'GPU', 'gpuTypeIds': [GPU],
               'gpuCount': 1, 'gpuTypePriority': 'custom', 'allowedCudaVersions': ['12.8', '12.9', '13.0'],
               'imageName': IMAGE, 'containerDiskInGb': 40, 'volumeInGb': 0,
               'minRAMPerGPU': 32, 'minVCPUPerGPU': 4, 'interruptible': False, 'ports': ['8080/http'],
               'dockerEntrypoint': ['python', '-u', '-c'], 'dockerStartCmd': [boot],
               'env': {'CRYO_WORKER_B64': base64.b64encode((ROOT/'scripts/runpod_boltz_validation_worker.py').read_bytes()).decode(),
                       'CRYO_FILES_B64': base64.b64encode(json.dumps({f: sha(ROOT/f) for f in plan['bundle_files']}).encode()).decode(),
                       'CRYO_TRANSFER_TOKEN': token, 'CRYO_RUNPOD_KEY': key(),
                       'CRYO_DEADLINE_EPOCH': str(intent['deadline_epoch']),
                       'CRYO_ARCHIVE_SHA256': hashlib.sha256(packed).hexdigest()}}
    try:
        validate_budget(load(OUT/'billing-reconciliation.json'), load(OUT/'gpu-quote.json'))
        if any(p.get('name', '').startswith('cryo-') for p in api('GET', 'pods')):
            raise ValueError('A research Pod appeared before launch')
        try:
            pod = api('POST', 'pods', payload)
        except Exception:
            found = []
            for _ in range(3):
                found = [p for p in api('GET', 'pods') if p.get('name') == intent['name']]
                if found:
                    break
                time.sleep(3)
            if len(found) != 1:
                error_path = LOCAL/'provider-errors'/(intent['name']+'.json')
                if not found and error_path.exists() and 400 <= load(error_path)['http_status'] < 500:
                    write_json(directory/'intent-reconciliation.json', {'definitive_rejection': True,
                               'http_status': load(error_path)['http_status'], 'no_matching_pods_now': True,
                               'checked_epoch': time.time()})
                raise RuntimeError('Ambiguous/rejected launch; intent watchdog retained') from None
            pod = found[0]
        rate = pod.get('costPerHr')
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            rate = float('nan')
        valid = math.isfinite(rate) and 0 < rate <= MAX_RATE
        state = {**intent, 'pod_id': pod['id'], 'cost_per_hour': rate if math.isfinite(rate) and rate > 0 else MAX_RATE,
                 'image': IMAGE, 'gpu': GPU, 'worker_sha256': sha(ROOT/'scripts/runpod_boltz_validation_worker.py')}
        write_json(directory/'state.json', state)
        if not valid:
            raise ValueError('Provider rate exceeds frozen cap')
        write_json(OUT/f'attempt{attempt}-reservation.json', state)
    except BaseException:
        if state:
            finish(state, {'failure': 'launch'})
        raise
    print(json.dumps({'pod_id': state['pod_id'], 'hourly_rate_usd': rate, 'reserved_usd': intent['reserved_usd'], 'deadline_epoch': intent['deadline_epoch']}))


def upload(state):
    packed = (LOCAL/f"attempt{state['attempt']}"/'input.tar.gz').read_bytes()
    with urllib.request.urlopen(request(state, 'inputs', packed), timeout=30) as r:
        return json.load(r)


def collect(state):
    with urllib.request.urlopen(request(state, 'status'), timeout=20) as r:
        status = json.load(r)
    if not status.get('results_ready'):
        return {'ready': False, 'worker_state': status.get('state')}
    directory = LOCAL/f"attempt{state['attempt']}"
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(request(state, 'results'), timeout=60) as response, (directory/'results.tar.gz').open('wb') as f:
        while chunk := response.read(1024*1024):
            total += len(chunk)
            if total > 500_000_000:
                raise ValueError('Output archive too large')
            digest.update(chunk)
            f.write(chunk)
    if digest.hexdigest() != status['archive_sha256']:
        raise ValueError('Output archive checksum mismatch')
    with tarfile.open(directory/'results.tar.gz') as archive:
        members = archive.getmembers()
        if sum(m.size for m in members) > 1_000_000_000:
            raise ValueError('Expanded archive too large')
        for member in members:
            parts = Path(member.name).parts
            if not parts or parts[0] != 'runs' or '..' in parts or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe output archive')
        archive.extractall(directory, filter='data')
    receipt = finish(state, {'worker_state': status['state'], 'result_archive_sha256': digest.hexdigest(), 'result_archive_bytes': total})
    return {'deleted': receipt['deleted'], 'estimated_gpu_cost_usd': receipt['estimated_gpu_cost_usd'], 'worker_state': status['state']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['launch', 'upload', 'status', 'log', 'collect', 'cleanup', 'watchdog'])
    parser.add_argument('--attempt', type=int, default=1)
    parser.add_argument('--intent', type=Path)
    args = parser.parse_args()
    if args.action == 'watchdog':
        watchdog(args.intent)
    elif args.action == 'launch':
        if not 1 <= args.attempt <= 3:
            parser.error('Only bounded explicit attempts 1-3 permitted')
        LOCAL.mkdir(parents=True, exist_ok=True)
        with (LOCAL/'launch.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
            launch(args.attempt)
    else:
        state = load(LOCAL/f'attempt{args.attempt}'/'state.json')
        if args.action in ['status', 'log']:
            with urllib.request.urlopen(request(state, args.action), timeout=20) as r:
                print(r.read().decode())
        elif args.action == 'upload':
            print(upload(state))
        elif args.action == 'collect':
            print(collect(state))
        elif args.action == 'cleanup':
            r = finish(state, {'manual_cleanup': True})
            print({'deleted': r['deleted'], 'estimated_gpu_cost_usd': r['estimated_gpu_cost_usd']})
