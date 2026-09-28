"""Supplemental uncertainty diagnostic; never changes frozen point gates or calibrator."""
import hashlib,json
from pathlib import Path
import numpy as np
from analyze_rock_scaffold import score
ROOT=Path(__file__).resolve().parents[1]
def groups(rows):
    out={}
    for r in rows:out.setdefault(r['scaffold'],[]).append(r)
    return out

def diagnostic(rows,n=2000,seed=2105):
    cal=[r for r in rows if r['split']=='calibration'];test=[r for r in rows if r['split']=='test']
    cg=groups(cal);tg=groups(test);rng=np.random.default_rng(seed)
    def fit(rr):return float(np.median([r['observed_pIC50']-r['panel_mean_pIC50'] for r in rr]))
    def metrics(cc,tt):
        off=fit(cc);m=score([r['observed_pIC50'] for r in tt],[r['panel_mean_pIC50']+off for r in tt],[float(np.mean([r['observed_pIC50'] for r in cc]))]*len(tt))
        return {'offset_pIC50':off,**{k:m[k] for k in ('mae_pIC50','bias_pIC50','mae_improvement_fraction','spearman')}}
    draws={k:[] for k in metrics(cal,test)}
    for _ in range(n):
        cc=[r for g in rng.choice(sorted(cg),len(cg),replace=True) for r in cg[g]]
        tt=[r for g in rng.choice(sorted(tg),len(tg),replace=True) for r in tg[g]]
        for k,v in metrics(cc,tt).items():
            if v is not None and np.isfinite(v):draws[k].append(v)
    loo=[]
    for g in sorted(cg):
        cc=[r for r in cal if r['scaffold']!=g]
        loo.append({'omitted_scaffold':g,'omitted_n':len(cg[g]),'remaining_calibration_n':len(cc),'offset_pIC50':fit(cc),'offset_change_from_frozen_fit':fit(cc)-fit(cal)})
    return {'bootstrap_seed':seed,'resamples':n,'calibration_clusters':len(cg),'test_clusters':len(tg),'percentiles':[2.5,50,97.5],'joint_resampling_intervals':{k:np.percentile(v,[2.5,50,97.5]).tolist() if v else None for k,v in draws.items()},'finite_resamples':{k:len(v) for k,v in draws.items()},'leave_one_calibration_scaffold_out':loo,'limits':['Supplemental sensitivity diagnostic, not a replacement decision rule or a fitted production calibrator.','Resampling only three calibration clusters gives coarse uncertainty; exchangeability across related scaffold groups is unproven.','Omitting dominant calibration group leaves only two compounds; that offset is a sensitivity calculation, not an eligible alternative calibrator.','No training-overlap or experimental-replicate uncertainty included.']}

def main():
    policy=json.loads((ROOT/'data/phase21/uncertainty-supplement-plan.json').read_text())
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=policy['script_sha256']:raise ValueError('Supplement code differs from recorded plan')
    path=ROOT/'data/phase21/scaffold-results.json';r=json.loads(path.read_text())
    if r['validation_errors'] or not r['analysis']:raise ValueError('Complete verified result required')
    out=diagnostic(r['panel_predictions'],policy['resamples'],policy['seed']);out['result_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();out['primary_gate_unchanged']=r['verdict']
    (ROOT/'data/phase21/calibration-fit-uncertainty.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print(json.dumps(out['joint_resampling_intervals']))
if __name__=='__main__':main()
