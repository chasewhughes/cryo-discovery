#!/usr/bin/env python3
"""Run a frozen plan-defined scaffold ROCK2 panel twice with explicit seeds."""
from __future__ import annotations
import argparse, hashlib, json, math, os, signal, subprocess, sys, threading, time
from pathlib import Path
SEEDS=(2101,2102)

def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def json_affinity(p):
 try: d=json.loads(p.read_text())
 except Exception:return {}
 out={}
 def walk(x):
  if isinstance(x,dict):
   for k,v in x.items():
    if k in ('affinity_pred_value','affinity_probability_binary'): out[k]=v
    walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
 walk(d); return out
def inventory(root):
 out=[]
 for p in sorted(root.rglob('*')):
  if p.is_file() and p.suffix.lower() in ('.json','.cif','.mmcif'):
   out.append({'path':str(p.relative_to(root)),'sha256':sha(p),'bytes':p.stat().st_size,'affinity_fields':json_affinity(p) if p.suffix.lower()=='.json' else {}})
 return out

def validate_seed_outputs(inputs, root):
 details=[]
 expected={p.stem for p in inputs}
 observed={p.name[len('affinity_'):-len('.json')] for p in root.rglob('affinity_*.json') if p.is_file()}
 unexpected=sorted(observed-expected)
 for inp in inputs:
  ident=inp.stem
  aff=[p for p in root.rglob(f'affinity_{ident}.json') if p.is_file()]
  cif=[p for p in root.rglob(f'{ident}_model_*.cif') if p.is_file() and 'processed' not in p.parts]
  parsed=json_affinity(aff[0]) if len(aff)==1 else {}
  valid=len(aff)==1 and len(cif)==1 and all(isinstance(parsed.get(k),(int,float)) and not isinstance(parsed.get(k),bool) and math.isfinite(parsed[k]) for k in ('affinity_pred_value','affinity_probability_binary')) and 0<=parsed.get('affinity_probability_binary',-1)<=1
  details.append({'id':ident,'affinity_json':[{'path':str(p.relative_to(root)),'sha256':sha(p)} for p in aff],'structure_cif':[{'path':str(p.relative_to(root)),'sha256':sha(p)} for p in cif],'affinity_fields':parsed,'valid':valid})
 return {'compound_outputs':details,'predicted_affinity_count':sum(bool(x['affinity_fields']) for x in details),'predicted_structure_count':sum(bool(x['structure_cif']) for x in details),'unexpected_affinity_ids':unexpected,'all_expected_outputs_valid':not unexpected and all(x['valid'] for x in details)}

def gpu(stop,samples):
 while not stop.is_set():
  try:
   x=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,power.draw','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,check=True); samples.append({'time_epoch':time.time(),'raw':x.stdout.strip()})
  except Exception as e:samples.append({'time_epoch':time.time(),'error':type(e).__name__})
  stop.wait(5)
