"""Offline engineering calibration on Phase 11; preserves original descriptor/gate."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
GRID = {'bins': [20, 50, 100], 'block_ps': [100, 250, 500],
        'endpoint_window_ps': [500, 1000, 1500], 'permutations': 1000,
        'random_seed': 20261005, 'frame_interval_ps': 10}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')

def tv(a, b, bins=100):
    return float(.5*np.abs(np.asarray(a)-np.asarray(b)).sum()*.5/bins)

def coarsen(pdf, bins):
    if pdf.shape[-1] != 100 or 100 % bins:
        raise ValueError('Expected a divisor of 100 bins')
    return pdf.reshape(*pdf.shape[:-1], bins, 100//bins).mean(axis=-1)

def diagnose(pdf, grid=GRID):
    if pdf.shape != (300, 100) or not np.isfinite(pdf).all() or np.any(pdf < 0):
        raise ValueError('Expected 300 finite nonnegative PDFs')
    if not np.allclose(pdf.sum(axis=1)*.005, 1, atol=1e-10):
        raise ValueError('Invalid normalization')
    # Same deterministic permutations for each trajectory and resolution.
    rows=[]
    for bins in grid['bins']:
        coarse=coarsen(pdf, bins)
        for duration in grid['endpoint_window_ps']:
            n=duration//10
            observed=tv(coarse[:n].mean(axis=0), coarse[-n:].mean(axis=0), bins)
            fine=tv(pdf[:n].mean(axis=0), pdf[-n:].mean(axis=0))
            if observed>fine+1e-12: raise ValueError('Coarsening increased TV')
            for block_ps in grid['block_ps']:
                k=block_ps//10
                if n%k or 300%k: raise ValueError('Unequal block weighting')
                blocks=coarse.reshape(300//k,k,bins).mean(axis=1)
                rng=np.random.default_rng(grid['random_seed'])
                values=[]
                for _ in range(grid['permutations']):
                    order=rng.permutation(len(blocks)); m=n//k
                    values.append(tv(blocks[order[:m]].mean(axis=0),blocks[order[-m:]].mean(axis=0),bins))
                q=np.quantile(values,[.05,.5,.95])
                rows.append({'bins':bins,'endpoint_window_ps':duration,'block_ps':block_ps,
                             'observed_tv':observed,'mixed_tv_quantiles_05_50_95':q.tolist(),
                             'fraction_mixed_tv_ge_observed':float(np.mean(np.asarray(values)>=observed))})
    return rows

def main():
    source=ROOT/'data/phase11/stability-results.json'
    prior=json.loads(source.read_text()); rows=[]
    for row in prior['runs']:
        path=ROOT/'data/raw/phase11/runpod/runs'/row['name']/'trajectory.npz'
        if sha(path)!=row['source_trajectory_sha256']: raise ValueError('Parent trajectory changed')
        with np.load(path) as d: diagnostics=diagnose(d['nearest_pdf'])
        rows.append({'name':row['name'],'source_trajectory_sha256':sha(path),'diagnostics':diagnostics})
    result={'status':'Exploratory offline engineering calibration; no revised pass criterion',
            'grid':GRID,'source_results_sha256':sha(source),'script_sha256':sha(__file__),
            'runs':rows,'interpretation':[
                'Endpoint windows compare first and last equal-duration portions of the same 3 ns trajectory.',
                'Block mixing gives descriptive finite-sampling references, not p-values or a stationarity test.',
                'Exchangeability and every tested dependence scale remain assumptions.',
                'Coarsening mechanically cannot increase TV; it does not establish convergence.',
                'All original 100-bin TV > 0.05 flags are retained; no fitted efficacy model.']}
    write(ROOT/'data/phase12/offline-calibration.json',result)
    table=[]
    for bins in GRID['bins']:
        for duration in GRID['endpoint_window_ps']:
            vals=[next(d['observed_tv'] for d in r['diagnostics'] if d['bins']==bins and d['endpoint_window_ps']==duration) for r in rows]
            table.append(f'| {bins} | {duration/1000:g} | {min(vals):.4f}–{max(vals):.4f} | {sum(v>.05 for v in vals)}/12 |')
    report='''# Hydration sampling calibration

This analysis reuses the twelve Phase 11 trajectories. It is an engineering
calibration informed by the observed Phase 11 flags, not independent validation.
The primary 100-bin descriptor and TV > 0.05 threshold remain unchanged.

| Bins | Each endpoint window (ns) | TV range across runs | Above 0.05 |
| --- | --- | --- | --- |
'''+ '\n'.join(table)+'''

The complete 20/50/100-bin, 100/250/500-ps block, and 0.5/1/1.5-ns endpoint
grid is preserved in `data/phase12/offline-calibration.json`, including every
trajectory and 1,000 block permutations per combination. Mixing compares
disjoint groups of equal duration, retaining within-block ordering and equal
frame weighting. Tail fractions are descriptive; exchangeability and the
dependence scale are unestablished. Fewer bins necessarily reduce or preserve
TV, so a lower coarse-bin value is not evidence of convergence.

The follow-up retains 100 bins and compares the first and second 5 ns of each
new 10-ns branch. Five 2-ns windows and all three block scales are secondary
diagnostics. Two NVT parents were selected because their Phase 11 chronological
TV exceeded the post hoc 100-ps mixing envelope; their matched NPT parents are
included. These selected branches share starting-state history with Phase 11.
They are not independent starting conformations, and old and new production
segments will not be pooled. This study measures sampling stability only.
'''
    (ROOT/'reports/hydration-sampling-calibration.md').write_text(report)
    print(json.dumps({'runs':len(rows),'combinations_per_run':len(rows[0]['diagnostics'])}))

if __name__=='__main__': main()
