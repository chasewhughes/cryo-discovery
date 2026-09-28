"""Read-only Phase 17 reconciliation and post-cleanup cost report."""
import argparse, hashlib, json, math, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reconcile_boltz_compute as billing_api
import runpod_boltz_panel as launcher

ROOT = billing_api.ROOT
OUT = ROOT / 'data/phase17'


def snapshot():
    receipts = billing_api.load_receipts()
    pods = billing_api.api('GET', 'pods')
    untracked = [{'id': p.get('id'), 'name': p.get('name'), 'costPerHr': p.get('costPerHr')}
                 for p in pods if str(p.get('name', '')).startswith('cryo-') and str(p.get('id')) not in receipts]
    if set(receipts) & {str(p.get('id')) for p in pods}:
        raise ValueError('prior research Pod remains present')
    with ThreadPoolExecutor(max_workers=3) as pool:
        queried = list(pool.map(billing_api.bill, receipts.items()))
    return receipts, pods, untracked, queried, sum(x['conservative_reserve_usd'] for x in queried), sum(x['estimated_gpu_usd'] for x in queried)


def attempt3_resolution():
    intent = ROOT / 'data/raw/phase16/attempt3/intent.json'
    resolution = ROOT / 'data/raw/phase16/attempt3/intent-reconciliation.json'
    raw, checked = intent.read_bytes(), json.loads(resolution.read_text())
    data = json.loads(raw)
    return {'attempt': 3, 'intent_path': str(intent.relative_to(ROOT)),
            'intent_sha256': hashlib.sha256(raw).hexdigest(),
            'provider_check_path': str(resolution.relative_to(ROOT)),
            'provider_check_sha256': hashlib.sha256(resolution.read_bytes()).hexdigest(),
            'provider_check': checked, 'deadline_epoch': data['deadline_epoch'],
            'resolved_as_no_matching_pod': checked.get('no_matching_pod_at_deadline') is True,
            'reserved_potential_usd': data['reserved_usd'],
            'resolution_recorded_at': datetime.now(timezone.utc).isoformat()}


def write_prelaunch(receipts, pods, untracked, queried, reserve, estimate):
    now = datetime.now(timezone.utc).isoformat()
    billing_api.write_json(OUT / 'billing-reconciliation.json', {
        'verified_at': now, 'all_prior_research_pods_absent': not untracked,
        'untracked_cryo_pods': untracked, 'prior_gpu_reserve_usd': reserve,
        'estimated_prior_gpu_usd': estimate, 'billing_queries': queried,
        'unrelated_pods_untouched': len(pods), 'receipt_count': len(receipts),
        'note': 'Phase 17 read-only snapshot; no allocation or deletion performed.'})
    ids = ['NVIDIA GeForce RTX 4090', 'NVIDIA RTX A5000', 'NVIDIA RTX A6000']
    billing_api.write_json(OUT / 'gpu-quote.json', {'checked_at': now, 'requested_gpu_ids': ids,
        'quotes': [billing_api.quote_one(x) for x in ids], 'selection_note': 'Read-only Phase 17 quote snapshot.'})
    billing_api.write_json(OUT / 'prior-intent-resolution.json', attempt3_resolution())


def final_report(receipts, queried, reserve, estimate, untracked, pending, pods=None):
    if untracked:
        raise ValueError('Cannot finalize while untracked research Pods remain')
    if not math.isfinite(pending) or pending < 0 or pending > 0:
        raise ValueError('Cannot finalize while an unresolved launch intent remains')
    total_reserve = reserve + pending
    if not math.isfinite(total_reserve) or total_reserve > 10.0:
        raise ValueError('Cumulative budget cap exceeded')
    phase_ids = set()
    for path in OUT.glob('runpod*-receipt.json'):
        data = json.loads(path.read_text())
        if data.get('deleted') is not True:
            raise ValueError('Cannot finalize before every Phase 17 receipt confirms deletion')
        phase_ids.add(str(data['pod_id']))
    phase_estimate = sum(x['estimated_gpu_usd'] for x in queried if str(x['pod_id']) in phase_ids)
    report = {'verified_at': datetime.now(timezone.utc).isoformat(),
              'receipt_count_all_phases': len(receipts), 'phase17_receipt_count': len(phase_ids),
              'estimated_gpu_usd_all_phases': estimate, 'estimated_gpu_usd_phase17': phase_estimate,
              'billing_queries': queried,
              'receipted_cumulative_reserve_usd': reserve, 'pending_intent_reserve_usd': pending,
              'total_reserve_including_pending_usd': total_reserve,
              'available_budget_usd': 10.0 - total_reserve, 'budget_cap_usd': 10.0,
              'all_research_pods_absent': not untracked, 'untracked_cryo_pods': untracked,
              'receipt_pod_ids': sorted(phase_ids),
              'all_research_pod_ids': sorted(str(x) for x in receipts),
              'unrelated_pods_untouched': len(pods) if pods is not None else None,
              'note': 'Final read-only report; prelaunch reconciliation and quote preserved; estimates are not final invoices.'}
    billing_api.write_json(OUT / 'compute-costs.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args(argv)
    receipts, pods, untracked, queried, reserve, estimate = snapshot()
    pending = launcher.pending_reserve()
    if args.final:
        result = final_report(receipts, queried, reserve, estimate, untracked, pending, pods)
    else:
        write_prelaunch(receipts, pods, untracked, queried, reserve, estimate)
        result = {'receipt_count': len(receipts), 'prior_gpu_reserve_usd': reserve,
                  'pending_intent_reserve_usd': pending, 'all_research_pods_absent': not untracked}
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
