"""Summarize independent MD seeds without treating trajectory frames as replicates."""
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def definition_diagnostics(path):
    """Post hoc alternatives motivated by the initial descriptor discrepancy.

    Radial variants are rescaled to integrate to one for this shape comparison;
    they are not the original dimensionless HIN pair-correlation output.
    """
    bins=np.arange(100)*.005+.0025
    values={'nearest_pdf':[], 'pair_radial_renormalized':[], 'nearest_radial_renormalized':[]}
    with np.load(path) as d:
        for xyz,box in zip(d['positions_nm'],d['boxes_nm']):
            lengths=np.diag(box)
            if not np.allclose(box,np.diag(lengths)):raise ValueError('Nonorthorhombic box')
            delta=xyz[d['water_oxygen_indices'],None,:]-xyz[None,d['solute_indices'],:]
            delta-=lengths*np.rint(delta/lengths)
            distances=np.linalg.norm(delta,axis=2)
            pair,_=np.histogram(distances,bins=100,range=(0,.5))
            nearest,_=np.histogram(distances.min(axis=1),bins=100,range=(0,.5))
            for name,hist in {'nearest_pdf':nearest,'pair_radial_renormalized':pair/bins**2,'nearest_radial_renormalized':nearest/bins**2}.items():
                values[name].append(hist/(hist.sum()*.005))
    return {name:np.mean(v,axis=0) for name,v in values.items()}


