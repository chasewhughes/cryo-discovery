#!/usr/bin/env python3
"""Bounded sequential Boltz-2 pilot runner for two prepared control inputs."""
from __future__ import annotations
import argparse, hashlib, json, math, os, signal, subprocess, sys, threading, time
from pathlib import Path
EXPECTED={'CHEMBL4522042.yaml':'known_bound_ligand','CHEMBL4540054.yaml':'measured_right_censored_weak_control'}
def sha256(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def files_with(root,suffix): return sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower()==suffix)
def collect_outputs(root):
 found=[]
 for p in root.rglob('*.json'):
  try: d=json.loads(p.read_text())
  except Exception: continue
  vals={}
  def walk(x):
   if isinstance(x,dict):
    for k,v in x.items():
     if k in ('affinity_pred_value','affinity_probability_binary','confidence_score'): vals[k]=v
     walk(v)
   elif isinstance(x,list):
    for v in x: walk(v)
  walk(d)
  if vals: found.append({'path':str(p),'keys':sorted(vals),'data':vals})
 return found
def checkpoint_files(args):
 roots=[args.cache,args.output.parent/'cases']; out=[]
 for root in roots:
  if root.exists(): out += [p for p in root.rglob('*') if p.is_file() and any(k in p.name.lower() for k in ('ckpt','checkpoint','weights'))]
 return [{'path':str(p),'sha256':sha256(p)} for p in sorted(set(out))]
def gpu_sampler(stop,samples):
 while not stop.is_set():
  try:
   x=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,power.draw','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,check=True); samples.append({'time_epoch':time.time(),'raw':x.stdout.strip()})
  except Exception as e: samples.append({'time_epoch':time.time(),'error':type(e).__name__})
  stop.wait(5)
def run_case(path,role,args,deadline):
 out=args.output.parent/'cases'/path.stem; out.mkdir(parents=True,exist_ok=True); so, se=out/'stdout.log',out/'stderr.log'; rem=deadline-time.time()-args.collection_reserve_seconds
 rec={'input':str(path),'role':role,'input_sha256':sha256(path),'output_dir':str(out),'command':[],'started_epoch':time.time(),'status':'not_started'}
 if rem<=0: rec.update(status='skipped_deadline',error='deadline minus collection reserve exhausted'); return rec
 cmd=[args.boltz,'predict',str(path),'--out_dir',str(out),'--cache',str(args.cache),'--accelerator','gpu','--devices','1','--recycling_steps','3','--sampling_steps','200','--diffusion_samples','1','--sampling_steps_affinity','200','--diffusion_samples_affinity','5','--num_workers','1','--no_kernels']; rec['command']=cmd; samples=[]; stop=threading.Event(); th=threading.Thread(target=gpu_sampler,args=(stop,samples),daemon=True); th.start()
 try:
  with so.open('w') as fo,se.open('w') as fe:
   proc=subprocess.Popen(cmd,stdout=fo,stderr=fe,text=True,start_new_session=True)
   try: rc=proc.wait(timeout=max(1,rem))
   except subprocess.TimeoutExpired:
    rec['status']='deadline_timeout'
    try: os.killpg(proc.pid,signal.SIGTERM)
    except Exception: pass
    try: proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
     try: os.killpg(proc.pid,signal.SIGKILL)
     except Exception: pass
     proc.wait()
    rc=None
  if rec['status']!='deadline_timeout': rec.update(returncode=rc,status='completed' if rc==0 else 'failed')
 except Exception as e: rec.update(status='runner_error',error=f'{type(e).__name__}: {e}')
 finally:
  stop.set(); th.join(timeout=6); rec.update(gpu_samples=samples,finished_epoch=time.time())
 rec['wall_seconds']=rec['finished_epoch']-rec['started_epoch']; rec['stdout_log']=str(so); rec['stderr_log']=str(se); rec['stdout_tail']=so.read_text(errors='replace')[-4000:] if so.exists() else ''; rec['stderr_tail']=se.read_text(errors='replace')[-4000:] if se.exists() else ''
 rec['output_artifacts']=collect_outputs(out); structural=files_with(out,'.cif')+files_with(out,'.mmcif'); rec['structural_files']=[str(x) for x in structural]; aff={k:v for x in rec['output_artifacts'] for k,v in x['data'].items() if k in ('affinity_pred_value','affinity_probability_binary')}; rec['affinity_fields']=aff
 valid=set(aff)>= {'affinity_pred_value','affinity_probability_binary'} and all(isinstance(v,(int,float)) and math.isfinite(v) for v in aff.values())
 if rec['status']=='completed' and not (valid and structural): rec.update(status='missing_outputs',error='exit 0 without finite affinity fields and structural CIF/mmCIF')
 return rec
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--input-dir',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--cache',type=Path,required=True); ap.add_argument('--deadline-epoch',type=float,required=True); ap.add_argument('--collection-reserve-seconds',type=float,default=120); ap.add_argument('--boltz',default='boltz'); a=ap.parse_args(); a.output.parent.mkdir(parents=True,exist_ok=True); a.cache.mkdir(parents=True,exist_ok=True); results=[]
 def save(progress=False): a.output.write_text(json.dumps({'runner':'boltz_pilot_inference.py','cases':results,'deadline_epoch':a.deadline_epoch,'progress':progress},indent=2)+'\n')
 for name,role in EXPECTED.items():
  p=a.input_dir/name
  if not p.is_file(): results.append({'input':str(p),'role':role,'status':'missing_input'})
  else: results.append(run_case(p,role,a,a.deadline_epoch))
  save(True)
 try: freeze=subprocess.run([sys.executable,'-m','pip','freeze'],capture_output=True,text=True,timeout=20).stdout.splitlines()
 except Exception: freeze=[]
 payload={'runner':'boltz_pilot_inference.py','created_epoch':time.time(),'deadline_epoch':a.deadline_epoch,'collection_reserve_seconds':a.collection_reserve_seconds,'parameters':{'recycling_steps':3,'sampling_steps':200,'diffusion_samples':1,'sampling_steps_affinity':200,'diffusion_samples_affinity':5,'no_kernels':True},'cases':results,'checkpoint_sha256':checkpoint_files(a),'pip_freeze':freeze}; a.output.write_text(json.dumps(payload,indent=2)+'\n'); return 0 if all(x.get('status')=='completed' for x in results) else 1
if __name__=='__main__': raise SystemExit(main())
