"""Analyze only new Phase 13 production against the frozen engineering criterion."""
import json
from pathlib import Path
import numpy as np
try:
    from .calibrate_hydration_sampling import sha, write, tv, coarsen
    from .hydration_descriptor import measure, VERSION
except ImportError:
    from calibrate_hydration_sampling import sha, write, tv, coarsen
    from hydration_descriptor import measure, VERSION

ROOT=Path(__file__).resolve().parents[1]

def resolve_locations(plan, map_path=None):
    path=Path(map_path or ROOT/'data/phase13/result-locations.json')
    if not path.is_file(): raise ValueError('Explicit result-locations map is required')
    raw=json.loads(path.read_text()); locations=raw.get('locations',raw) if isinstance(raw,dict) else None
    ids={j['id'] for j in plan['jobs']}
    if not isinstance(locations,dict) or set(locations)!=ids: raise ValueError('Result map must contain exactly frozen job IDs')
    base=(ROOT/'data/raw/phase13').resolve(); resolved={}
    for jid,value in locations.items():
        if not isinstance(value,str): raise ValueError('Result map paths must be strings')
        rel=Path(value)
        if rel.is_absolute() or '..' in rel.parts: raise ValueError('Unsafe result map path')
        if rel.parts[:3] == ('data','raw','phase13'): rel=Path(*rel.parts[3:])
        if len(rel.parts)!=4 or rel.parts[1]!=jid or rel.parts[0] not in {'runpod-attempt2','runpod-attempt3'} or rel.parts[-2:] != ('runs',jid): raise ValueError('Result map path must end in allowed attempt/runs/job ID')
        target=(base/rel).resolve()
        if base not in target.parents or not (target/'result.json').is_file(): raise ValueError('Mapped result path missing or escapes raw storage')
        resolved[jid]=target
    return resolved

def summarize(pdf, counts, density, temperature):
    return {'mean_pdf':pdf.mean(axis=0).tolist(), 'mean_counts':counts.mean(axis=0).tolist(), 'mean_count_0_30nm':float(counts[:,2].mean()),
            'mean_density_g_ml':float(density.mean()),'mean_temperature_K':float(temperature.mean())}

