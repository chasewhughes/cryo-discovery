"""Verify archived two-seed predictions and evaluate the frozen orthogonal ROCK2 and calibration hypotheses."""
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
def safe_artifact(seedroot,value):
    rel=Path(str(value))
    if rel.is_absolute() or '..' in rel.parts or not rel.parts: raise ValueError('unsafe artifact path')
    p=(seedroot/rel).resolve(); p.relative_to(seedroot.resolve())
    if not p.is_file(): raise ValueError('missing artifact')
    return p

def check(attempt,output):
    folder=ROOT/'data/phase19'; receiptfile=folder/f'runpod-attempt{attempt}-receipt.json'
    rec=read(receiptfile) if receiptfile.exists() else {}
    matches=[p for p in folder.glob('orthogonal-plan*.json') if sha(p)==rec.get('plan_sha256')]
    planfile=matches[0] if len(matches)==1 else folder/'orthogonal-plan.json'; plan=read(planfile); ev=plan['evaluation']
    raw=ROOT/'data/raw/phase19'/f'attempt{attempt}'; summaryfile=raw/'runs/summary.json'; receiptfile=folder/f'runpod-attempt{attempt}-receipt.json'
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
    if ev.get('required_complete_predictions')!=len(expected)*len(seeds): errors.append('required prediction count differs from frozen identities')
    if data.get('plan_id')!=plan['id']: errors.append('runtime plan identity mismatch')
    hashes={Path(p).name:h for p,h in plan['source_sha256'].items() if p.startswith('data/phase19/boltz-inputs/')}
    if data.get('input_hashes')!=hashes or len(expected)!=len(ev['primary_ids']) or len(expected)<20: errors.append('input identities/hashes differ from frozen panel')
    freeze=data.get('pip_freeze',[])
    if 'boltz==2.2.1' not in freeze or not any(re.fullmatch(r'torch==2\.8\.0(?:\+[A-Za-z0-9.]+)?',s) for s in freeze): errors.append('recorded package versions mismatch')
    ck=data.get('checkpoint_hashes',[])
    if len(ck)!=2 or {Path(x['path']).name:x['sha256'] for x in ck}!=plan['model_checkpoint_sha256']: errors.append('checkpoint digest mismatch')
    records=data.get('seeds',[]); byseed={x.get('seed'):x for x in records}
    if len(records)!=2 or set(byseed)!=set(seeds): errors.append('seed identities/count mismatch')
    predictions={ident:[] for ident in expected}
    for seed in seeds:
        c=byseed.get(seed,{})
        expected_cmd=['boltz','predict','data/phase19/boltz-inputs','--out_dir',f'/workspace/cryo/runs/seed-{seed}','--cache','/workspace/cryo/cache/boltz','--accelerator','gpu','--devices','1','--recycling_steps','3','--sampling_steps','200','--diffusion_samples','1','--sampling_steps_affinity','200','--diffusion_samples_affinity','5','--max_msa_seqs','512','--num_workers','1','--no_kernels','--seed',str(seed)]
        if c.get('command')!=expected_cmd: errors.append(f'seed {seed}: command mismatch')
        if c.get('status')!='completed' or c.get('returncode')!=0: errors.append(f'seed {seed}: incomplete execution')
        comps=c.get('output_validation',{}).get('compound_outputs',[])
        if c.get('output_validation',{}).get('all_expected_outputs_valid') is not True: errors.append(f'seed {seed}: runtime output validation failed')
        if len(comps)!=len(expected) or {x['id'] for x in comps}!=expected: errors.append(f'seed {seed}: missing or duplicate compound identities')
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
    dataset=read(ROOT/ev['dataset_path']); base={r['molecule_id']:r for r in dataset['exact_compounds']}
    if set(base)!=expected: errors.append('experimental dataset identity set mismatch')
    cal_ids=set(dataset['split']['calibration_ids']); test_ids=set(dataset['split']['test_ids'])
    if cal_ids & test_ids or cal_ids | test_ids!=expected: errors.append('invalid calibration/test partition')
    if {base[i]['scaffold'] for i in cal_ids}&{base[i]['scaffold'] for i in test_ids}: errors.append('scaffold leakage between calibration/test')
    for ident in sorted(expected):
        vals=predictions[ident]
        if len(vals)!=2 or [v['seed'] for v in vals]!=seeds:
            errors.append('incomplete repeated predictions: '+ident);continue
        values=[v['pIC50'] for v in vals]
        panel.append({**base[ident],'split':'calibration' if ident in cal_ids else 'test',
                      'panel_seed_pIC50':values,'panel_mean_pIC50':float(np.mean(values)),
                      'seed_absolute_difference_pIC50':abs(values[0]-values[1]),
                      'binder_probabilities':[v['binder_probability'] for v in vals]})
    analysis=analyze(panel,dataset,ev) if not errors else None
    result={'attempt':attempt,'plan_id':plan['id'],'plan_sha256':sha(planfile),
            'verdict':analysis['screening_decision'] if analysis else 'inconclusive',
            'validation_errors':errors,'archive_hash_verified':archive_ok,
            'analysis':analysis,'seeds':telemetry,'panel_predictions':panel,'limits':plan['limits']}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result

