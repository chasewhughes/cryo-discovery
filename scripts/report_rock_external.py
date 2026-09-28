"""Render the frozen Phase 18 external ROCK2 evaluation without inventing results."""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(path):
    if not path.is_file(): raise FileNotFoundError(f"required file missing: {path}")
    with path.open() as f: value=json.load(f)
    if not isinstance(value,dict): raise ValueError(f"expected JSON object: {path}")
    return value

def finite(x): return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def num(x,label):
    if not finite(x): raise ValueError(f"invalid numeric field {label}")
    return float(x)
def f(x): return 'undefined' if x is None else f"{num(x,'metric'):.3f}"
def pct(x): return 'undefined' if x is None else f"{100*num(x,'fraction'):.1f}%"
def metric_row(label,m):
    need=('n','mae_pIC50','rmse_pIC50','bias_pIC50','baseline_mae_pIC50','mae_improvement_fraction','spearman')
    for k in need:
        if k not in m: raise ValueError(f"metric missing {k}: {label}")
    return f"| {label} | {m['n']} | {f(m['mae_pIC50'])} | {f(m['rmse_pIC50'])} | {f(m['bias_pIC50'])} | {f(m['baseline_mae_pIC50'])} | {pct(m['mae_improvement_fraction'])} | {f(m['spearman'])} |"

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--results',type=Path,default=ROOT/'data/phase18/external-results.json'); ap.add_argument('--costs',type=Path,default=ROOT/'data/phase18/compute-costs.json'); ap.add_argument('--output',type=Path,default=ROOT/'reports/rock2-external-calibration.md'); a=ap.parse_args()
    r=load(a.results); c=load(a.costs)
    for k in ('verdict','validation_errors','analysis','panel_predictions','attempt'):
        if k not in r: raise ValueError(f"results missing {k}")
    errors=r['validation_errors'];
    if not isinstance(errors,list): raise ValueError('validation_errors must be a list')
    analysis=r['analysis']
    if errors:
        verdict='The external evaluation is inconclusive because archived validation failed.'; validation='Archive/output validation did not pass; recorded errors:\n' + '\n'.join(f'- `{e}`' for e in errors); atext='Metrics were not computed because validation failed.'
    else:
        if not isinstance(analysis,dict): raise ValueError('valid results require analysis')
        verdicts={'provisional_prioritization_gate_passed':'The frozen transfer and calibration gates passed.','novel_screening_not_qualified':'The frozen transfer/calibration gates did not jointly pass.'}
        verdict=verdicts.get(r['verdict'],f"Recorded verdict: `{r['verdict']}`."); validation='All 60 predictions passed the archive, provenance and output checks; no validation errors.'; atext=''
    rows=r['panel_predictions'];
    if not isinstance(rows,list): raise ValueError('panel_predictions must be a list')
    if not errors and len(rows)!=30: raise ValueError('valid result must contain 30 panel compounds')
    table=[]
    if not errors:
        for x in rows:
            for k in ('molecule_id','observed_pIC50','panel_mean_pIC50','source_calibrated_pIC50','assay_calibrated_pIC50','split','seed_absolute_difference_pIC50'):
                if k not in x: raise ValueError(f'panel row missing {k}')
            table.append(f"| {x['molecule_id']} | {x['split']} | {f(x['observed_pIC50'])} | {f(x['panel_mean_pIC50'])} | {f(x['source_calibrated_pIC50'])} | {f(x['assay_calibrated_pIC50'])} | {f(x['seed_absolute_difference_pIC50'])} |")
    if not errors:
        full=analysis['full_external']; held=analysis['heldout_external']; cal=analysis['calibration_fit']; checks=analysis['calibration_checks']; boot=analysis['bootstrap']; source=analysis['source_constants']
        for k in ('raw','source_calibrated'):
            if k not in full: raise ValueError(f'full metrics missing {k}')
        for k in ('raw','source_calibrated','assay_calibrated'):
            if k not in held: raise ValueError(f'heldout metrics missing {k}')
        for k in ('full_raw','heldout_assay_calibrated'):
            if k not in boot: raise ValueError(f'bootstrap missing {k}')
        full_lines='\n'.join(metric_row(x,full[x]) for x in ('raw','source_calibrated'))
        held_lines='\n'.join(metric_row(x,held[x]) for x in ('raw','source_calibrated','assay_calibrated'))
        check_lines='\n'.join(f"- `{k}`: {'pass' if v is True else 'fail'}" for k,v in checks.items())
        gate_text=f"Primary transfer gate: **{'PASS' if analysis['primary_transfer_passed'] else 'FAIL'}**. Held-out calibration gate: **{'PASS' if analysis['calibration_gate_passed'] else 'FAIL'}**.\n\nCalibration subset: {cal['n']} compounds; held-out set: 18 compounds. Offset method: {cal['method']}; fitted offset **{f(cal['offset_pIC50'])} pIC50**. The additive correction cannot improve Spearman by construction.\n\nCalibration gate checks:\n\n{check_lines}"
        def interval(block,name):
            vals=boot[block].get('intervals',{}).get(name)
            if vals is None: return 'undefined'
            if not isinstance(vals,list) or len(vals)!=3: raise ValueError(f'missing bootstrap interval {block}/{name}')
            return ', '.join(pct(vals[i]) if name=='mae_improvement_fraction' else f(vals[i]) for i in range(3))
        boot_text=f"- All 30 raw: MAE improvement 2.5th/median/97.5th percentiles **{interval('full_raw','mae_improvement_fraction')}**; Spearman **{interval('full_raw','spearman')}**.\n- Held-out assay-calibrated: MAE improvement **{interval('heldout_assay_calibrated','mae_improvement_fraction')}**; Spearman **{interval('heldout_assay_calibrated','spearman')}**."
        largest=max(rows,key=lambda x:abs(num(x['panel_mean_pIC50'],'prediction')-num(x['observed_pIC50'],'observation')))
        largest_text=f"Largest raw model-mean absolute error: **{largest['molecule_id']}**, {f(abs(largest['panel_mean_pIC50']-largest['observed_pIC50']))} pIC50."
        worst_test=max((x for x in rows if x['split']=='test'),key=lambda x:abs(x['assay_calibrated_pIC50']-x['observed_pIC50']))
        largest_text+=f" The largest calibrated held-out error is **{worst_test['molecule_id']}**, {f(abs(worst_test['assay_calibrated_pIC50']-worst_test['observed_pIC50']))} pIC50; no outlier was excluded."
        gain_bounds=boot['heldout_assay_calibrated']['intervals']['mae_improvement_fraction']
        uncertainty_note=''
        if gain_bounds and gain_bounds[0]<=0<=gain_bounds[2]:
            uncertainty_note='The held-out calibrated improvement interval includes zero and negative values, so these data do not establish a robust improvement over the simple baseline.'
        metrics_text=f'''## Metrics

| Evaluation | n | MAE | RMSE | Bias | Baseline MAE | Improvement | Spearman |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{full_lines}

### Held-out methods

| Method | n | MAE | RMSE | Bias | Calibration-mean MAE | Improvement | Spearman |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{held_lines}

All errors are in pIC50 units. Bias is mean(predicted minus observed); positive bias means predicted potency is too high. The full-panel baseline is the previous assay's frozen mean; the held-out baseline is the mean of the 12 calibration labels. These are different comparisons and their improvement percentages should not be directly compared.

{gate_text}

{largest_text}

On the held-out set, the diagnostic observed-on-calibrated-predicted slope is **{f(held['assay_calibrated']['observed_on_predicted_slope'])}** and intercept is **{f(held['assay_calibrated']['observed_on_predicted_intercept'])}**; ideal values are 1 and 0. These test-set regression coefficients are descriptive and are not fitted into the deployed correction. The calibrated fraction within 0.5 pIC50 is **{pct(held['assay_calibrated']['fraction_within_0_5'])}**.

Bootstrap intervals are paired scaffold-cluster resampling (14 clusters for all rows; the held-out set has 9 clusters). They are descriptive and conditional on the fitted offset; they exclude calibration-fit uncertainty and pretrained-data uncertainty. They must not be read as guaranteeing the point gate: a confidence interval crossing a 20% improvement threshold does not overturn or independently establish the frozen point-estimate decision.

{boot_text}

{uncertainty_note}'''
    else: metrics_text=atext; boot_text='Bootstrap intervals were not computed because validation failed.'; largest_text='Largest outlier was not computed because validation failed.'
    required=('estimated_gpu_usd_all_phases','estimated_gpu_usd_phase18','total_reserve_including_pending_usd','receipted_cumulative_reserve_usd','budget_cap_usd')
    for k in required:
        if k not in c: raise ValueError(f'costs missing {k}')
    if c.get('all_research_pods_absent') is not True: raise ValueError('cost reconciliation does not confirm cleanup')
    plan='data/phase18/external-plan.json'
    h=r.get('plan_sha256')
    if h:
        for q in sorted((ROOT/'data/phase18').glob('external-plan*.json')):
            if hashlib.sha256(q.read_bytes()).hexdigest()==h: plan=str(q.relative_to(ROOT)); break
    source_constants=analysis['source_constants'] if isinstance(analysis,dict) else load(ROOT/'data/phase18/external-dataset.json')['source_constants']
    seed_text=f"Median absolute difference between the two seed predictions: **{f(analysis['median_seed_absolute_difference_pIC50'])} pIC50**." if isinstance(analysis,dict) else 'Seed stability was not computed because validation failed.'
    if errors:
        next_text='Resolve the recorded execution or provenance failure before drawing scientific conclusions; retain this attempt and freeze any revised evaluation separately.'
    elif analysis['primary_transfer_passed'] and analysis['calibration_gate_passed']:
        next_text='The model qualifies for provisional prioritization under these criteria. Before a discovery claim, audit training overlap and test candidates or controls in independent biochemical measurements, including an assay that avoids luciferase interference. Cryoprotection and cell function require separate evidence.'
    else:
        next_text='Keep novel-candidate screening on hold. First test whether the error reflects limited compound ranking, an assay-dependent offset, or readout interference using a separate, preregistered dataset with orthogonal biochemical measurements. A new calibration model would need a fresh held-out test; do not tune on these 18 test compounds and then reuse them as validation.'
    report=f'''# ROCK2 external evaluation and calibration

{c.get('verified_at','')[:10]} • Phase 18 • analyzed attempt {r['attempt']}

{verdict} This is a retrospective cross-publication evaluation of known compounds from Morwick et al. It does not establish that compounds are unseen during pretraining and does not support novelty, CEPT biology, ice inhibition, or prospective efficacy claims.

Boltz-2 version 2.2.1 ran all 30 compounds with fixed seeds 1801 and 1802. Each raw prediction is the arithmetic mean of the two pIC50-equivalent outputs, converted as `6 - affinity_pred_value` from the [documented log10(IC50 in µM) output](https://github.com/jwohlwend/boltz/blob/v2.2.1/docs/prediction.md). No best seed was selected.

{metrics_text}

The primary frozen transfer gate required at least 20% MAE improvement over the Phase 17 source mean and Spearman at least 0.5 across all 30 compounds. The calibration gate required held-out MAE ≤0.5 pIC50, absolute bias ≤0.25 pIC50, ≥20% improvement versus the 12-compound calibration mean, Spearman ≥0.5, and no worse held-out MAE than raw. It was evaluated only after an intercept-only median-residual fit on 12 calibration compounds. No cherry-picking, slope fitting, or best-method selection is permitted.

## Compound-level record

| Molecule | Split | Observed pIC50 | Raw model mean | Source-offset model | Assay-calibrated model | Seed difference |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(table) if table else 'Panel rows were not available because validation failed.'}

## Validation status

{validation}

Any validation error makes the primary and calibration conclusions inconclusive; no successful subset is selected. A failed calibration gate means this frozen setup does not qualify for screening, regardless of any descriptive raw or calibrated metric.

## Assay and provenance limits

The source is [CHEMBL1071707](https://www.ebi.ac.uk/chembl/api/data/assay/CHEMBL1071707.json), from the primary [Morwick et al. paper](https://doi.org/10.1021/jm9014263) and [ACS supporting information](https://acs.figshare.com/articles/journal_contribution/Hit_to_Lead_Account_of_the_Discovery_of_Bisbenzamide_and_Related_Ureidobenzamide_Inhibitors_of_Rho_Kinase/2796493). It measured ROCK2(1–543) inhibition using 750 nM ATP, 500 nM AKRRRLSSLRA peptide, 90 minutes at 28 °C, and a luciferase readout. The SI separately reports IMAP at 100 µM ATP. Luciferase detection-enzyme interference was reported for some dimethylaminomethylphenyl analogues, so absolute accuracy remains assay-sensitive. Phase 17 used CHEMBL4328667 with 100 µM ATP and residues 11–552; these are separate assay contexts. The model retains the Phase 17 542-residue sequence, 512-row MSA, and unforced partial 6ED6 template. Assay ATP, substrate and readout are not explicit physical inputs to the model. The source audit documents 17 unit corrections and exclusion of both ambiguous CHEMBL604249 rows. The frozen source mean is **{f(source_constants['source_mean_pIC50'])} pIC50** and source-only residual offset is **{f(source_constants['source_median_residual_offset_pIC50'])} pIC50**.

All 30 rows are included in the frozen external dataset; the 12/18 calibration/test partition is scaffold-disjoint (5 calibration and 9 test scaffolds). No molecule ID, canonical isomeric structure or achiral structure matches Phase 17. Labels were accessible for source auditing, so this is not a blinded benchmark. Some source compounds are racemic or have unspecified stereochemistry; a predicted ligand structure does not explicitly model a racemic mixture. The known 2010 series may overlap pretraining. See [assay review](../data/phase18/assay-review.json), [source-table reconciliation](../data/phase18/source-table-reconciliation.json), and [external dataset](../data/phase18/external-dataset.json).

The [Boltz-2 paper](https://jeremywohlwend.com/assets/boltz2.pdf) names ChEMBL among its affinity-training sources. Its documented filters do not establish whether this particular assay or target was retained. The [training-overlap audit](../data/phase18/pretraining-overlap-review.json) therefore records exact membership as unknown; the structural PDB date cutoff does not establish affinity-data independence.

## Next step

{next_text}

## Reproduction and diagnostic figures

With the locally archived sources and result archive present, these commands verify and regenerate the analysis without renting compute. The raw files are excluded from Git; a fresh clone alone is insufficient.

```sh
.venv/bin/python -m unittest tests.test_analyze_rock_external tests.test_boltz_external_inference tests.test_runpod_boltz_external tests.test_reconcile_phase18
.venv/bin/python scripts/analyze_rock_external.py --attempt {r['attempt']}
.venv/bin/python scripts/plot_rock_external.py
python3 scripts/report_rock_external.py
```

{chr(10).join(f'![{p.stem.replace("-", " ")}](figures/{p.name})' for p in sorted((ROOT / 'reports/figures').glob('rock2-external*.png')))}

## Compute and cleanup

{seed_text} The executed plan was [external-plan]({('../'+plan) if plan.startswith('data/') else plan}). Seed differences measure limited model stochasticity, not independent physical replicate uncertainty.

Reconciled records report **${c['estimated_gpu_usd_phase18']:.4f}** Phase 18 estimate, **${c['estimated_gpu_usd_all_phases']:.4f}** all-phase estimate, **${c['total_reserve_including_pending_usd']:.4f}** total reserve including pending intents, and **${c['receipted_cumulative_reserve_usd']:.4f}** receipted reserve against the **${c['budget_cap_usd']:.2f}** cap. All research Pods are recorded absent. These are estimates, not final invoices.

The [machine-readable result](../data/phase18/external-results.json) and [cost reconciliation](../data/phase18/compute-costs.json) preserve the frozen execution evidence. Any further experiment needs a new frozen plan and fresh cumulative billing reconciliation.
'''
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(report);print(f'Wrote {a.output}')
if __name__=='__main__':
    try: main()
    except (FileNotFoundError,ValueError,json.JSONDecodeError) as e: raise SystemExit(f'error: {e}')
