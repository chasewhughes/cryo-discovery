"""Render saved retrospective benchmark predictions; never launches inference."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
def main():
    result=json.loads((ROOT/'data/phase17/panel-results.json').read_text())
    if result['validation_errors']: raise ValueError('Do not plot an incomplete benchmark as validated')
    rows=result['panel_predictions']; y=np.array([r['observed_pIC50'] for r in rows]); pred=np.array([r['panel_mean_pIC50'] for r in rows]); seeds=np.array([r['panel_seed_pIC50'] for r in rows]); anchor=np.array([r['molecule_id']=='CHEMBL4522042' for r in rows])
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(10,4.6),layout='constrained')
    for ax,x,z,title,xlabel,ylabel in [(axes[0],y,pred,'Measured potency versus model','Measured pIC50','Mean model pIC50-equivalent'),(axes[1],seeds[:,0],seeds[:,1],'Sensitivity to random seed','Seed 1701 pIC50-equivalent','Seed 1702 pIC50-equivalent')]:
        low=min(x.min(),z.min())-.25;high=max(x.max(),z.max())+.25
        ax.plot([low,high],[low,high],color='#87939e',linestyle='--',linewidth=1,label='Equality')
        ax.scatter(x[~anchor],z[~anchor],s=34,color='#245985',alpha=.8,edgecolor='white',linewidth=.4)
        ax.scatter(x[anchor],z[anchor],s=65,color='#bd6b18',marker='D',edgecolor='white',linewidth=.5,label='6ED6 reference ligand')
        ax.set(xlim=(low,high),ylim=(low,high),title=title,xlabel=xlabel,ylabel=ylabel);ax.grid(alpha=.15);ax.set_aspect('equal')
    axes[0].legend(loc='upper left',fontsize=8,frameon=False)
    fig.suptitle('ROCK2: 43 known compounds, two Boltz-2 seeds',fontsize=14)
    out=ROOT/'reports/figures';out.mkdir(exist_ok=True)
    fig.savefig(out/'rock2-panel-benchmark.png',dpi=180,facecolor='white')
    fig.savefig(out/'rock2-panel-benchmark.svg',facecolor='white');plt.close(fig)
    svg=out/'rock2-panel-benchmark.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    print('Saved benchmark figures')
if __name__=='__main__':main()
