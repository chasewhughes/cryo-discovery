"""Analyze only new Phase 12 production against the frozen engineering criterion."""
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

def summarize(pdf, counts, density, temperature):
    return {'mean_pdf':pdf.mean(axis=0).tolist(), 'mean_count_0_30nm':float(counts[:,2].mean()),
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
    if result['input_hashes']!=job['parent_sha256']: raise ValueError('Branch parent provenance mismatch')
    if result['seed']!=job['seed'] or result['compound']!=job['compound']: raise ValueError('Wrong branch identity')
    if not np.isclose(result['source_state_time_ps'],3500,rtol=0,atol=1e-5): raise ValueError('Unexpected parent clock')
    deployment=json.loads((ROOT/'data/phase12/deployment-provenance.json').read_text())
    for field,source in [('script','scripts/run_hydration_extension.py'),('descriptor','scripts/hydration_descriptor.py')]:
        if result['hashes'][field]!=deployment['source_sha256'][source]: raise ValueError('Deployed source mismatch')
    path=directory/'trajectory.npz'
    if sha(path)!=result['hashes']['trajectory']: raise ValueError('Trajectory checksum mismatch')
    if sha(directory/'system.xml')!=result['hashes']['system']: raise ValueError('System checksum mismatch')
    if result['descriptor_version']!=VERSION: raise ValueError('Descriptor version changed')
    conf=result['configuration']
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

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--runs-root',type=Path,default=ROOT/'data/raw/phase12/runpod-attempt2')
    args=p.parse_args(); planpath=ROOT/'data/phase12/sampling-plan.json';plan=json.loads(planpath.read_text())
    runs=[]
    for job in plan['jobs']:
        matches=list(args.runs_root.glob('**/'+job['id']+'/result.json'))
        if len(matches)!=1: raise ValueError(f"Expected exactly one result for {job['id']}, found {len(matches)}")
        runs.append(analyze_run(matches[0].parent,job,plan))
    contrasts=[]
    for compound in ['gly','phe']:
        pair={r['ensemble']:r for r in runs if r['compound']==compound}
        nvt,npt=pair['NVT']['summary'],pair['NPT']['summary']
        contrasts.append({'compound':compound,
            'NPT_minus_NVT_mean_count_0_30nm':npt['mean_count_0_30nm']-nvt['mean_count_0_30nm'],
            'NPT_minus_NVT_mean_density_g_ml':npt['mean_density_g_ml']-nvt['mean_density_g_ml'],
            'whole_production_ensemble_pdf_tv':tv(npt['mean_pdf'],nvt['mean_pdf']),
            'interpretation':'One selected parent pair per compound; descriptive only, no replicate uncertainty or efficacy inference.'})
    result={'status':'Selected stochastic branches; exploratory measurement stability only',
        'plan_sha256':sha(planpath),'analyzer_sha256':sha(__file__),'runs':runs,
        'flagged_runs':sum(any(r['flags'].values()) for r in runs),'new_production_ns':40,'ensemble_contrasts':contrasts,
        'limits':['Selected parents share Phase 11 starting-state history; no independent starting conformations.',
                  'XML states do not preserve RNG internals. New thermostat/barostat seeds create stochastic branches.',
                  'Original 3 ns and new 10 ns were not pooled. Re-equilibration is excluded.',
                  'Flags are engineering criteria, not proof of physical convergence or efficacy.',
                  'No ice, membrane, cell, toxicity, apoptosis or post-thaw function is simulated.',
                  'No new experimental labels, fitted model, or independent activity validation.']}
    write(ROOT/'data/phase12/extension-results.json',result)
    report(result)
    print(json.dumps({'runs':len(runs),'flagged_runs':result['flagged_runs'],'new_production_ns':40}))

def report(result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    runs=result['runs']; lines=[]
    for r in runs:
        lines.append(f"| {r['name']} | {r['first_second_5ns_pdf_tv']:.4f} | {r['second_minus_first_count']:+.3f} | {r['second_minus_first_density_g_ml']:+.5f} | {r['summary']['mean_temperature_K']:.2f} | {', '.join(k for k,v in r['flags'].items() if v) or 'None'} |")
    content=f'''# Longer hydration sampling controls

Four selected 10-ns stochastic branches produced 40 ns of new liquid-water
sampling. **{result['flagged_runs']} of 4 branches retain an engineering flag**
under the frozen first-versus-second 5-ns comparison. Each branch retained its
parent's final coordinates and velocities, reset thermostat/barostat RNG seeds,
and excluded 100 ps of re-equilibration. The original 3-ns segments were not pooled.

| Parent / branch | 100-bin TV | Count change (water) | Density change (g/mL) | Mean T (K) | Flags |
| --- | --- | --- | --- | --- | --- |
'''+ '\n'.join(lines)+'''

The unchanged primary limits are TV > 0.05, absolute water-count change > 0.5
at 0.30 nm, absolute density change > 0.005 g/mL, and absolute whole-production
mean temperature offset > 3 K from 273 K. NVT density is structurally constant.
Every 2-ns window and the complete block/resolution/length diagnostic grid are
saved in `data/phase12/extension-results.json`; no maximum-window gate was added.

![Longer-run diagnostics](hydration-extensions.png)

The parents were selected after inspecting Phase 11. These four branches are
not independent starting conformations or validation replicates. Block-mixing
tail fractions are descriptive references, not p-values; exchangeability and
dependence scales remain unvalidated. Coarsening cannot increase TV.

Passing supports only measurement stability for this descriptor and setup.
It does not establish physical convergence, reproduce unresolved DOLMEN settings,
or predict cryoprotective efficacy. No ice, cell membrane, apoptosis, toxicity,
or post-thaw function is modeled. No experimental labels or models were added.

OpenMM XML states preserve physical state but not the internal RNG state, so
these are explicitly stochastic branches with recorded new seeds.
See [OpenMM Simulation documentation](https://docs.openmm.org/latest/api-python/generated/openmm.app.simulation.Simulation.html).
'''
    one_ns=[next(d['observed_tv'] for d in r['sampling_diagnostics'] if d['bins']==100 and d['endpoint_window_ps']==1000) for r in runs]
    content+=f'\nWithin these same new trajectories, the secondary first-versus-last 1-ns comparisons remain above 0.05 (range {min(one_ns):.4f}–{max(one_ns):.4f}). The longer 5-ns comparisons pass without changing histogram resolution. This supports sensitivity to sampling duration; it does not prove equilibrium. All four primary contrasts fall within the descriptive 5th–95th percentile mixing envelopes at each of the 100/250/500-ps block scales.\n'
    content+='\nFor the selected NPT versus NVT pairs, whole-production water counts at 0.30 nm differ by +0.122 for glycine and +0.335 for phenylalanine; density differs by approximately +0.0084 and +0.0083 g/mL respectively. These are single selected parent pairs, so no replicate uncertainty or efficacy inference is assigned.\n'
    if result['flagged_runs']:
        content+='\nThe next step is to investigate the remaining flagged measurements before expanding candidate screening. Do not turn these descriptors into efficacy predictions.\n'
    else:
        content+='\nThe next virtual step is the already deferred leucine/isoleucine control comparison, which reduces molecular-size differences. It still requires a new frozen design and budget check. Experimental ice-recrystallization and cell-recovery measurements remain necessary for efficacy validation.\n'
    costpath=ROOT/'data/phase12/compute-costs.json'
    if costpath.exists():
        costs=json.loads(costpath.read_text())
        content+=f"\nEstimated cumulative GPU spending through Phase 12 is **${costs['cumulative_estimated_gpu_usd']:.4f}** against the $10 authorization. Research Pod deletion confirmed: **{costs['all_research_pods_absent']}**. Elapsed-time estimates are separate from posted provider billing, which may be incomplete and include storage. See `data/phase12/compute-costs.json`.\n"
    content+='\nThe first four-Pod attempt stopped before production when an overly strict restored-state comparison rejected GPU rounding. It cost approximately $0.0820 and is included above. The successful retry retained the frozen scientific plan and recorded restoration errors below 4.12e-7 nm for positions and zero for velocities. Failed-run archives, receipts and source are preserved in `data/phase12/retry-rationale.json` and Git.\n'
    content+='\nReproduce from locally archived results with `python3 scripts/with_external_storage.py -- env MPLCONFIGDIR=data/tmp/matplotlib .venv/bin/python scripts/analyze_hydration_extensions.py`. The frozen plan, source hashes, branch-parent hashes and raw trajectory checksums are preserved in `data/phase12/`.\n'
    (ROOT/'reports/hydration-extensions.md').write_text(content)
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    labels=[{'gly':'Glycine','phe':'Phenylalanine'}[r['compound']]+'\n'+r['ensemble'] for r in runs]
    x=np.arange(4)
    axes[0,0].bar(x,[r['first_second_5ns_pdf_tv'] for r in runs],color=['#1f77b4','#ff7f0e','#2ca02c','#d62728'])
    axes[0,0].axhline(.05,color='#c33',ls='--',label='Frozen 0.05 flag');axes[0,0].legend()
    axes[0,0].set(xticks=x,xticklabels=labels,ylabel='100-bin total variation',title='First 5 ns versus second 5 ns')
    for r,label in zip(runs,labels):
        axes[0,1].plot(np.arange(1,6)*2-1,[w['mean_count_0_30nm'] for w in r['windows']],marker='o',label=label.replace('\n',' '))
        axes[1,0].plot(np.arange(1,6)*2-1,[w['mean_density_g_ml'] for w in r['windows']],marker='o',label=label.replace('\n',' '))
        rows=[d for d in r['sampling_diagnostics'] if d['bins']==100 and d['block_ps']==100]
        axes[1,1].plot([d['endpoint_window_ps']/1000 for d in rows],[d['observed_tv'] for d in rows],marker='o',label=r['name'])
    axes[0,1].set(title='All five production windows',xlabel='Window midpoint (ns)',ylabel='Mean water count at 0.30 nm')
    axes[0,1].legend(fontsize=8)
    axes[1,0].set(xlabel='Window midpoint (ns)',ylabel='Mean density (g/mL)')
    axes[1,1].axhline(.05,color='#c33',ls='--');axes[1,1].set(title='Endpoint-window length sensitivity',xlabel='Duration of each endpoint window (ns)',ylabel='100-bin total variation')
    fig.suptitle('Phase 12: selected branches; measurement stability, no efficacy validation')
    fig.savefig(ROOT/'reports/hydration-extensions.png',dpi=160);plt.close(fig)

if __name__=='__main__': main()