def score(y,pred,baseline):
    y=np.asarray(y,dtype=float); pred=np.asarray(pred,dtype=float); baseline=np.asarray(baseline,dtype=float)
    if len(y)==0 or len(y)!=len(pred) or len(y)!=len(baseline) or not all(np.isfinite(a).all() for a in [y,pred,baseline]): raise ValueError('Invalid scoring arrays')
    err=pred-y;mae=float(np.mean(abs(err)));bmae=float(np.mean(abs(baseline-y)))
    slope=float(np.cov(pred,y,ddof=0)[0,1]/np.var(pred)) if len(pred)>1 and np.var(pred)>1e-20 else None
    intercept=float(np.mean(y)-slope*np.mean(pred)) if slope is not None else None
    return {'n':len(y),'mae_pIC50':mae,'rmse_pIC50':float(np.sqrt(np.mean(err**2))),'bias_pIC50':float(np.mean(err)),
            'baseline_mae_pIC50':bmae,'mae_improvement_fraction':1-mae/bmae if bmae>0 else None,
            'spearman':spearman(pred.tolist(),y.tolist()),'pearson':float(np.corrcoef(pred,y)[0,1]) if len(y)>1 and np.var(pred)>1e-20 and np.var(y)>1e-20 else None,
            'observed_on_predicted_slope':slope,'observed_on_predicted_intercept':intercept,
            'fraction_within_0_5':float(np.mean(abs(err)<=.5)),'fraction_within_1_0':float(np.mean(abs(err)<=1)),
            'maximum_absolute_error_pIC50':float(max(abs(err)))}

def summarize(rows,key,constant):
    return score([r['observed_pIC50'] for r in rows],[r[key] for r in rows],[constant]*len(rows))

def bootstrap_metrics(rows,key,constant,n,seed):
    groups={}
    for row in rows:groups.setdefault(row['scaffold'],[]).append(row)
    keys=sorted(groups);rng=np.random.default_rng(seed); draws={k:[] for k in ['mae_pIC50','bias_pIC50','mae_improvement_fraction','spearman']}
    for _ in range(n):
        sample=[r for k in rng.choice(keys,len(keys),replace=True) for r in groups[k]]
        m=summarize(sample,key,constant)
        for k in draws:
            if finite(m[k]):draws[k].append(m[k])
    return {'clusters':len(keys),'resamples':n,'seed':seed,'percentiles':[2.5,50,97.5],
            'intervals':{k:np.percentile(v,[2.5,50,97.5]).tolist() if v else None for k,v in draws.items()},
            'finite_resamples':{k:len(v) for k,v in draws.items()},
            'interpretation':'Descriptive paired scaffold resampling conditional on fitted offsets; excludes calibration fitting uncertainty and pretrained-data uncertainty.'}

