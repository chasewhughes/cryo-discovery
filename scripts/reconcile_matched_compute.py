"""Read-only billing and quote snapshot before/after Phase 13 rentals."""
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
try:
    from .runpod_stability import api, key, write_json
except ImportError:
    from runpod_stability import api, key, write_json

ROOT=Path(__file__).resolve().parents[1]

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--final',action='store_true');args=parser.parse_args()
    receipts={}
    for path in (ROOT/'data').glob('phase*/runpod*receipt.json'):
        row=json.loads(path.read_text()); ident=row.get('id') or row.get('pod_id')
        if not ident or row.get('deleted') is not True: raise ValueError('Unconfirmed prior pod')
        cost=float(row['estimated_gpu_cost_usd'])
        if not math.isfinite(cost) or cost<0: raise ValueError('Invalid prior cost')
        if ident not in receipts or cost>receipts[ident]['estimated_gpu_cost_usd']: receipts[ident]=row
    pods=api('GET','pods')
    if not isinstance(pods,list): raise ValueError('Unexpected pods response')
    active={r['id'] for r in pods}
    if active.intersection(receipts): raise ValueError('Prior research Pod remains present')
    now=datetime.now(timezone.utc); rows=[]
    for ident,receipt in receipts.items():
        params=urllib.parse.urlencode({'podId':ident,'bucketSize':'hour','grouping':'podId',
            'startTime':'2026-09-01T00:00:00Z','endTime':now.isoformat()})
        records=api('GET','billing/pods?'+params)
        if not isinstance(records,list): raise ValueError('Unexpected billing response')
        amount=sum(float(r['amount']) for r in records)
        if not math.isfinite(amount) or amount<0: raise ValueError('Invalid billing amount')
        billed_ms=sum(float(r.get('timeBilledMs',0)) for r in records)
        elapsed_ms=(receipt['ended_epoch']-receipt['created_epoch'])*1000
        rows.append({'pod_id':ident,'records':records,'posted_amount_usd':amount,
                     'posted_billed_time_ms':billed_ms,'recorded_elapsed_ms':elapsed_ms,
                     'posted_time_fraction_of_recorded_elapsed':billed_ms/elapsed_ms if elapsed_ms else None,
                     'estimated_gpu_usd':receipt['estimated_gpu_cost_usd'],
                     'conservative_reserve_usd':max(amount,receipt['estimated_gpu_cost_usd'])})
    output={'verified_at':now.isoformat(),'all_prior_research_pods_absent':True,
            'prior_gpu_reserve_usd':sum(r['conservative_reserve_usd'] for r in rows),
            'estimated_prior_gpu_usd':sum(r['estimated_gpu_usd'] for r in rows),
            'billing_queries':rows,'unrelated_pods_untouched':len(pods),
            'note':'Reserve the larger of posted provider amount (may include storage) and elapsed-time GPU estimate for each Pod. Posted records may be incomplete; not a final invoice.'}
    if args.final:
        phase_ids=set()
        for path in (ROOT/'data/phase13').glob('runpod*receipt.json'):
            r=json.loads(path.read_text());phase_ids.add(r.get('id') or r.get('pod_id'))
        costs={'checked_at':now.isoformat(),'cumulative_estimated_gpu_usd':output['estimated_prior_gpu_usd'],
               'phase13_estimated_gpu_usd':sum(r['estimated_gpu_usd'] for r in rows if r['pod_id'] in phase_ids),
               'conservative_cumulative_reserve_usd':output['prior_gpu_reserve_usd'],
               'all_research_pods_absent':True,'research_pod_ids':list(receipts),
               'unrelated_pods_untouched':len(pods),'user_cumulative_gpu_limit_usd':10,
               'billing_queries':rows,'billing_note':output['note']}
        write_json(ROOT/'data/phase13/compute-costs.json',costs)
        print(json.dumps({k:v for k,v in costs.items() if k!='billing_queries'}));return
    write_json(ROOT/'data/phase13/billing-reconciliation.json',output)
    req=urllib.request.Request('https://api.runpod.io/graphql',
        data=json.dumps({'query':'query { gpuTypes(input: {id: "NVIDIA GeForce RTX 4090"}) { id securePrice communityPrice } }'}).encode(),
        headers={'Authorization':'Bearer '+key(),'Content-Type':'application/json','User-Agent':'cryo-research/0.1'})
    with urllib.request.urlopen(req,timeout=40) as response: quote=json.load(response)
    write_json(ROOT/'data/phase13/gpu-quote.json',{'checked_at':datetime.now(timezone.utc).isoformat(),'response':quote})
    print(json.dumps({'prior_gpu_reserve_usd':output['prior_gpu_reserve_usd'],'all_prior_pods_absent':True,'quote':quote}))

if __name__=='__main__': main()