def main():
 plan_path=Path(__file__).resolve().parents[1]/'data/phase21/inference-config.json'
 plan=json.loads(plan_path.read_text())
 if plan.get('seeds')!=list(SEEDS): raise SystemExit('inference config seed mismatch')
 expected_ids=plan.get('panel_ids',[])
 if not expected_ids or len(expected_ids)!=len(set(expected_ids)): raise SystemExit('scaffold plan must define distinct panel_ids')
 expected_set=set(expected_ids)
 ap=argparse.ArgumentParser(); ap.add_argument('--input-dir',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--cache',type=Path,required=True); ap.add_argument('--deadline-epoch',type=float,required=True); ap.add_argument('--collection-reserve-seconds',type=float,default=300); ap.add_argument('--boltz',default='boltz'); a=ap.parse_args(); a.output.parent.mkdir(parents=True,exist_ok=True); a.cache.mkdir(parents=True,exist_ok=True)
 inputs=sorted(a.input_dir.glob('*.yaml')); result={'runner':'boltz_scaffold_inference.py','plan_id':plan.get('id'),'expected_inputs':len(expected_ids),'panel_ids':expected_ids,'input_count':len(inputs),'input_hashes':{p.name:sha(p) for p in inputs},'seeds':[],'deadline_epoch':a.deadline_epoch}
 if {p.stem for p in inputs}!=expected_set: result['error']='input YAML identities differ from scaffold plan panel_ids'; a.output.write_text(json.dumps(result,indent=2)+'\n'); return 1
 save_lock=threading.Lock()
 def save():
  with save_lock:
   tmp=a.output.with_suffix('.tmp'); tmp.write_text(json.dumps(result,indent=2)+'\n'); os.replace(tmp,a.output)
 for seed in SEEDS:
  out=a.output.parent/f'seed-{seed}'; rem=a.deadline_epoch-time.time()-a.collection_reserve_seconds; log=out/'inference.log'; samples=[]
  cmd=[a.boltz,'predict',str(a.input_dir), '--out_dir',str(out),'--cache',str(a.cache),'--accelerator','gpu','--devices','1','--recycling_steps','3','--sampling_steps','200','--diffusion_samples','1','--sampling_steps_affinity','200','--diffusion_samples_affinity','5','--max_msa_seqs','512','--num_workers','1','--no_kernels','--seed',str(seed)]
  case={'seed':seed,'output_dir':str(out),'command':cmd,'status':'not_started','started_epoch':time.time()}; result['seeds'].append(case)
  if out.exists(): case.update(status='output_dir_not_empty',error='refusing to reuse existing seed output directory'); save(); continue
  out.mkdir(parents=True,exist_ok=False); save()
  stop=threading.Event(); th=threading.Thread(target=gpu,args=(stop,samples),daemon=True); th.start()
  progress_stop=threading.Event()
  def progress():
   while not progress_stop.wait(30):
    case['progress']=validate_seed_outputs(inputs,out); save()
  progress_thread=threading.Thread(target=progress,daemon=True); progress_thread.start()
  if rem<=0: case.update(status='skipped_deadline')
  else:
   try:
    with log.open('w') as f:
     proc=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,start_new_session=True); deadline=min(rem, a.deadline_epoch-time.time()-a.collection_reserve_seconds); rc=proc.wait(timeout=max(1,deadline)); case.update(returncode=rc,status='completed' if rc==0 else 'failed')
   except subprocess.TimeoutExpired:
    case['status']='deadline_timeout'
    try: os.killpg(proc.pid,signal.SIGTERM); proc.wait(timeout=10)
    except Exception:
     try: os.killpg(proc.pid,signal.SIGKILL)
     except ProcessLookupError: pass
     proc.wait(timeout=10)
   except Exception as e: case.update(status='runner_error',error=f'{type(e).__name__}: {e}')
  progress_stop.set(); progress_thread.join(timeout=2); stop.set(); th.join(timeout=6); case.update(finished_epoch=time.time(),wall_seconds=time.time()-case['started_epoch'],gpu_samples=samples,log=str(log),artifacts=inventory(out)); case['output_validation']=validate_seed_outputs(inputs,out);
  if case['status']=='completed' and not case['output_validation']['all_expected_outputs_valid']: case['status']='missing_outputs'
  save()
 try: result['pip_freeze']=subprocess.run([sys.executable,'-m','pip','freeze'],capture_output=True,text=True,timeout=20).stdout.splitlines()
 except Exception: result['pip_freeze']=[]
 result['checkpoint_hashes']=[{'path':str(p),'sha256':sha(p)} for p in sorted({p for p in a.cache.rglob('*') if p.is_file() and any(x in p.name.lower() for x in ('ckpt','checkpoint','weight'))})]
 save(); return 0 if all(x['status']=='completed' for x in result['seeds']) else 1
if __name__=='__main__':raise SystemExit(main())