def sampling_grid(pdf, config):
    rows=[]
    for bins in config['bins']:
        coarse=coarsen(pdf,bins)
        for duration in config['endpoint_window_ps']:
            n=duration//10
            observed=tv(coarse[:n].mean(axis=0),coarse[-n:].mean(axis=0),bins)
            for block_ps in config['block_ps']:
                k=block_ps//10; m=n//k
                if n%k or len(pdf)%k or 2*n>len(pdf): raise ValueError('Invalid block grouping')
                blocks=coarse.reshape(len(pdf)//k,k,bins).mean(axis=1)
                rng=np.random.default_rng(config['random_seed']); values=[]
                for _ in range(config['block_mixing_permutations']):
                    order=rng.permutation(len(blocks))
                    values.append(tv(blocks[order[:m]].mean(axis=0),blocks[order[-m:]].mean(axis=0),bins))
                rows.append({'bins':bins,'endpoint_window_ps':duration,'block_ps':block_ps,
                    'observed_tv':observed,'mixed_tv_quantiles_05_50_95':np.quantile(values,[.05,.5,.95]).tolist(),
                    'fraction_mixed_tv_ge_observed':float(np.mean(np.asarray(values)>=observed))})
    return rows

def analyze_run(directory, job, plan):
    result=json.loads((directory/'result.json').read_text())
    if result['phase']!=13: raise ValueError('Wrong study phase')
    if result['input_hashes']!=job['parent_sha256']: raise ValueError('Branch parent provenance mismatch')
    if result['seed']!=job['seed'] or result['compound']!=job['compound']: raise ValueError('Wrong branch identity')
    if not np.isclose(result['source_state_time_ps'],0,rtol=0,atol=1e-5): raise ValueError('Unexpected parent clock')
    deployment=json.loads((ROOT/'data/phase13/deployment-provenance.json').read_text())
    for field,source in [('script','scripts/run_matched_hydration.py'),('descriptor','scripts/hydration_descriptor.py')]:
        if result['hashes'][field]!=deployment['source_sha256'][source]: raise ValueError('Deployed source mismatch')
    path=directory/'trajectory.npz'
    if sha(path)!=result['hashes']['trajectory']: raise ValueError('Trajectory checksum mismatch')
    if sha(directory/'system.xml')!=result['hashes']['system']: raise ValueError('System checksum mismatch')
    if result['descriptor_version']!=VERSION: raise ValueError('Descriptor version changed')
    if result['hashes']['integration_engine']!=deployment['source_sha256']['scripts/run_hydration_extension.py']: raise ValueError('Integration engine changed')
    conf=result['configuration']
    if conf['water_molecules']!=2070: raise ValueError('Solvent count mismatch')
    if conf['barostat_seed']!=(job['seed']+100000 if job['ensemble']=='NPT' else None): raise ValueError('Wrong barostat RNG seed')
    if conf['platform']!='CUDA' or conf['platform_properties']!={'Precision':'mixed'}: raise ValueError('Unexpected platform')
    for name in ['frames','production_ps','equilibration_ps','ensemble']:
        if conf[name]!=job[name]: raise ValueError('Configuration differs from plan: '+name)
    with np.load(path) as d:
        pdf=d['nearest_pdf']; counts=d['hydration_counts']; density=d['density_g_ml']; temps=d['temperature_K']
        if pdf.shape!=(1000,100) or counts.shape!=(1000,7): raise ValueError('Incomplete production')
        for key in d.files:
            if not np.isfinite(d[key]).all(): raise ValueError('Nonfinite trajectory values: '+key)
        if np.any(pdf<0) or np.any(counts<0): raise ValueError('Negative density/count')
        np.testing.assert_allclose(pdf.sum(axis=1)*.005,1,atol=1e-10)
        np.testing.assert_allclose(d['production_time_ps'],np.arange(1,1001)*10,atol=1e-8)
        boxes=d['boxes_nm']; volumes=np.linalg.det(boxes)
        np.testing.assert_allclose(density,conf['mass_da']*1.66053906660e-3/volumes,rtol=1e-10)
        if job['ensemble']=='NVT': np.testing.assert_allclose(boxes,np.broadcast_to(boxes[0],boxes.shape),atol=1e-10)
        checks=[]
        for i in [0,499,999]:
            c,p=measure(d['positions_nm'][i],boxes[i],d['solute_indices'],d['water_oxygen_indices'])
            # Coordinates are archived as float32; one distance very near an edge can change bins.
            if np.max(np.abs(c-counts[i]))>1 or tv(p,pdf[i])>.001: raise ValueError('Descriptor recomputation mismatch')
            checks.append({'frame':i,'max_count_error':float(np.max(np.abs(c-counts[i]))),'pdf_tv_error':tv(p,pdf[i])})
        first=summarize(pdf[:500],counts[:500],density[:500],temps[:500])
        last=summarize(pdf[500:],counts[500:],density[500:],temps[500:])
        delta_count=last['mean_count_0_30nm']-first['mean_count_0_30nm']
        delta_density=last['mean_density_g_ml']-first['mean_density_g_ml']
        contrast=tv(first['mean_pdf'],last['mean_pdf']); gate=plan['primary']
        flags={'pdf_drift':contrast>gate['max_pdf_total_variation'],
               'count_drift':abs(delta_count)>gate['max_absolute_count_0_30nm_change'],
               'density_drift':abs(delta_density)>gate['max_absolute_density_change_g_ml'],
               'temperature_offset':abs(float(temps.mean())-273)>gate['max_absolute_whole_production_mean_temperature_error_K']}
        windows=[{'window':i+1,'start_ns':i*2,'end_ns':(i+1)*2,
            **summarize(pdf[i*200:(i+1)*200],counts[i*200:(i+1)*200],density[i*200:(i+1)*200],temps[i*200:(i+1)*200])} for i in range(5)]
        return {'name':job['id'],'parent_id':job['parent_id'],'seed':job['seed'],'compound':job['compound'],
                'ensemble':job['ensemble'],'trajectory_sha256':sha(path),'result_sha256':sha(directory/'result.json'),
                'summary':summarize(pdf,counts,density,temps),'halves':[first,last],'windows':windows,
                'first_second_5ns_pdf_tv':contrast,'second_minus_first_count':delta_count,
                'second_minus_first_density_g_ml':delta_density,'flags':flags,'coordinate_spot_checks':checks,
                'sampling_diagnostics':sampling_grid(pdf,plan['secondary'])}

def compare_groups(runs):
    import itertools
    groups={}
    for compound in ['leu','ile']:
        members=[r for r in runs if r['compound']==compound]
        if len(members)!=3 or len({r['seed'] for r in members})!=3:raise ValueError('Need three independent trajectories per compound')
        counts=np.array([r['summary']['mean_counts'] for r in members])
        densities=[r['summary']['mean_density_g_ml'] for r in members]
        groups[compound]={'mean_counts':counts.mean(axis=0).tolist(),'sample_sd_counts':counts.std(axis=0,ddof=1).tolist(),
            'mean_pdf':np.mean([r['summary']['mean_pdf'] for r in members],axis=0).tolist(),
            'mean_density_g_ml':float(np.mean(densities)),'sample_sd_density_g_ml':float(np.std(densities,ddof=1)),
            'replicates':3,'within_pair_tv':[{'runs':[a['name'],b['name']],'tv':tv(a['summary']['mean_pdf'],b['summary']['mean_pdf'])} for a,b in itertools.combinations(members,2)]}
    cross=[{'leu':a['name'],'ile':b['name'],'tv':tv(a['summary']['mean_pdf'],b['summary']['mean_pdf']),
            'leu_minus_ile_count_0_30nm':a['summary']['mean_count_0_30nm']-b['summary']['mean_count_0_30nm']}
            for a in runs if a['compound']=='leu' for b in runs if b['compound']=='ile']
    within=[p['tv'] for g in groups.values() for p in g['within_pair_tv']]
    deltas=[p['leu_minus_ile_count_0_30nm'] for p in cross]
    return {'groups':groups,'leu_minus_ile_mean_counts':(np.array(groups['leu']['mean_counts'])-groups['ile']['mean_counts']).tolist(),
            'between_compound_mean_pdf_tv':tv(groups['leu']['mean_pdf'],groups['ile']['mean_pdf']),
            'cross_compound_pairs':cross,'all_cross_tvs_exceed_all_within_tvs':min(p['tv'] for p in cross)>max(within),
            'all_cross_count_differences_same_sign':bool(min(deltas)>0 or max(deltas)<0),
            'interpretation':'Pair values share trajectories and are not independent observations. Only six independently prepared trajectories exist; descriptive method-development comparison, no calibrated significance or efficacy inference.'}

def main():
    planpath=ROOT/'data/phase13/sampling-plan.json';plan=json.loads(planpath.read_text());locations=resolve_locations(plan);runs=[]
    for job in plan['jobs']:
        directory=locations[job['id']]
        row=analyze_run(directory,job,plan)
        raw=json.loads((directory/'result.json').read_text())
        row['mean_solute_concentration_mM']=float(row['summary']['mean_density_g_ml']*1000/(raw['configuration']['mass_da']*1.66053906660e-3*6.02214076e23*1e-24))
        # Mean inverse volume is proportional to mean density at fixed mass.
        runs.append(row)
    result={'status':'Same-formula control comparison; known-label method development only','plan_sha256':sha(planpath),
            'analyzer_sha256':sha(__file__),'runs':runs,'comparison':compare_groups(runs),
            'flagged_runs':sum(any(r['flags'].values()) for r in runs),'new_production_ns':60,
            'limits':plan['limits'],'new_experimental_rows':0,'model_fitting':False}
    write(ROOT/'data/phase13/matched-results.json',result);report(result)
    print(json.dumps({'runs':6,'flagged_runs':result['flagged_runs'],'between_compound_pdf_tv':result['comparison']['between_compound_mean_pdf_tv'],'leu_minus_ile_count':result['comparison']['leu_minus_ile_mean_counts'][2]}))

def report(result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    runs=result['runs'];comparison=result['comparison'];groups=comparison['groups']
    lines=[]
    for r in runs:
        lines.append(f"| {r['name']} | {r['summary']['mean_count_0_30nm']:.3f} | {r['first_second_5ns_pdf_tv']:.4f} | {r['summary']['mean_density_g_ml']:.5f} | {r['mean_solute_concentration_mM']:.2f} | {', '.join(k for k,v in r['flags'].items() if v) or 'None'} |")
    within=[p['tv'] for g in groups.values() for p in g['within_pair_tv']];cross=[p['tv'] for p in comparison['cross_compound_pairs']]
    if result['flagged_runs']:
        finding='At least one trajectory fails a frozen engineering stability criterion, so compound differences require caution and further diagnosis.'
    elif comparison['all_cross_tvs_exceed_all_within_tvs'] and comparison['all_cross_count_differences_same_sign']:
        finding='Both selected hydration summaries separate these known controls across all three preparations in this small simulation set. This is an unvalidated physical descriptor difference, not evidence of superior cryoprotection.'
    elif not comparison['all_cross_tvs_exceed_all_within_tvs'] and not comparison['all_cross_count_differences_same_sign']:
        finding='The between-compound comparisons overlap preparation-to-preparation variation for both selected hydration summaries. This setup does not cleanly distinguish these known controls using these summaries.'
    else:
        finding='Nearby-water counts separate the compounds in these three preparations each, but full distance-distribution differences overlap within-compound variation. This mixed result does not validate a prediction of cryoprotection.' if comparison['all_cross_count_differences_same_sign'] else 'Full distance distributions separate the compounds in this small set, while nearby-water count differences overlap within-compound variation. This mixed result does not validate a prediction of cryoprotection.'
    text=f'''# Leucine versus isoleucine: a virtual same-formula comparison

{finding}

Six independently prepared liquid-water simulations produced **60 ns** of new
sampling: three 10-ns trajectories per compound, each following 1 ns excluded
equilibration. **{result['flagged_runs']} of six trajectories have an engineering stability flag.**
Both compounds have formula C6H13NO2 and modeled mass 131.175 Da, and each box
contains one zwitterion and exactly 2,070 water molecules. NPT simulations use
273 K, 1 bar, CHARMM36 and the same local TIP4P/Ice model as the prior phases.
Same formula controls mass and atom count, while shape, stereochemistry and
exposed surface remain different.

![Structures](leucine-isoleucine-structures.png)

Mean water counts within 0.30 nm, expressed as mean ± sample SD across three
independent trajectories, are **{groups['leu']['mean_counts'][2]:.3f} ± {groups['leu']['sample_sd_counts'][2]:.3f}
for leucine** and **{groups['ile']['mean_counts'][2]:.3f} ± {groups['ile']['sample_sd_counts'][2]:.3f} for isoleucine**.
Leucine minus isoleucine is **{comparison['leu_minus_ile_mean_counts'][2]:+.3f} water molecules**.
All nine cross-compound count differences have the same sign:
**{comparison['all_cross_count_differences_same_sign']}**. These overlapping pair
comparisons are descriptive; they are not nine independent observations.

The 100-bin TV between the equally weighted compound mean PDFs is
**{comparison['between_compound_mean_pdf_tv']:.4f}**. Individual cross-compound
pair TVs range **{min(cross):.4f}–{max(cross):.4f}**, versus
**{min(within):.4f}–{max(within):.4f}** within compounds. Every cross-compound TV
exceeds every within-compound TV: **{comparison['all_cross_tvs_exceed_all_within_tvs']}**.
This compares observable separation with preparation-to-preparation variation;
it supplies no calibrated significance test or efficacy inference.

| Preparation | Mean water count at 0.30 nm | First/second 5-ns TV | Mean density (g/mL) | Mean concentration (mM) | Flags |
| --- | --- | --- | --- | --- | --- |
'''+ '\n'.join(lines)+'''

![Hydration comparison](matched-hydration.png)

The descriptor counts unique water oxygens by their nearest distance to any
solute atom, including hydrogens. Its PDF is normalized within 0–0.5 nm for
each frame and then averaged equally across frames. It is not a radial
distribution function and has no radial-shell or exposed-area normalization.

The frozen stability checks retain TV > 0.05, absolute half-to-half count change
> 0.5 water, density change > 0.005 g/mL, and mean temperature offset > 3 K.
All five 2-ns windows and the full binning/block/length diagnostics are retained.
The replicate unit is the independently prepared trajectory, never a frame.
No endpoint, binning or seed was selected after examining production results.

The published context is a known activity contrast: leucine 45.6 ± 14.0 and
isoleucine 18.8 ± 4.1 percent mean grain size (reported SD), with lower values
indicating stronger cell-free ice-recrystallization inhibition. These values
were known during control selection and were not used for fitting or choosing
a direction of hydration effect. They are not new predictions or independent
validation. See the [original study](https://doi.org/10.1038/s41467-024-52266-w)
and the [source reconciliation](../data/phase11/deferred-controls.json).

The source assay uses nominally 20 mM compound, 10 mM NaCl, and ice annealing at
−8 °C. These simulations use salt-free liquid water at 273 K and report their
own realized concentration. They do not model an ice surface, recrystallization,
apoptosis, toxicity or cell recovery. Same-formula matching cannot establish a
causal cryoprotective mechanism. The original DOLMEN descriptor settings remain
unresolved; these are the explicitly defined local nearest-water descriptors.
'''
    if result['flagged_runs']:
        text+='\nRemaining engineering flags limit interpretation; investigate those runs before expanding this comparison.\n'
    else:
        text+='\nThe runs support a descriptive comparison of hydration under this setup. Demonstrating cryoprotection requires condition-matched ice-recrystallization and cell-recovery experiments. Broader virtual modeling should first use additional controls and independently validate the physical setup and observable.\n'
    costs=ROOT/'data/phase13/compute-costs.json'
    if costs.exists():
        c=json.loads(costs.read_text());text+=f"\nEstimated cumulative GPU spending is **${c['cumulative_estimated_gpu_usd']:.4f}** of the $10 authorization; all research Pods absent: **{c['all_research_pods_absent']}**. Estimates include failed attempts; posted billing may be incomplete and include storage.\n"
    text+='\nThe frozen design, source and input hashes, all individual comparisons and uncertainty limitations are in `data/phase13/`. Reproduce with `python3 scripts/with_external_storage.py -- env MPLCONFIGDIR=data/tmp/matplotlib .venv/bin/python scripts/analyze_matched_hydration.py`.\n'
    (ROOT/'reports/matched-hydration.md').write_text(text)
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained');colors={'leu':'#377eb8','ile':'#e66101'}
    for i,c in enumerate(['leu','ile']):
        vals=[r['summary']['mean_count_0_30nm'] for r in runs if r['compound']==c]
        axes[0,0].scatter(np.array([-.12,0,.12])+i,vals,color=colors[c],s=45)
        axes[0,0].errorbar(i,np.mean(vals),yerr=np.std(vals,ddof=1),fmt='_',color='black',capsize=8)
        axes[0,1].plot(np.linspace(.0025,.4975,100),groups[c]['mean_pdf'],label=c.upper(),color=colors[c])
        for r in [r for r in runs if r['compound']==c]:
            axes[1,0].plot([1,3,5,7,9],[w['mean_count_0_30nm'] for w in r['windows']],color=colors[c],alpha=.7,marker='o',label=r['name'])
    axes[0,0].set(xticks=[0,1],xticklabels=['L-leucine','L-isoleucine'],ylabel='Mean unique-water count at 0.30 nm',title='Three independent preparations each; mean ± SD')
    axes[0,1].set(xlabel='Nearest-solute-atom distance (nm)',ylabel='Conditional PDF density (1/nm)',title='Equally weighted compound mean PDFs');axes[0,1].legend()
    axes[1,0].set(xlabel='2-ns window midpoint (ns)',ylabel='Mean water count at 0.30 nm',title='Every window of every trajectory')
    axes[1,1].scatter(np.zeros(len(within)),within,label='Within compound',color='#777777')
    axes[1,1].scatter(np.ones(len(cross)),cross,label='Cross compound',color='#6a3d9a')
    axes[1,1].set(xticks=[0,1],xticklabels=['Within compound (6 pairs)','Cross compound (9 pairs)'],ylabel='100-bin total variation',title='Pair comparisons share trajectories')
    fig.suptitle('Same-formula controls: hydration comparison, no efficacy validation')
    fig.savefig(ROOT/'reports/matched-hydration.png',dpi=160);plt.close(fig)

if __name__=='__main__':main()
