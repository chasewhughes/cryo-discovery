#!/usr/bin/env python3
"""Validate and summarize a frozen two-control Boltz pilot archive."""
from __future__ import annotations
import argparse, hashlib, json, math
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXPECTED={'CHEMBL4522042.yaml':'known_bound_ligand','CHEMBL4540054.yaml':'measured_right_censored_weak_control'}
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def finite(x): return isinstance(x,(int,float)) and math.isfinite(x)
def localize(raw, value):
 s=str(value); prefix='/workspace/cryo/runs/'; marker='/runs/'
 if not s.startswith(prefix) or marker not in s: return None
 rel=Path(s.split(marker,1)[1])
 if not rel.parts or any(p in ('','..') for p in rel.parts) or rel.is_absolute(): return None
 candidate=(raw/'runs'/rel).resolve()
 try: candidate.relative_to((raw/'runs').resolve())
 except ValueError: return None
 return candidate
def affinity_values(value):
 out={}
 def walk(x):
  if isinstance(x,dict):
   for k,v in x.items():
    if k in ('affinity_pred_value','affinity_probability_binary'): out[k]=v
    walk(v)
  elif isinstance(x,list):
   for v in x: walk(v)
 walk(value); return out
def check(attempt, output):
 raw=ROOT/'data/raw/phase16'/f'attempt{attempt}'; summary=raw/'runs'/'summary.json'; errors=[]
 if not summary.exists(): errors.append('missing summary.json')
 receipt=ROOT/'data/phase16'/f'runpod-attempt{attempt}-receipt.json'
 if not receipt.exists(): errors.append('missing attempt receipt')
 data=json.loads(summary.read_text()) if summary.exists() else {}
 rec=json.loads(receipt.read_text()) if receipt.exists() else {}
 plan_candidates=list((ROOT/'data/phase16').glob('pilot-plan*.json')); plan=None
 for candidate in plan_candidates:
  if rec.get('plan_sha256') == sha(candidate): plan=json.loads(candidate.read_text()); break
 if plan is None:
  default=ROOT/'data/phase16/pilot-plan.json'
  plan=json.loads(default.read_text()) if default.exists() else {}
  if rec: errors.append('receipt plan_sha256 does not match a local frozen pilot plan')
 if rec.get('deleted') is not True: errors.append('receipt does not confirm deleted=true')
 expected_config={'recycling_steps':3,'sampling_steps':200,'diffusion_samples':1,'sampling_steps_affinity':200,'diffusion_samples_affinity':5,'no_kernels':True}
 config=data.get('parameters',{}); config_valid=all(config.get(k)==v for k,v in expected_config.items())
 if not config_valid: errors.append('summary parameters do not match frozen plan')
 raw_cases=data.get('cases',[]); cases={Path(x.get('input','')).name:x for x in raw_cases}
 if set(cases)!=set(EXPECTED): errors.append('unexpected or missing control identities')
 if len(cases)!=len(raw_cases): errors.append('duplicate or malformed control entries')
 results=[]
 for name,role in EXPECTED.items():
  c=cases.get(name); item={'input':name,'expected_role':role}
  if not c: item.update(status='missing_case',pIC50_equivalent=None,affinity_fields={},affinity_finite=False,probability_in_range=False); errors.append(f'missing case {name}'); results.append(item); continue
  artifact_data=[a.get('data',{}) for a in c.get('output_artifacts',[])]
  confidence={k:v for d in artifact_data for k,v in d.items() if 'confidence' in k}
  confidence.update({k:v for k,v in c.items() if 'confidence' in k})
  item.update(status=c.get('status'),role=c.get('role'),wall_seconds=c.get('wall_seconds'),gpu_samples=c.get('gpu_samples',[]),affinity_fields=c.get('affinity_fields',{}),confidence_fields=confidence)
  if c.get('role') != role: errors.append(f'role mismatch {name}')
  expected_hash=plan.get('source_sha256',{}).get('data/phase15/boltz-inputs/'+name); item['input_sha256']=c.get('input_sha256'); item['input_hash_matches']=c.get('input_sha256')==expected_hash
  if not item['input_hash_matches']: errors.append(f'input hash mismatch {name}')
  localized_struct=[localize(raw,x) for x in c.get('structural_files',[])]
  item['structural_files']=[str(x) if x else str(y) for x,y in zip(localized_struct,c.get('structural_files',[]))]
  item['structural_paths_valid']=bool(localized_struct) and all(x is not None for x in localized_struct)
  item['structural_files_exist']=item['structural_paths_valid'] and all(x.exists() for x in localized_struct)
  aff=c.get('affinity_fields',{}); item['affinity_finite']=all(finite(aff.get(k)) for k in ('affinity_pred_value','affinity_probability_binary')); item['probability_in_range']=item['affinity_finite'] and 0<=aff['affinity_probability_binary']<=1
  artifact_checks=[]
  for artifact in c.get('output_artifacts',[]):
   lp=localize(raw,artifact.get('path','')); check={'recorded_path':artifact.get('path'),'valid_path':lp is not None,'exists':bool(lp and lp.exists())}
   if lp and lp.exists():
    try: check['file_sha256']=sha(lp); check['parsed_affinity']=affinity_values(json.loads(lp.read_text())); check['matches_summary']=check['parsed_affinity']=={k:v for k,v in aff.items() if k in ('affinity_pred_value','affinity_probability_binary')}
    except (OSError,ValueError, json.JSONDecodeError): check['matches_summary']=False
   artifact_checks.append(check)
  item['artifact_checks']=artifact_checks; item['artifact_data_verified']=any(x.get('valid_path') and x.get('exists') and x.get('matches_summary') and set(x.get('parsed_affinity',{})) >= {'affinity_pred_value','affinity_probability_binary'} for x in artifact_checks)
  cmd=c.get('command',[])
  expected_cmd=['boltz','predict','data/phase15/boltz-inputs/'+name,'--out_dir','/workspace/cryo/runs/cases/'+Path(name).stem,'--cache','/workspace/cryo/cache/boltz','--accelerator','gpu','--devices','1','--recycling_steps','3','--sampling_steps','200','--diffusion_samples','1','--sampling_steps_affinity','200','--diffusion_samples_affinity','5','--num_workers','1','--no_kernels']
  item['configuration_matches']=item['command_shape_valid']=cmd==expected_cmd
  if not item['configuration_matches']: errors.append(f'command settings mismatch {name}')
  item['pIC50_equivalent']=6-aff['affinity_pred_value'] if finite(aff.get('affinity_pred_value')) else None
  if c.get('status')!='completed' or not item['input_hash_matches'] or not item['structural_files_exist'] or not item['affinity_finite'] or not item['probability_in_range'] or not item['artifact_data_verified']: errors.append(f'incomplete or invalid outputs {name}')
  results.append(item)
 ordering=None
 if all(x['pIC50_equivalent'] is not None for x in results): ordering=results[0]['pIC50_equivalent']>results[1]['pIC50_equivalent']
 archive_hash=rec.get('result_archive_sha256'); archives=list((raw).glob('*.tar.gz'))+list(raw.glob('*.tgz')); archive_match=any(archive_hash==sha(p) for p in archives) if archive_hash else False
 if not archive_hash: errors.append('receipt lacks archive_sha256')
 elif not archive_match: errors.append('receipt archive hash not found among local archives')
 checkpoints=data.get('checkpoint_sha256',[]); checkpoint_names=[Path(x.get('path','')).name for x in checkpoints if isinstance(x,dict)]
 byname={Path(x.get('path','')).name:x.get('sha256') for x in checkpoints if isinstance(x,dict)}
 checkpoint_valid=set(checkpoint_names)=={'boltz2_conf.ckpt','boltz2_aff.ckpt'} and all(isinstance(byname.get(n),str) and re.fullmatch(r'[0-9a-fA-F]{64}',byname[n]) for n in ('boltz2_conf.ckpt','boltz2_aff.ckpt'))
 if not checkpoint_valid: errors.append('missing or unexpected checkpoint hashes')
 freeze=data.get('pip_freeze',[]); runtime_valid='boltz==2.2.1' in freeze and any(re.fullmatch(r'torch==2\.8\.0(?:\+[a-zA-Z0-9.]+)?',x) for x in freeze)
 if not runtime_valid: errors.append('pip_freeze missing boltz==2.2.1 or torch==2.8.0')
 out={'attempt':attempt,'plan_id':plan.get('id'),'claim_level':'smoke_execution_and_directional_comparison','valid':not errors,'validation_errors':errors,'archive_sha256':archive_hash,'archive_hash_verified':archive_match,'checkpoint_hashes':checkpoints,'checkpoint_names_valid':checkpoint_valid,'runtime_versions_valid':runtime_valid,'summary_parameters_valid':config_valid,'cases':results,'directional_ordering_known_pIC50_higher_than_weak_control':ordering,'observed_weak_control_pIC50_bound':'<5 (from >10,000 nM), not equality', 'limits':['Two controls do not support MAE, correlation, accuracy, calibration, efficacy, or novelty claims.','pIC50 is only the documented 6-affinity_pred_value conversion; binder probability remains separate.']}
 output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(out,indent=2)+'\n'); return out

def main():
 p=argparse.ArgumentParser(); p.add_argument('--attempt',type=int,default=1); p.add_argument('--output',type=Path,default=ROOT/'data/phase16/pilot-results.json'); a=p.parse_args(); r=check(a.attempt,a.output); print(json.dumps({'errors':len(r['validation_errors']),'output':str(a.output)})); return 0 if not r['validation_errors'] else 1
if __name__=='__main__': raise SystemExit(main())