def analyze(rows,dataset,ev):
    cal=[r for r in rows if r['split']=='calibration']; test=[r for r in rows if r['split']=='test']
    if len(cal)<6 or len(test)<10: raise ValueError('Insufficient prespecified calibration/test rows')
    offset=float(np.median([r['observed_pIC50']-r['panel_mean_pIC50'] for r in cal]))
    calmean=float(np.mean([r['observed_pIC50'] for r in cal]))
    source=dataset['source_constants']
    for r in rows:
        r['source_calibrated_pIC50']=r['panel_mean_pIC50']+source['source_median_residual_offset_pIC50']
        r['assay_calibrated_pIC50']=r['panel_mean_pIC50']+offset
    full={label:summarize(rows,key,source['source_mean_pIC50']) for label,key in [('raw','panel_mean_pIC50'),('source_calibrated','source_calibrated_pIC50')]}
    heldout={label:summarize(test,key,calmean) for label,key in [('raw','panel_mean_pIC50'),('source_calibrated','source_calibrated_pIC50'),('assay_calibrated','assay_calibrated_pIC50')]}
    primary=full['raw'];primary_pass=(finite(primary['mae_improvement_fraction']) and primary['mae_improvement_fraction']>=ev['minimum_mae_improvement_fraction'] and finite(primary['spearman']) and primary['spearman']>=ev['minimum_spearman'])
    gate=ev['calibration_gate'];m=heldout['assay_calibrated']
    checks={'mae_at_most_limit':m['mae_pIC50']<=gate['maximum_heldout_mae_pIC50'],
            'absolute_bias_at_most_limit':abs(m['bias_pIC50'])<=gate['maximum_absolute_heldout_bias_pIC50'],
            'improvement_vs_calibration_mean':finite(m['mae_improvement_fraction']) and m['mae_improvement_fraction']>=gate['minimum_mae_improvement_vs_calibration_mean'],
            'rank_correlation':finite(m['spearman']) and m['spearman']>=gate['minimum_spearman'],
            'no_worse_than_raw':m['mae_pIC50']<=heldout['raw']['mae_pIC50']}
    calibrated_pass=all(checks.values())
    intervals={'full_raw':bootstrap_metrics(rows,'panel_mean_pIC50',source['source_mean_pIC50'],ev['bootstrap_samples'],ev['bootstrap_seed']),
               'heldout_assay_calibrated':bootstrap_metrics(test,'assay_calibrated_pIC50',calmean,ev['bootstrap_samples'],ev['bootstrap_seed']+1)}
    return {'full_orthogonal':full,'heldout_orthogonal':heldout,'source_constants':source,
            'calibration_fit':{'n':len(cal),'molecule_ids':sorted(r['molecule_id'] for r in cal),'method':'Add median(observed-predicted) on calibration subset only','offset_pIC50':offset,'calibration_mean_pIC50':calmean},
            'primary_transfer_passed':primary_pass,'calibration_checks':checks,'calibration_gate_passed':calibrated_pass,
            'screening_decision':'provisional_prioritization_gate_passed' if primary_pass and calibrated_pass else 'novel_screening_not_qualified',
            'bootstrap':intervals,'median_seed_absolute_difference_pIC50':float(np.median([r['seed_absolute_difference_pIC50'] for r in rows])),
            'warning':'Calibration-set fit is not scored as evidence of generalization. No fitted scale/slope or best-offset selection. The diagnostic regression on test outputs is descriptive, not a deployable calibrator.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',type=int,default=1);p.add_argument('--output',type=Path,default=ROOT/'data/phase19/orthogonal-results.json');a=p.parse_args()
    result=check(a.attempt,a.output);print(json.dumps({'verdict':result['verdict'],'errors':len(result['validation_errors'])}));return int(bool(result['validation_errors']))
if __name__=='__main__':raise SystemExit(main())
