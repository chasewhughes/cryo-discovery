"""Exploratory paired-readout diagnostic; never qualifies novel screening."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def assemble(source,reconciliation,predictions):
    mapping={r['source_compound_number']:r for r in reconciliation['reconciled_rows']}
    pred={r['molecule_id']:r for r in predictions['panel_predictions']}
    if predictions['validation_errors'] or predictions['archive_hash_verified'] is not True:raise ValueError('Prior predictions unverified')
    rows=[];excluded=[]
    for r in source['rows']:
        n=r['source_compound_number'];m=mapping.get(n)
        if not m:excluded.append({**r,'reason':'No source-verified Phase18 identity/prediction'});continue
        if r['luciferase_relation']!='=' or r['IMAP_relation']!='=':excluded.append({**r,'reason':'Censored endpoint; not an exact paired observation'});continue
        if m['corrected_value_nM']!=r['luciferase_nM']:raise ValueError('Primary luciferase value mismatch')
        p=pred.get(m['molecule_chembl_id'])
        if not p or p['canonical_smiles']!=m['canonical_smiles']:raise ValueError('Missing/mismatched prior prediction identity')
        if p['observed_nM']!=r['luciferase_nM']:raise ValueError('Prior experimental label mismatch')
        rows.append({**r,'molecule_id':p['molecule_id'],'scaffold':p['scaffold'],'prior_split':p['split'],'predicted_pIC50':p['panel_mean_pIC50'],'luciferase_pIC50':9-math.log10(r['luciferase_nM']),'IMAP_pIC50':9-math.log10(r['IMAP_nM']),'IMAP_to_luciferase_IC50_ratio':r['IMAP_nM']/r['luciferase_nM']})
    return rows,excluded

def metrics(y,p):
    y=np.asarray(y);p=np.asarray(p);e=p-y
    return {'n':len(y),'MAE_pIC50':float(np.mean(abs(e))),'bias_pIC50':float(np.mean(e)),'RMSE_pIC50':float(np.sqrt(np.mean(e*e))),'spearman':float(spearmanr(y,p).statistic) if len(set(y))>1 and len(set(p))>1 else None}
def main():
    paths=['data/phase19/morwick-imap-source.json','data/phase18/source-table-reconciliation.json','data/phase18/external-results.json','data/phase18/external-dataset.json']
    source,recon,pred,dataset=[read(ROOT/p) for p in paths]
    if sha(ROOT/source['source_path'])!=source['source_sha256']:raise ValueError('SI source digest mismatch')
    rows,excluded=assemble(source,recon,pred)
    offset=dataset['source_constants']['source_median_residual_offset_pIC50']
    p=np.array([r['predicted_pIC50'] for r in rows]);l=np.array([r['luciferase_pIC50'] for r in rows]);i=np.array([r['IMAP_pIC50'] for r in rows])
    result={'scope':source['scope'],'screening_decision':'novel_screening_not_qualified','independent_validation':False,'new_GPU_cost_usd':0,'new_calibration_fitted':False,'source_sha256':{x:sha(ROOT/x) for x in paths},'source_only_offset_pIC50':offset,'paired_exact_n':len(rows),'excluded_n':len(excluded),'experimental_readout_spearman':float(spearmanr(l,i).statistic),'median_IMAP_to_luciferase_IC50_ratio':float(np.median([r['IMAP_to_luciferase_IC50_ratio'] for r in rows])),'median_IMAP_minus_luciferase_pIC50':float(np.median(i-l)),'raw_luciferase':metrics(l,p),'raw_IMAP':metrics(i,p),'source_offset_luciferase':metrics(l,p+offset),'source_offset_IMAP':metrics(i,p+offset),'rows':rows,'excluded_rows':excluded,'limits':source['limits']}
    (ROOT/'data/phase19/imap-diagnostic-results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['rows','excluded_rows','source_sha256','limits']}))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10})
    fig,ax=plt.subplots(1,2,figsize=(10.5,4.6))
    ax[0].scatter(l,i,color='#276b84');ax[0].plot([5.5,8.5],[5.5,8.5],color='gray',linestyle='--');ax[0].set(xlabel='Luciferase observed pIC50',ylabel='IMAP observed pIC50',title=f'Paired experimental readouts (n={len(rows)})')
    for r in rows:
        ax[1].plot([r['luciferase_pIC50'],r['IMAP_pIC50']],[r['predicted_pIC50']]*2,color='#c1c7cd',zorder=1)
    ax[1].scatter(l,p,label='Luciferase',color='#b67826');ax[1].scatter(i,p,label='IMAP',color='#276b84');ax[1].plot([5.5,8.5],[5.5,8.5],color='gray',linestyle='--');ax[1].set(xlabel='Observed pIC50',ylabel='Unchanged model prediction',title='Same predictions, different assay labels');ax[1].legend()
    for a in ax:a.set_xlim(5.5,8.5);a.set_ylim(5.5,8.5);a.grid(alpha=.15)
    fig.suptitle('Exploratory assay sensitivity — reused Phase18 compounds',fontsize=13)
    fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(ROOT/f'reports/figures/rock2-imap-diagnostic.{ext}',dpi=170)
    svg=ROOT/'reports/figures/rock2-imap-diagnostic.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
if __name__=='__main__':main()
