#!/usr/bin/env python3
"""Render static ROCK2 external benchmark figures from verified results."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
def clean_svg(p):
 p.write_text('\n'.join(x.rstrip() for x in p.read_text().splitlines())+'\n')
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--input',type=Path,default=ROOT/'data/phase18/external-results.json'); ap.add_argument('--output-dir',type=Path,default=ROOT/'reports/figures'); a=ap.parse_args(); result=json.loads(a.input.read_text())
 if result.get('validation_errors'): raise SystemExit('Refusing to plot results with validation_errors')
 rows=result.get('panel_predictions',[]); cal=[r for r in rows if r.get('split')=='calibration']; test=[r for r in rows if r.get('split')=='test']
 if len(rows)!=30 or len(cal)!=12 or len(test)!=18: raise SystemExit(f'Expected 12 calibration and 18 heldout rows, got {len(cal)} and {len(test)}')
 a.output_dir.mkdir(parents=True,exist_ok=True)
 lo=min(min(r['observed_pIC50'],r['panel_mean_pIC50']) for r in rows); hi=max(max(r['observed_pIC50'],r['panel_mean_pIC50']) for r in rows)
 fig,ax=plt.subplots(figsize=(7.2,5.4),dpi=180); ax.scatter([r['observed_pIC50'] for r in cal],[r['panel_mean_pIC50'] for r in cal],s=30,alpha=.75,label='Calibration (n=12)'); ax.scatter([r['observed_pIC50'] for r in test],[r['panel_mean_pIC50'] for r in test],s=30,alpha=.75,marker='s',label='Heldout (n=18)'); ax.plot([lo,hi],[lo,hi],color='0.3',lw=1); ax.set(xlabel='Observed pIC50',ylabel='Raw model pIC50-equivalent',title='ROCK2 external panel'); ax.legend(frameon=False); fig.tight_layout(); fig.savefig(a.output_dir/'rock2-external-calibration.png'); fig.savefig(a.output_dir/'rock2-external-calibration.svg'); plt.close(fig); clean_svg(a.output_dir/'rock2-external-calibration.svg')
 labels=['Raw model','Source offset','Assay calibration']; metrics=result.get('analysis',{}).get('heldout_external',{}); vals=[metrics.get('raw',{}).get('mae_pIC50'),metrics.get('source_calibrated',{}).get('mae_pIC50'),metrics.get('assay_calibrated',{}).get('mae_pIC50')]
 if any(v is None for v in vals): raise SystemExit('Missing heldout metric for comparison figure')
 all_pred=[r['panel_mean_pIC50'] for r in test]+[r['assay_calibrated_pIC50'] for r in test]; lo2=min([r['observed_pIC50'] for r in test]+all_pred); hi2=max([r['observed_pIC50'] for r in test]+all_pred); fig,axs=plt.subplots(1,2,figsize=(11,4.8),dpi=180); axs[0].scatter([r['observed_pIC50'] for r in test],[r['panel_mean_pIC50'] for r in test],s=30,alpha=.75); pred=[r['assay_calibrated_pIC50'] for r in test]; axs[1].scatter([r['observed_pIC50'] for r in test],pred,s=30,alpha=.75,color='tab:orange');
 for ax in axs: ax.set_xlim(lo2-.15,hi2+.15); ax.set_ylim(lo2-.15,hi2+.15); ax.plot([lo2,hi2],[lo2,hi2],color='0.3',lw=1); ax.set(xlabel='Observed pIC50',ylabel='Predicted pIC50-equivalent');
 axs[0].set_title('Heldout (n=18): raw model'); axs[1].set_title('Heldout (n=18): assay-calibrated'); fig.tight_layout(); fig.savefig(a.output_dir/'rock2-external-heldout.png'); fig.savefig(a.output_dir/'rock2-external-heldout.svg'); plt.close(fig); clean_svg(a.output_dir/'rock2-external-heldout.svg')
 labels.append('Calibration mean'); vals.append(metrics['raw']['baseline_mae_pIC50'])
 fig,ax=plt.subplots(figsize=(8,4.6),dpi=180); bars=ax.bar(labels,vals,color=['0.45','0.65','tab:orange','tab:blue']); ax.bar_label(bars,fmt='%.3f',padding=4); ax.set_ylim(0,max(vals)*1.12); ax.set_ylabel('Heldout MAE (pIC50)'); ax.set_title('Heldout error comparison (n=18)'); fig.tight_layout(); fig.savefig(a.output_dir/'rock2-external-error-comparison.png'); fig.savefig(a.output_dir/'rock2-external-error-comparison.svg'); plt.close(fig); clean_svg(a.output_dir/'rock2-external-error-comparison.svg')
if __name__=='__main__': main()