def main():
    raw = ROOT/'data/raw/phase10/runpod/runs'
    files = sorted(raw.glob('*-2026090*/result.json'))
    if len(files)!=6: raise ValueError('Expected all six prespecified replicate results')
    with (ROOT/'data/raw/phase8/dolmen/data/descriptors/hydhist_amino.csv').open() as f:
        reader=csv.DictReader(f)
        bins=np.array([float(x) for x in reader.fieldnames[1:]])
        source={r['Name'].casefold():np.array([float(r[k]) for k in reader.fieldnames[1:]]) for r in reader}
    if len(bins)!=100 or not np.allclose(bins,np.arange(100)*.005+.0025):
        raise ValueError('Unexpected source histogram bins')
    inputs=[]; groups={}
    for path in files:
        r=json.loads(path.read_text())
        if r['hashes']['script']!=sha(ROOT/'scripts/run_hydration_pilot.py') or r['hashes']['water_xml']!=sha(ROOT/'simulation/tip4p-ice.xml'):
            raise ValueError('Simulation source changed after the run')
        if r['hashes']['trajectory']!=sha(path.parent/'trajectory.npz'):
            raise ValueError('Trajectory hash mismatch')
        if r['configuration']['production_ps']!=1000 or r['configuration']['frames']!=100:
            raise ValueError('Unexpected trajectory duration/frames')
        r['posthoc_definitions']=definition_diagnostics(path.parent/'trajectory.npz')
        inputs.append({'local_path':str(path.relative_to(ROOT)),'sha256':sha(path)})
        groups.setdefault(r['control']['name'],[]).append(r)
    if set(groups)!={'l-phenylalanine','l-glycine'}: raise ValueError('Unexpected controls')
    results={}
    fig,axs=plt.subplots(1,2,figsize=(11,4.7),sharey=True)
    colors=['#2563a6','#2563a6']
    for ax,(name,rows),color in zip(axs,sorted(groups.items()),colors):
        if sorted(r['seed'] for r in rows)!=[20260906,20260907,20260908]:raise ValueError('Unexpected seeds')
        means=np.array([r['observables']['mean_hydration_counts'] for r in rows])
        hist=np.array([r['observables']['mean_pair_histogram_density'] for r in rows])
        old=source[name]
        if not np.allclose(hist.sum(axis=1)*.005,1) or not np.isclose(old.sum()*.005,1,atol=.01):
            raise ValueError('Histogram normalization mismatch')
        temp=[r['observables']['mean_temperature_K'] for r in rows]
        alternatives={k:np.array([r['posthoc_definitions'][k] for r in rows]) for k in rows[0]['posthoc_definitions']}
        if not np.isfinite(means).all() or not all(250<t<295 for t in temp):
            raise ValueError('Numerical/temperature diagnostic failed')
        results[name]={
            'n_seeds':3,'cutoffs_nm':rows[0]['observables']['cutoffs_nm'],
            'hydration_count_mean_across_seeds':means.mean(axis=0).tolist(),
            'hydration_count_seed_sd':means.std(axis=0,ddof=1).tolist(),
            'hydration_count_seed_means':means.tolist(),
            'hydration_per_mw_mean':np.mean([r['observables']['mean_hydration_per_molecular_weight'] for r in rows],axis=0).tolist(),
            'mean_histogram_density':hist.mean(axis=0).tolist(),
            'source_histogram_total_variation':float(.5*np.abs(hist.mean(axis=0)-old).sum()*.005),
            'posthoc_definition_comparisons':{k:{'mean_density':v.mean(axis=0).tolist(),
                'source_total_variation':float(.5*np.abs(v.mean(axis=0)-old).sum()*.005)} for k,v in alternatives.items()},
            'replicate_temperature_means_K':temp,
            'replicate_density_g_ml':[r['configuration']['density_g_ml'] for r in rows],
            'replicate_ns_per_day':[r['timing']['production_ns_per_day'] for r in rows],
            'replicate_max_first_to_last_block_count_change':[float(np.max(np.abs(np.array(r['observables']['four_time_block_means'])[-1]-np.array(r['observables']['four_time_block_means'])[0]))) for r in rows],
            'provenance':[{'seed':r['seed'],'versions':r['versions'],'configuration':r['configuration'],'hashes':r['hashes']} for r in rows]}
        ax.plot(bins,old,color='#656565',linestyle='--',label='Published descriptor')
        ax.plot(bins,hist.mean(axis=0),color=color,label='All-pairs PDF (primary)')
        ax.fill_between(bins,hist.min(axis=0),hist.max(axis=0),color=color,alpha=.18)
        near=alternatives['nearest_pdf']
        ax.plot(bins,near.mean(axis=0),color='#9c477b',label='Nearest-water PDF (post hoc)')
        ax.fill_between(bins,near.min(axis=0),near.max(axis=0),color='#9c477b',alpha=.13,label='Bands: range across 3 seeds')
        ax.set_title('Glycine' if name=='l-glycine' else 'L-phenylalanine'); ax.set_xlabel('Water O–solute distance (nm)')
        ax.set_xlim(.1,.5); ax.set_ylim(0,9.2); ax.spines[['top','right']].set_visible(False)
    axs[0].set_ylabel('Distance probability density (nm⁻¹)')
    axs[1].legend(frameon=False,fontsize=8,loc='upper left')
    fig.suptitle('Hydration descriptor definition check: liquid water at 273 K',fontsize=15)
    fig.text(.5,.025,'3 × 1 ns per compound • Different molecular sizes • No ice-growth or cell-survival validation',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.06,1,.94))
    fig.savefig(ROOT/'reports/hydration-pilot.png',dpi=180)
    output={'status':'Short reconstructed MD pilot; descriptive comparison, not independent experimental validation',
        'experimental_rows_added':0,'production_trajectories':6,'total_production_ns':6,
        'inputs':inputs,'source_descriptor_file_sha256':sha(ROOT/'data/raw/phase8/dolmen/data/descriptors/hydhist_amino.csv'),
        'analysis_script_sha256':sha(Path(__file__)),'results':results,
        'posthoc_status':'Nearest-water and radial-normalization alternatives were examined after the primary histogram discrepancy was observed. No claim that the best-matching alternative identifies the original production method; no activity labels used to select an MD force field or fit a model.',
        'limits':['Replicate spread covers seeds within this chosen force field and molecular state, not uncertainty over protonation or force fields.',
                  'Histogram total variation compares reconstructed descriptors with source descriptors; it is not an activity prediction error.',
                  'No volumetric hydration index calculated, no frozen model evaluated with these new descriptors, no synthetic experimental labels.',
                  'Six short trajectories do not establish convergence or a causal relationship between hydration and IRI.']}
    (ROOT/'data/phase10/hydration-results.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps({name:{'hydration_count_0.3nm':v['hydration_count_mean_across_seeds'][2],
          'histogram_total_variation':v['source_histogram_total_variation'],
          'ns_per_day':v['replicate_ns_per_day']} for name,v in results.items()}))


if __name__=='__main__': main()
