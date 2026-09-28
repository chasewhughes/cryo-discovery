"""Read-only Phase 16 billing reconciliation and GPU quote snapshot."""
import argparse, json, math, os, subprocess, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/phase16'

def key():
    return subprocess.check_output(['security','find-generic-password','-s','cryo.runpod.api-key','-w'], text=True).strip()

def api(method, endpoint, payload=None):
    body=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request('https://rest.runpod.io/v1/'+endpoint,data=body,method=method,
      headers={'Authorization':'Bearer '+key(),'Content-Type':'application/json','User-Agent':'cryo-research/0.1'})
    with urllib.request.urlopen(req,timeout=40) as response:
        data=response.read(); return json.loads(data) if data else None

def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n'); os.replace(temp,path)

def load_receipts():
    rows={}
    for path in (ROOT/'data').glob('phase*/runpod*receipt.json'):
        row=json.loads(path.read_text()); ident=row.get('id') or row.get('pod_id')
        if not ident or row.get('deleted') is not True: raise ValueError('unconfirmed prior research Pod: '+str(path))
        cost=float(row['estimated_gpu_cost_usd'])
        if not math.isfinite(cost) or cost<0: raise ValueError('invalid prior receipt cost')
        old=rows.get(str(ident))
        if old and (old['estimated_gpu_cost_usd']!=cost or old.get('deleted')!=row.get('deleted')): raise ValueError('conflicting duplicate receipt '+str(ident))
        rows[str(ident)]=row
    return rows

def pending_intents():
    """Mirror runpod_boltz.pending_reserve without importing launcher state."""
    pending=[]; seen=set()
    base=ROOT/'data/raw/phase16'
    for path in base.glob('attempt*/intent.json'):
        intent=json.loads(path.read_text()); attempt=intent.get('attempt'); seen.add(attempt)
        receipt=OUT/f"runpod-attempt{attempt}-receipt.json"
        reconciliation=path.with_name('intent-reconciliation.json')
        rec=json.loads(reconciliation.read_text()) if reconciliation.exists() else {}
        if receipt.exists() or rec.get('definitive_rejection') or rec.get('no_matching_pod_at_deadline'): continue
        amount=float(intent.get('reserved_usd',0.9))
        if not math.isfinite(amount) or amount<0: raise ValueError('invalid pending intent reserve')
        pending.append({'attempt':attempt,'name':intent.get('name'),'reserved_usd':max(0.9,amount),'source':str(path.relative_to(ROOT))})
    # Preserve a pending intent if its watchdog wrote the audit outside raw storage.
    for path in OUT.glob('attempt*-unresolved-intent.json'):
        intent=json.loads(path.read_text()); attempt=int(intent.get('attempt'))
        if attempt in seen or (OUT/f"runpod-attempt{attempt}-receipt.json").exists(): continue
        if intent.get('definitive_rejection') or intent.get('no_matching_pod_at_deadline'): continue
        amount=float(intent.get('reserve_until_deadline_usd',intent.get('reserved_usd',0.9)))
        if not math.isfinite(amount) or amount<0: raise ValueError('invalid pending intent reserve')
        pending.append({'attempt':attempt,'name':intent.get('name'),'reserved_usd':max(0.9,amount),'source':str(path.relative_to(ROOT))})
    return pending

def bill(item):
    ident,row=item
    now=datetime.now(timezone.utc).isoformat()
    query=urllib.parse.urlencode({'podId':ident,'bucketSize':'hour','grouping':'podId','startTime':'2026-01-01T00:00:00Z','endTime':now})
    records=api('GET','billing/pods?'+query)
    if not isinstance(records,list): raise ValueError('unexpected billing response for '+ident)
    amount=sum(float(x['amount']) for x in records); billed=sum(float(x.get('timeBilledMs',0)) for x in records)
    if not math.isfinite(amount) or amount<0 or not math.isfinite(billed) or billed<0: raise ValueError('invalid billing record for '+ident)
    elapsed=(float(row['ended_epoch'])-float(row['created_epoch']))*1000
    if elapsed<0: raise ValueError('invalid receipt timing for '+ident)
    return {'pod_id':ident,'records':records,'posted_amount_usd':amount,'posted_billed_time_ms':billed,
            'recorded_elapsed_ms':elapsed,'estimated_gpu_usd':float(row['estimated_gpu_cost_usd']),
            'conservative_reserve_usd':max(amount,float(row['estimated_gpu_cost_usd']))}

