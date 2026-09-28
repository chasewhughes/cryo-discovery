"""Monitor the existing Phase 13 batch and collect ready results; never rents GPUs."""
import json,time
from concurrent.futures import ThreadPoolExecutor
try:
    from .runpod_phase13 import LOCAL, status_one, collect_one
except ImportError:
    from runpod_phase13 import LOCAL, status_one, collect_one

def main():
    states=json.loads((LOCAL/'batch-state.json').read_text());started=time.time()
    while time.time()-started<4000:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures={j:pool.submit(status_one,s) for j,s in states.items()}
            rows={}
            for j,future in futures.items():
                try:rows[j]=future.result()
                except Exception as exc:rows[j]={'error_type':type(exc).__name__}
        print(json.dumps({'elapsed_seconds':round(time.time()-started),'status':rows}),flush=True)
        if all(r.get('deleted') for r in rows.values()):return
        for j,row in rows.items():
            if row.get('deleted'):continue
            if (row.get('worker') or {}).get('results_ready'):
                try:print(json.dumps(collect_one(states[j])),flush=True)
                except Exception as exc:print(json.dumps({'job_id':j,'collection_error':type(exc).__name__}),flush=True)
        time.sleep(45)
    raise TimeoutError('Monitoring limit reached; inspect batch receipts and watchdogs')

if __name__=='__main__':main()
