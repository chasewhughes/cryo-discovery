"""Report ensemble sensitivity and prespecified stability flags without fitting."""
import json
import hashlib
import platform
import subprocess
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

try:
    from .hydration_descriptor import VERSION, measure
except ImportError:
    from hydration_descriptor import VERSION, measure

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def correlation_diagnostic(values):
    """Finite-sample initial-positive autocorrelation sum; exploratory, not a CI."""
    x=np.asarray(values,dtype=float)-np.mean(values)
    denominator=float(np.dot(x,x))
    if denominator<1e-20:
        return {'lag1':None,'rough_effective_frames':None,'note':'Constant series'}
    acf=np.correlate(x,x,mode='full')[len(x)-1:]/denominator
    positive=[]
    for value in acf[1:len(x)//2]:
        if value<=0: break
        positive.append(float(value))
    return {'lag1':float(acf[1]),'rough_effective_frames':float(len(x)/(1+2*sum(positive))),
        'positive_lags_used':len(positive),'note':'Biased finite-length autocorrelation, truncated at first nonpositive lag; descriptive only'}


def write_report(result):
    names={'gly':'Glycine','phe':'L-phenylalanine'}
    lines=['# Hydration measurement and ensemble stability', '',
        f"Completed {result['trajectories']} trajectories totaling {result['production_ns']:g} ns of production, plus 6 ns of equilibration. "
        f"{result['flagged_runs']} runs triggered at least one prespecified stability flag. "
        'This is a liquid-water sensitivity study, not validation of ice inhibition or cell protection.', '',
        '## Measurement and design', '',
        'The new `cryo-nearest-water-v1` descriptor counts each nearby water once and measures its distance to the nearest solute atom, including solute hydrogens. '
        'Each frame has a conditional PDF over 0–0.5 nm, and frames are averaged with equal weight. '
        'All-pairs PDFs are retained as a secondary sensitivity measurement. '
        'The original DOLMEN production settings remain unresolved: this is an explicitly new representation, not a substitute input for the frozen source model. '
        '[Definition and saved-trajectory audit](hydration-definition.md).', '',
        'Glycine and L-phenylalanine each have three seeds in fixed-volume NVT and pressure-controlled NPT. '
        'Every run starts in a 4 nm cube, equilibrates for 500 ps, and produces 300 frames over 3 ns. '
        'Both ensembles use 273 K, CHARMM36, TIP4P/Ice, assumed free-amino-acid zwitterions, and no added salt. '
        'NPT uses an isotropic Monte Carlo barostat targeting 1 bar, proposing volume changes every 25 steps. '
        'The thermostat controls temperature separately. [OpenMM barostat documentation](https://docs.openmm.org/latest/api-python/generated/openmm.openmm.MonteCarloBarostat.html).', '',
        'Preparation seeds and durations match across ensembles, but trajectories diverge; this is not paired experimental replication. '
        'Changing volume changes density and effective solute concentration together. '
        'The source experimental assay uses 20 mM compound and 10 mM NaCl, so these simulations do not reproduce that solution. '
        '[Original study](https://doi.org/10.1038/s41467-024-52266-w), [plan frozen before production](../data/phase11/stability-plan.json).', '',
        '## Results', '',
        'Values below are means ± sample SD across three simulation seeds. They do not include uncertainty from force fields, molecular states or experimental assays.', '',
        '| Compound | Ensemble | Density (g/mL) | Waters within 0.30 nm | Flagged runs |',
        '| --- | --- | ---: | ---: | ---: |']
    for g in result['groups']:
        lines.append(f"| {names[g['compound']]} | {g['ensemble']} | {g['density_mean_g_ml']:.5f} ± {g['density_seed_sd_g_ml']:.5f} | {g['count_030_mean']:.3f} ± {g['count_030_seed_sd']:.3f} | {g['flagged_runs']}/3 |")
    lines += ['', '![Density and hydration time series](hydration-stability.png)', '',
        'The following differences subtract NVT from NPT within each preparation seed, then average across seeds. '
        'They describe the sensitivity of the entire modeled ensemble/volume setup; they do not isolate a causal density effect.', '',
        '| Compound | Mean density change (g/mL) | Mean hydration-count change | Mean nearest-PDF TV |',
        '| --- | ---: | ---: | ---: |']
    for c in result['ensemble_contrasts']:
        pairs=c['paired_seed_contrasts']
        values=[np.mean([p[k] for p in pairs]) for k in ['NPT_minus_NVT_density_g_ml','NPT_minus_NVT_count_030','nearest_pdf_tv_between_ensembles']]
        lines.append(f"| {names[c['compound']]} | {values[0]:+.5f} | {values[1]:+.3f} | {values[2]:.4f} |")
    lines += ['', '## Stability flags and decision', '',
        'Before production we specified three 1 ns time blocks, flagging first-to-last changes above 0.005 g/mL in density, '
        '0.5 water molecules at 0.30 nm, or 0.05 total variation in the nearest PDF; mean temperature must remain within 3 K of target. '
        'These are engineering thresholds, not statistical or physical convergence guarantees. '
        'All block means, per-seed ensemble contrasts, frame-stride sensitivity and exploratory autocorrelation estimates are preserved in the '
        '[numerical results](../data/phase11/stability-results.json). Autocorrelation estimates are finite-sample diagnostics, not confidence intervals.', '',
        '| Run | Triggered flags |', '| --- | --- |']
    for r in result['runs']:
        lines.append(f"| {r['name']} | {', '.join(k for k,v in r['flags'].items() if v) or 'None'} |")
    lines += ['', 'All 12 flags concern the 100-bin PDF. No run crossed the prespecified density, 0.30 nm count or mean-temperature thresholds. '
        'The first-to-last PDF total variations range from '
        f"{min(r['first_last_pdf_tv'] for r in result['runs']):.3f} to {max(r['first_last_pdf_tv'] for r in result['runs']):.3f}. "
        'A threshold crossing does not by itself distinguish temporal change from finite histogram sampling.', '']
    diagnostic_path=ROOT/'data/phase11/sampling-diagnostics.json'
    if diagnostic_path.exists():
        diagnostic=json.loads(diagnostic_path.read_text())
        if diagnostic['source_results_sha256']==sha(ROOT/'data/phase11/stability-results.json'):
            upper=', '.join(r['run'] for r in diagnostic['runs'] if r['chronological_1ns_blocks_tv']>r['random_100ps_block_mixing_tv_quantiles_05_50_95'][2]) or 'None'
            lines += [f"A post hoc diagnostic found {diagnostic['within_mixed_05_95_count']}/12 chronological PDF differences within the 5th–95th percentile range obtained by randomly mixing 100 ps blocks from the same run. "
                f'Runs above that range: {upper}. '
                'This suggests finite sampling is relevant to the chosen 0.05 threshold, but does not establish stationarity: exchangeability and the block length remain assumptions. '
                'The tail fractions are not calibrated p-values. Coarsening cannot increase TV, so smaller 20-bin differences do not validate a new threshold. '
                '**All 12 original flags remain.** [Post hoc sampling diagnostics](../data/phase11/sampling-diagnostics.json).', '']
    lines += ['', result['decision']+'.', '',
        'Do not scale directly to novel candidate screening. First assess whether additional trajectory duration resolves the observed flags and whether '
        'density/ensemble choices materially change descriptors. Three nanoseconds is longer than the pilot but shorter than the published 20 ns; '
        'neither duration automatically establishes convergence. Molecular size still differs between the two controls, and no new model was fitted.', '',
        'A deferred leucine/isoleucine pair has the same molecular formula and verified free-amino-acid vacuum template builds. '
        'Its labels are already known and both show some IRI activity, so it is a method-development activity contrast, not an independent active/inactive test. '
        'No solvated simulations of these additional compounds were run. [Deferred controls](../data/phase11/deferred-controls.json).', '',
        '## Compute, validation and limits', '']
    costs=ROOT/'data/phase11/compute-costs.json'
    if costs.exists():
        c=json.loads(costs.read_text())
        lines.append(f"Estimated GPU charges are ${c['phase11_estimated_gpu_usd']:.3f} for this phase and ${c['cumulative_estimated_gpu_usd']:.3f} across all research attempts, against the user's $10 cumulative limit. "
            'These elapsed-time estimates are not final invoices and exclude separately billed storage. '
            + ('All research Pods were confirmed absent. ' if c['all_research_pods_absent'] else 'Research Pod cleanup remains unconfirmed. ')
            + '[Cost/deletion record](../data/phase11/compute-costs.json).')
        if 'posted_billing_amount_total_usd' in c:
            lines.append(f"Provider records have posted ${c['posted_billing_amount_total_usd']:.4f} in charges so far, potentially including storage. "
                'Phase 11 billed-time coverage is shorter than its recorded elapsed lifetime, so this partial total is not treated as the final cost.')
    lines += ['', 'The analyzer checks planned configurations, deployed input hashes, trajectory hashes, every saved frame for finite coordinates/observables, '
        'PDF normalization and density recomputed from mass and volume. It spot-checks count recalculation on the first, middle and last frame of every run; '
        'intermediate frames are covered by hashes and numerical checks but are not all independently remeasured. '
        'Raw trajectories, logs and environments remain in ignored local `cryo-adata/` storage.', '',
        'The deployed source is preserved in Git commit `06210fc`, verified against every launch input hash. '
        'During review we found that the companion NPT PDB retained the initial box dimensions even though trajectory and final-state boxes were correct. '
        'The current runner fixes that metadata, and corrected `topology-final-box.pdb` copies accompany the preserved original cloud outputs. '
        'No trajectory, energy or hydration measurement was changed. [Deployment provenance](../data/phase11/deployment-provenance.json), '
        '[PDB correction record](../data/phase11/pdb-box-corrections.json).', '',
        '**Zero independent experimental rows were added.** There is no ice interface, membrane, apoptosis target, cell-survival model or toxicity measurement. '
        'NPT specifies a pressure target, but we have not independently estimated mean pressure or calibrated the bulk-water model. '
        'A stable trajectory cannot validate a cryoprotectant. Prospective ice and post-thaw viability/function measurements remain necessary to establish a novel protective effect.', '',
        'Reproduction commands and test results are in the [simulation guide](../simulation/README.md) and [verification record](verification.md).', '']
    (ROOT/'reports/hydration-stability.md').write_text('\n'.join(lines))


def tv(a,b):
    return float(.5*np.abs(np.asarray(a)-np.asarray(b)).sum()*.005)


def main():
    plan = json.loads((ROOT/'data/phase11/stability-plan.json').read_text())
    cloud_state = json.loads((ROOT/'data/raw/phase11/runpod/state.json').read_text())
    provenance=json.loads((ROOT/'data/phase11/deployment-provenance.json').read_text())
    for path, expected in cloud_state['input_sha256'].items():
        source=subprocess.check_output(['git','show',provenance['deployed_source_commit']+':'+path],cwd=ROOT)
        if hashlib.sha256(source).hexdigest() != expected:
            raise ValueError('Cloud input changed: '+path)
    raw = ROOT/'data/raw/phase11/runpod/runs'
    rows, series = [], {}
    limits = plan['diagnostics']['flags']
    for job in plan['jobs']:
        name = f"{job['compound']}-{job['ensemble']}-{job['seed']}"
        path = raw/name/'result.json'
        r = json.loads(path.read_text())
        cfg = r['configuration']
        if any(cfg[k]!=job[k] for k in ['ensemble','equilibration_ps','production_ps','frames']) or r['seed']!=job['seed'] or r['compound']!=job['compound'] or r['descriptor_version']!=VERSION:
            raise ValueError('Unexpected simulation configuration')
        for k,source_name in [('script','scripts/run_hydration_stability.py'),('descriptor','scripts/hydration_descriptor.py')]:
            if r['hashes'][k]!=cloud_state['input_sha256'][source_name]: raise ValueError('Deployed script hash mismatch')
        for k, file in [('trajectory',path.parent/'trajectory.npz'),('system',path.parent/'system.xml')]:
            if r['hashes'][k] != sha(file): raise ValueError('Hash mismatch: '+str(file))
        with np.load(path.parent/'trajectory.npz') as d:
            count = d['hydration_counts']; pdf = d['nearest_pdf']; density = d['density_g_ml']
            temp = d['temperature_K']; energy = d['potential_kj_mol']
            if count.shape!=(job['frames'],7) or pdf.shape!=(job['frames'],100) or any(x.shape!=(job['frames'],) for x in [density,temp,energy]) or d['pair_histograms'].shape!=pdf.shape:
                raise ValueError('Unexpected observable shapes')
            if len(count)!=job['frames'] or not all(np.isfinite(x).all() for x in [count,pdf,density,temp,energy,d['positions_nm'],d['boxes_nm']]):
                raise ValueError('Incomplete/nonfinite trajectory')
            if not np.allclose(pdf.sum(axis=1)*.005,1): raise ValueError('PDF normalization failed')
            expected_density = cfg['mass_da']*1.66053906660e-3/np.linalg.det(d['boxes_nm'])
            np.testing.assert_allclose(density,expected_density)
            checked_frames=[0,len(count)//2,len(count)-1]
            for i in checked_frames:
                expected,_ = measure(d['positions_nm'][i],d['boxes_nm'][i],d['solute_indices'],d['water_oxygen_indices'])
                np.testing.assert_array_equal(count[i],expected)
            if cfg['ensemble']=='NVT' and not np.allclose(density,density[0]): raise ValueError('NVT volume changed')
            blocks = [{'density_g_ml':float(density[ix].mean()),'counts':count[ix].mean(axis=0).tolist(),
                'temperature_K':float(temp[ix].mean()),'nearest_pdf':pdf[ix].mean(axis=0).tolist(),
                'potential_kj_mol':float(energy[ix].mean())} for ix in np.array_split(np.arange(len(count)),3)]
            density_drift = blocks[-1]['density_g_ml']-blocks[0]['density_g_ml']
            count_drift = blocks[-1]['counts'][2]-blocks[0]['counts'][2]
            pdf_drift = tv(blocks[0]['nearest_pdf'],blocks[-1]['nearest_pdf'])
            flags = {'density_drift':abs(density_drift)>limits['max_absolute_first_last_block_density_change_g_ml'],
                'count_drift_030':abs(count_drift)>limits['max_absolute_first_last_block_count_change'],
                'pdf_drift':pdf_drift>limits['max_first_last_block_pdf_total_variation'],
                'temperature':abs(temp.mean()-plan['design']['temperature_K'])>limits['max_absolute_mean_temperature_error_K']}
            flags={key:bool(value) for key,value in flags.items()}
            rows.append({'name':name, 'compound':job['compound'],'ensemble':job['ensemble'],'seed':job['seed'],
                'mean_density_g_ml':float(density.mean()),'mean_count_030':float(count[:,2].mean()),
                'mean_counts':count.mean(axis=0).tolist(),'mean_nearest_pdf':pdf.mean(axis=0).tolist(),
                'mean_pair_pdf':d['pair_histograms'].mean(axis=0).tolist(),
                'mean_temperature_K':float(temp.mean()),'concentration_mM':cfg['mean_solute_concentration_mM'],
                'first_last_density_change_g_ml':density_drift,'first_last_count_030_change':count_drift,
                'first_last_pdf_tv':pdf_drift,'flags':flags,'blocks':blocks,
                'recomputed_count_frame_indices':checked_frames,
                'correlation_diagnostics':{'count_030':correlation_diagnostic(count[:,2]),'density':correlation_diagnostic(density)},
                'stride_diagnostics':{str(stride):{'count_030':float(count[::stride,2].mean()),'pdf_tv_from_full':tv(pdf[::stride].mean(axis=0),pdf.mean(axis=0))} for stride in plan['diagnostics']['stride_sensitivity']},
                'source_result_sha256':sha(path),'source_trajectory_sha256':r['hashes']['trajectory'],
                'configuration':cfg,'versions':r['versions'],'hashes':r['hashes'],
                'equilibration_samples':r['equilibration_samples'],
                'production_ns_per_day':r['timing']['production_ns_per_day']})
            series[name] = {'density':density.copy(),'count':count[:,2].copy(),'time_ns':d['production_time_ps'].copy()/1000}
    groups = []
    if len(series)!=len(plan['jobs']) or len({r['name'] for r in rows})!=len(rows):
        raise ValueError('Run identifiers must remain unique in tables and plots')
    for compound in ['gly','phe']:
        for ensemble in ['NVT','NPT']:
            selected = [r for r in rows if r['compound']==compound and r['ensemble']==ensemble]
            means = np.array([r['mean_count_030'] for r in selected])
            densities = np.array([r['mean_density_g_ml'] for r in selected])
            groups.append({'compound':compound,'ensemble':ensemble,'n_seeds':len(selected),
                'count_030_mean':float(means.mean()),'count_030_seed_sd':float(means.std(ddof=1)),
                'density_mean_g_ml':float(densities.mean()),'density_seed_sd_g_ml':float(densities.std(ddof=1)),
                'flagged_runs':sum(any(r['flags'].values()) for r in selected)})
    contrasts = []
    for compound in ['gly','phe']:
        pairs=[]
        for seed in sorted({r['seed'] for r in rows}):
            by_ens={r['ensemble']:r for r in rows if r['compound']==compound and r['seed']==seed}
            a,b=by_ens['NVT'],by_ens['NPT']
            pairs.append({'seed':seed,'NPT_minus_NVT_density_g_ml':b['mean_density_g_ml']-a['mean_density_g_ml'],
                'NPT_minus_NVT_count_030':b['mean_count_030']-a['mean_count_030'],
                'nearest_pdf_tv_between_ensembles':tv(a['mean_nearest_pdf'],b['mean_nearest_pdf']),
                'pair_pdf_tv_between_ensembles':tv(a['mean_pair_pdf'],b['mean_pair_pdf'])})
        contrasts.append({'compound':compound,'paired_seed_contrasts':pairs})
    flagged = sum(any(r['flags'].values()) for r in rows)
    result={'status':'Completed exploratory NVT/NPT sensitivity study; no efficacy validation',
        'analysis_versions':{'python':platform.python_version(),'numpy':np.__version__,'matplotlib':matplotlib.__version__},
        'analysis_script_sha256':sha(__file__),
        'deployed_input_sha256':cloud_state['input_sha256'],
        'deployed_input_archive':'data/raw/phase11/deployed-inputs',
        'deployed_source_commit':provenance['deployed_source_commit'],
        'descriptor_version':VERSION,'plan_sha256':sha(ROOT/'data/phase11/stability-plan.json'),
        'trajectories':len(rows),'production_ns':sum(j['production_ps'] for j in plan['jobs'])/1000,
        'experimental_rows_added':0,'flagged_runs':flagged,'groups':groups,'ensemble_contrasts':contrasts,'runs':rows,
        'decision':'Defer compound expansion pending review of stability flags and physical assumptions' if flagged else 'Prespecified short-run flags absent; inspect model sensitivity before any compound expansion',
        'limits':['Thresholds are engineering flags, not statistical convergence guarantees.',
            'Three seeds per condition; frames and time blocks are correlated, not independent experimental samples.',
            'NPT targets pressure but no independent pressure estimator or bulk-water calibration was performed.',
            'Changing volume also changes concentration. Force field, charge state, finite size and no salt remain assumptions.',
            'Neither descriptor nor liquid water MD establishes IRI or cell protection.']}
    write_json(ROOT/'data/phase11/stability-results.json',result)
    write_report(result)
    fig, axes=plt.subplots(2,2,figsize=(11,7),sharex=True)
    for col,compound in enumerate(['gly','phe']):
        for ensemble,color in [('NVT','#2563a6'),('NPT','#b04a38')]:
            for n,r in enumerate([r for r in rows if r['compound']==compound and r['ensemble']==ensemble]):
                s=series[r['name']]
                # Non-overlapping 100 ps means; no confidence band over frames.
                t=np.array([v.mean() for v in np.array_split(s['time_ns'],30)])
                for row,key in enumerate(['density','count']):
                    y=[v.mean() for v in np.array_split(s[key],30)]
                    axes[row,col].plot(t,y,color=color,alpha=.6,lw=1,label=ensemble if n==0 else None)
        axes[0,col].set_title('Glycine' if compound=='gly' else 'L-phenylalanine')
        axes[1,col].set_xlabel('Production time (ns)')
    axes[0,0].set_ylabel('Density (g/mL)'); axes[1,0].set_ylabel('Waters within 0.30 nm')
    for ax in axes.flat:
        ax.spines[['top','right']].set_visible(False); ax.legend(frameon=False,fontsize=8)
    fig.suptitle('Hydration stability: fixed volume versus pressure control')
    fig.text(.5,.02,'3 seeds per condition • Lines show 100 ps means • Liquid-water sensitivity, not cryoprotection efficacy',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,.95)); fig.savefig(ROOT/'reports/hydration-stability.png',dpi=180)
    print(json.dumps({'trajectories':len(rows),'flagged_runs':flagged,'groups':groups}))


if __name__=='__main__':main()
