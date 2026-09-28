"""Verify archived two-seed predictions and evaluate the frozen ROCK2 hypothesis."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import tarfile
import numpy as np
from scipy.stats import spearmanr

ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def finite(x): return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def spearman(x,y):
    if len(x)<2 or len(set(x))<2 or len(set(y))<2: return None
    return float(spearmanr(x,y).statistic)
def metrics(rows,seed_index=None):
    y=np.array([r['observed_pIC50'] for r in rows])
    pred=np.array([r['panel_mean_pIC50'] if seed_index is None else r['panel_seed_pIC50'][seed_index] for r in rows])
    mean=np.array([r['control_pIC50'] for r in rows]); nn=np.array([r['baseline_predicted_pIC50'] for r in rows])
    mae=float(np.mean(abs(pred-y))); mean_mae=float(np.mean(abs(mean-y)))
    return {'n':len(rows),'panel_mae_pIC50':mae,'mean_control_mae_pIC50':mean_mae,
            'neighbor_baseline_mae_pIC50':float(np.mean(abs(nn-y))),
            'mae_improvement_fraction':1-mae/mean_mae if mean_mae else None,'spearman':spearman(pred.tolist(),y.tolist())}
def bootstrap(rows,n=2000,seed=1703):
    clusters={}
    for r in rows: clusters.setdefault(r['scaffold'],[]).append(r)
    keys=list(clusters); rng=np.random.default_rng(seed); gains=[]; cors=[]
    for _ in range(n):
        sample=[r for k in rng.choice(keys,len(keys),replace=True) for r in clusters[k]]
        m=metrics(sample)
        if m['mae_improvement_fraction'] is not None: gains.append(m['mae_improvement_fraction'])
        if m['spearman'] is not None: cors.append(m['spearman'])
    return {'resamples':n,'seed':seed,'clusters':len(keys),'percentiles':[2.5,50,97.5],
            'mae_improvement_fraction':np.percentile(gains,[2.5,50,97.5]).tolist() if gains else None,
            'spearman':np.percentile(cors,[2.5,50,97.5]).tolist() if cors else None,
            'finite_spearman_resamples':len(cors),'interpretation':'Descriptive cluster-resampling intervals within one medicinal-chemistry series; not external-generalization uncertainty.'}
def safe_artifact(seedroot,value):
    rel=Path(str(value))
    if rel.is_absolute() or '..' in rel.parts or not rel.parts: raise ValueError('unsafe artifact path')
    p=(seedroot/rel).resolve(); p.relative_to(seedroot.resolve())
    if not p.is_file(): raise ValueError('missing artifact')
    return p

def check(attempt,output):
    folder=ROOT/'data/phase17'; receiptfile=folder/f'runpod-attempt{attempt}-receipt.json'
    rec=read(receiptfile) if receiptfile.exists() else {}
    matches=[p for p in folder.glob('panel-plan*.json') if sha(p)==rec.get('plan_sha256')]
    planfile=matches[0] if len(matches)==1 else folder/'panel-plan.json'; plan=read(planfile); ev=plan['evaluation']
    raw=ROOT/'data/raw/phase17'/f'attempt{attempt}'; summaryfile=raw/'runs/summary.json'; receiptfile=folder/f'runpod-attempt{attempt}-receipt.json'
    errors=[]; panel=[]; telemetry=[]; archived={}
    data=read(summaryfile) if summaryfile.exists() else {}; rec=read(receiptfile) if receiptfile.exists() else {}
    if not data: errors.append('missing summary')
    if rec.get('deleted') is not True: errors.append('Pod deletion not confirmed')
    if rec.get('plan_sha256')!=sha(planfile): errors.append('receipt plan hash mismatch')
    archive=raw/'results.tar.gz'; archive_ok=archive.exists() and sha(archive)==rec.get('result_archive_sha256')
    if not archive_ok: errors.append('archive receipt hash mismatch')
    else:
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                if member.isfile() and member.name.endswith(('.json','.cif','.mmcif')):
                    archived[member.name]=hashlib.sha256(tar.extractfile(member).read()).hexdigest()
        if not summaryfile.exists() or archived.get('runs/summary.json')!=sha(summaryfile): errors.append('extracted summary differs from archive')
    for path,want in {**plan['source_sha256'],**plan['provenance_sha256']}.items():
        p=ROOT/path
        if not p.exists() or sha(p)!=want: errors.append('frozen source mismatch: '+path)
    expected=set(ev['primary_ids']); seeds=ev['seeds']
    hashes={Path(p).name:h for p,h in plan['source_sha256'].items() if p.startswith('data/phase17/boltz-inputs/')}
    if data.get('input_hashes')!=hashes or len(expected)!=43: errors.append('input identities/hashes differ from frozen panel')
    freeze=data.get('pip_freeze',[])
    if 'boltz==2.2.1' not in freeze or not any(re.fullmatch(r'torch==2\.8\.0(?:\+[A-Za-z0-9.]+)?',s) for s in freeze): errors.append('recorded package versions mismatch')
    ck=data.get('checkpoint_hashes',[])
    if len(ck)!=2 or {Path(x['path']).name:x['sha256'] for x in ck}!=plan['model_checkpoint_sha256']: errors.append('checkpoint digest mismatch')
    records=data.get('seeds',[]); byseed={x.get('seed'):x for x in records}
    if len(records)!=2 or set(byseed)!=set(seeds): errors.append('seed identities/count mismatch')
    predictions={ident:[] for ident in expected}
    for seed in seeds:
        c=byseed.get(seed,{})
        expected_cmd=['boltz','predict','data/phase17/boltz-inputs','--out_dir',f'/workspace/cryo/runs/seed-{seed}','--cache','/workspace/cryo/cache/boltz','--accelerator','gpu','--devices','1','--recycling_steps','3','--sampling_steps','200','--diffusion_samples','1','--sampling_steps_affinity','200','--diffusion_samples_affinity','5','--max_msa_seqs','512','--num_workers','1','--no_kernels','--seed',str(seed)]
        if c.get('command')!=expected_cmd: errors.append(f'seed {seed}: command mismatch')
        if c.get('status')!='completed' or c.get('returncode')!=0: errors.append(f'seed {seed}: incomplete execution')
        comps=c.get('output_validation',{}).get('compound_outputs',[])
        if len(comps)!=43 or {x['id'] for x in comps}!=expected: errors.append(f'seed {seed}: missing or duplicate compound identities')
        seedroot=raw/'runs'/f'seed-{seed}'
        for x in comps:
            ident=x['id']
            try:
                if ident not in expected: raise ValueError('unexpected identity')
                if len(x['affinity_json'])!=1 or len(x['structure_cif'])!=1: raise ValueError('missing/duplicate outputs')
                for artifact in x['affinity_json']+x['structure_cif']:
                    p=safe_artifact(seedroot,artifact['path']); digest=sha(p)
                    if p.stat().st_size==0 or digest!=artifact['sha256'] or archived.get('runs/'+f'seed-{seed}/'+artifact['path'])!=digest: raise ValueError('artifact digest mismatch')
                affinity=read(safe_artifact(seedroot,x['affinity_json'][0]['path']))
                values={k:affinity[k] for k in ('affinity_pred_value','affinity_probability_binary')}
                if not all(finite(v) for v in values.values()) or not 0<=values['affinity_probability_binary']<=1: raise ValueError('nonfinite/out-of-range output')
                if values!=x['affinity_fields']: raise ValueError('summary affinity differs from actual output')
                predictions[ident].append({'seed':seed,'pIC50':6-values['affinity_pred_value'],'binder_probability':values['affinity_probability_binary']})
            except (ValueError,KeyError,TypeError,OSError) as exc: errors.append(f'seed {seed}/{ident}: {exc}')
        telemetry.append({'seed':seed,'status':c.get('status'),'wall_seconds':c.get('wall_seconds'),'gpu_samples':c.get('gpu_samples',[]),'complete_compounds':sum(len(v)==seeds.index(seed)+1 for v in predictions.values())})
    baseline=read(ROOT/ev['baseline_source'])['predictions']; base={x['molecule_id']:x for x in baseline}
    if set(base)!=expected: errors.append('baseline identity set mismatch')
    for ident in sorted(expected):
        vals=predictions[ident]
        if len(vals)!=2 or [v['seed'] for v in vals]!=seeds:
            errors.append('incomplete repeated predictions: '+ident); continue
        b=base[ident]; values=[v['pIC50'] for v in vals]
        panel.append({'molecule_id':ident,'scaffold':b['scaffold'],'observed_pIC50':b['observed_pIC50'],
                      'control_pIC50':b['control_pIC50'],'baseline_predicted_pIC50':b['predicted_pIC50'],
                      'panel_seed_pIC50':values,'panel_mean_pIC50':float(np.mean(values)),
                      'seed_absolute_difference_pIC50':abs(values[0]-values[1]),'binder_probabilities':[v['binder_probability'] for v in vals]})
    decision='inconclusive'; computed=None; intervals=None
    if not errors:
        full=metrics(panel); sensitivity=[r for r in panel if r['molecule_id']!=ev['anchor_excluded_sensitivity']]
        computed={'full':full,'per_seed':{str(s):metrics(panel,i) for i,s in enumerate(seeds)},'anchor_excluded':metrics(sensitivity),
                  'median_seed_absolute_difference_pIC50':float(np.median([r['seed_absolute_difference_pIC50'] for r in panel]))}
        passed=finite(full['mae_improvement_fraction']) and full['mae_improvement_fraction']>=ev['minimum_mae_improvement_fraction'] and finite(full['spearman']) and full['spearman']>=ev['minimum_spearman']
        decision='supported_internal_benchmark' if passed else 'not_supported_internal_benchmark'
        intervals=bootstrap(panel,ev['bootstrap_samples'],ev['bootstrap_seed'])
    result={'attempt':attempt,'plan_id':plan['id'],'plan_sha256':sha(planfile),'verdict':decision,'validation_errors':errors,
            'archive_hash_verified':archive_ok,'metrics':computed,'bootstrap':intervals,'seeds':telemetry,
            'panel_predictions':panel,'limits':plan['limits']}
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n'); return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',type=int,default=1);p.add_argument('--output',type=Path,default=ROOT/'data/phase17/panel-results.json');a=p.parse_args()
    result=check(a.attempt,a.output); print(json.dumps({'verdict':result['verdict'],'errors':len(result['validation_errors'])}));return int(bool(result['validation_errors']))
if __name__=='__main__': raise SystemExit(main())