def quote_one(gpu_id):
    query='query { gpuTypes(input: {id: '+json.dumps(gpu_id)+'}) { id securePrice communityPrice } }'
    req=urllib.request.Request('https://api.runpod.io/graphql',data=json.dumps({'query':query}).encode(),
      headers={'Authorization':'Bearer '+key(),'Content-Type':'application/json','User-Agent':'cryo-research/0.1'})
    with urllib.request.urlopen(req,timeout=40) as response: body=json.load(response)
    rows=((body.get('data') or {}).get('gpuTypes') or [])
    errors=body.get('errors')
    if errors: return {'id':gpu_id,'error':'GraphQL query failed','error_count':len(errors)}
    if len(rows)!=1: return {'id':gpu_id,'error':'GPU quote unavailable'}
    return {'id':gpu_id,'securePrice':rows[0].get('securePrice'),'communityPrice':rows[0].get('communityPrice')}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--final',action='store_true'); args=p.parse_args()
    receipts=load_receipts(); pods=api('GET','pods')
    if not isinstance(pods,list): raise ValueError('unexpected Pod response')
    ids=set(receipts); active_ids={str(x.get('id')) for x in pods}
    if ids & active_ids: raise ValueError('prior research Pod remains present')
    untracked=[{'id':x.get('id'),'name':x.get('name'),'costPerHr':x.get('costPerHr')} for x in pods if str(x.get('name','')).startswith('cryo-') and str(x.get('id')) not in ids]
    with ThreadPoolExecutor(max_workers=3) as pool: billing=list(pool.map(bill,receipts.items()))
    now=datetime.now(timezone.utc).isoformat(); reserve=sum(x['conservative_reserve_usd'] for x in billing)
    pending=pending_intents(); pending_reserve=sum(x['reserved_usd'] for x in pending)
    result={'verified_at':now,'all_prior_research_pods_absent':not bool(ids & active_ids) and not bool(untracked),'untracked_cryo_pods':untracked,
      'pending_intents':pending,'pending_reserve_usd':pending_reserve,
      'prior_gpu_reserve_usd':reserve,'receipted_prior_gpu_reserve_usd':reserve,
      'total_reserve_including_pending_usd':reserve+pending_reserve,
      'estimated_prior_gpu_usd':sum(x['estimated_gpu_usd'] for x in billing),
      'billing_queries':billing,'unrelated_pods_untouched':len(pods),
      'note':'Read-only snapshot. Reserve is the sum of the larger posted billing amount or receipt elapsed GPU estimate per Pod; posted billing may be incomplete and is not a final invoice.'}
    if args.final:
        phase16_ids=set()
        for path in OUT.glob('runpod*receipt.json'):
            row=json.loads(path.read_text()); phase16_ids.add(str(row.get('id') or row.get('pod_id')))
        costs={'checked_at':now,
          'cumulative_estimated_gpu_usd':result['estimated_prior_gpu_usd'],
          'phase16_estimated_gpu_usd':sum(x['estimated_gpu_usd'] for x in billing if x['pod_id'] in phase16_ids),
          'conservative_cumulative_reserve_usd':reserve+pending_reserve,
          'receipted_cumulative_reserve_usd':reserve,
          'final_posted_reserve_usd':reserve,
          'pending_reserve_usd':pending_reserve,
          'pending_intents':pending,
          'all_research_pods_absent':result['all_prior_research_pods_absent'],
          'research_pod_ids':sorted(receipts),
          'untracked_cryo_pods':untracked,
          'unrelated_pods_untouched':len(pods),
          'user_cumulative_gpu_limit_usd':10,
          'billing_queries':billing,
          'billing_note':result['note']}
        write_json(OUT/'compute-costs.json',costs)
        print(json.dumps({k:v for k,v in costs.items() if k!='billing_queries'},allow_nan=False)); return
    write_json(OUT/'billing-reconciliation.json',result)
    quotes=[quote_one(x) for x in ['NVIDIA GeForce RTX 4090','NVIDIA RTX A5000','NVIDIA RTX A6000']]
    write_json(OUT/'gpu-quote.json',{'checked_at':datetime.now(timezone.utc).isoformat(),'requested_gpu_ids':[x['id'] for x in quotes],'quotes':quotes,'selection_note':'Prioritize RTX 4090; A5000/A6000 are comparison quotes and require >=24 GB VRAM confirmation before use.'})
    print(json.dumps({'prior_gpu_reserve_usd':result['prior_gpu_reserve_usd'],'receipted_prior_gpu_reserve_usd':reserve,'pending_reserve_usd':pending_reserve,'prior_pod_count':len(receipts),'all_prior_research_pods_absent':result['all_prior_research_pods_absent'],'untracked_cryo_pod_count':len(untracked),'quotes':quotes},allow_nan=False))

if __name__=='__main__': main()
