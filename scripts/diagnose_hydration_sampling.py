"""Post hoc finite-sampling diagnostics; never replace prespecified flags."""
import json
from pathlib import Path
import numpy as np
try:
    from .analyze_hydration_stability import sha, write_json, write_report
except ImportError:
    from analyze_hydration_stability import sha, write_json, write_report

ROOT=Path(__file__).resolve().parents[1]


def main():
    source=ROOT/'data/phase11/stability-results.json'
    result=json.loads(source.read_text()); rng=np.random.default_rng(20260929); rows=[]
    for row in result['runs']:
        trajectory=ROOT/'data/raw/phase11/runpod/runs'/row['name']/'trajectory.npz'
        if sha(trajectory)!=row['source_trajectory_sha256']: raise ValueError('Trajectory changed')
        with np.load(trajectory) as d: pdf=d['nearest_pdf']
        blocks=pdf.reshape(30,10,100).mean(axis=1)
        values=[]
        for _ in range(1000):
            order=rng.permutation(30)
            values.append(float(.5*np.abs(blocks[order[:10]].mean(axis=0)-blocks[order[20:]].mean(axis=0)).sum()*.005))
        observed=row['first_last_pdf_tv']; quantiles=np.quantile(values,[.05,.5,.95])
        coarse=pdf.reshape(300,20,5).mean(axis=2)
        coarse_tv=float(.5*np.abs(coarse[:100].mean(axis=0)-coarse[200:].mean(axis=0)).sum()*.025)
        if coarse_tv>observed+1e-10: raise ValueError('Coarsening unexpectedly increased TV')
        rows.append({'run':row['name'],'chronological_1ns_blocks_tv':observed,
            'random_100ps_block_mixing_tv_quantiles_05_50_95':quantiles.tolist(),
            'fraction_mixed_tv_ge_observed':float(np.mean(np.array(values)>=observed)),
            'chronological_tv_within_mixed_05_95':bool(quantiles[0]<=observed<=quantiles[-1]),
            'posthoc_20bin_tv':coarse_tv})
    output={'status':'Post hoc diagnostic after observing all 12 fine-histogram flags; no new MD or revised primary gate',
        'source_results_sha256':sha(source),'script_sha256':sha(__file__),'numpy_version':np.__version__,
        'random_seed':20260929,'permutations_per_run':1000,'block_length_ps':100,
        'procedure':'Group 300 frames into 30 consecutive 100 ps blocks. Randomly permute blocks; compare equal-weight PDFs from disjoint sets of 10 blocks each, omitting the middle 10. Preserve within-block dependence, break longer dependence.',
        'within_mixed_05_95_count':sum(r['chronological_tv_within_mixed_05_95'] for r in rows),'runs':rows,
        'limits':['Block exchangeability and a 100 ps dependence scale are assumptions, not established by this diagnostic.',
            'Tail fractions are descriptive, not calibrated p-values; no multiple-testing or formal stationarity claim.',
            'Coarsening bins cannot increase TV, so smaller 20-bin values are not evidence of convergence or better activity prediction.',
            'The 0.05 fine-histogram gate and all 12 original flags remain unchanged. More effective samples or prespecified resolution calibration is needed before screening.']}
    write_json(ROOT/'data/phase11/sampling-diagnostics.json',output)
    write_report(result)
    print(json.dumps({'posthoc_only':True,'within_mixed_05_95_count':output['within_mixed_05_95_count'],'primary_flags_retained':result['flagged_runs']}))


if __name__=='__main__':main()
