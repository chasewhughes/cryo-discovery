"""Read local Phase20 monitor status without printing affinity values or credentials."""
import json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 d=ROOT/'data/raw/phase20/attempt1';s=json.loads((d/'state.json').read_text());p=d/'last-worker-status.json';r=json.loads(p.read_text()) if p.exists() else {}
 seeds=r.get('progress',{}).get('seeds',[])
 receipt=ROOT/'data/phase20/runpod-attempt1-receipt.json'
 result={'state':r.get('state','provisioning'),'elapsed_minutes':round((time.time()-s['created_epoch'])/60,1),'status_age_seconds':round(time.time()-p.stat().st_mtime,1) if p.exists() else None,
  'seeds':[{'seed':x['seed'],'status':('running_or_loading' if x['status']=='not_started' else x['status']),'affinity_count':x.get('progress',x.get('output_validation',{})).get('predicted_affinity_count',0),'structure_count':x.get('progress',x.get('output_validation',{})).get('predicted_structure_count',0)} for x in seeds],
  'deleted':json.loads(receipt.read_text()).get('deleted') if receipt.exists() else False}
 print(json.dumps(result))
if __name__=='__main__':main()
