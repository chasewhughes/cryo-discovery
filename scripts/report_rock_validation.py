"""Render the frozen Phase 20 validation ROCK2 evaluation without inventing results."""
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

def comparison_table(current):
    specs=[('Phase 17','data/phase17/panel-results.json','metrics.full','HTRF; 100 µM ATP; human ROCK2 11–552'),
           ('Phase 18','data/phase18/external-results.json','analysis.full_external.raw','luciferase; 750 nM ATP; human ROCK2 1–543'),
           ('Phase 20','data/phase20/validation-results.json','analysis.full_validation.raw','radiometric; 10 µM ATP; current provider protocol; 2019 lot uncertain')]
    rows=[]
    for label,path,field,assay in specs:
        try:
            data=load(ROOT/path)
            value=data
            for key in field.split('.'): value=value[key]
            rows.append(f"| {label} | {value.get('n','—')} | {f(value.get('panel_mae_pIC50',value.get('mae_pIC50'))) } | {f(value.get('spearman'))} | {assay} | {data.get('verdict','—')} |")
        except (FileNotFoundError,ValueError,KeyError,TypeError):
            rows.append(f"| {label} | — | undefined | undefined | {assay} | unavailable/inconclusive |")
    return "## Across-phase descriptive comparison\n\n| Phase | n | Raw MAE | Raw Spearman | Assay context | Recorded verdict |\n| --- | ---: | ---: | ---: | --- | --- |\n"+'\n'.join(rows)+"\n\nThese rows are descriptive only. Baselines differ across phases, and compound series, ATP, construct, readout, and lot are confounded; the table does not support pooled gains or causal attribution to readout. Interpret each phase under its frozen decision rules."

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--results',type=Path,default=ROOT/'data/phase20/validation-results.json'); ap.add_argument('--costs',type=Path,default=ROOT/'data/phase20/compute-costs.json'); ap.add_argument('--output',type=Path,default=ROOT/'reports/rock2-radiometric-validation.md'); a=ap.parse_args()
    r=load(a.results); c=load(a.costs)
    for k in ('verdict','validation_errors','analysis','panel_predictions','attempt'):
        if k not in r: raise ValueError(f"results missing {k}")
    errors=r['validation_errors'];
    if not isinstance(errors,list): raise ValueError('validation_errors must be a list')
    analysis=r['analysis']
    if errors:
        verdict='The validation evaluation is inconclusive because archived validation failed.'; validation='Archive/output validation did not pass; recorded errors:\n' + '\n'.join(f'- `{e}`' for e in errors); atext='Metrics were not computed because validation failed.'
    else:
        if not isinstance(analysis,dict): raise ValueError('valid results require analysis')
        verdicts={'provisional_prioritization_gate_passed':'The frozen transfer and calibration gates passed.','novel_screening_not_qualified':'The frozen transfer/calibration gates did not jointly pass.'}
        verdict=verdicts.get(r['verdict'],f"Recorded verdict: `{r['verdict']}`."); validation='All 100 expected predictions passed the archive, provenance and output checks; no validation errors.'; atext=''
    rows=r['panel_predictions'];
    if not isinstance(rows,list): raise ValueError('panel_predictions must be a list')
    if not errors and len(rows)!=50: raise ValueError('valid result must contain 50 panel compounds')
    table=[]
    if not errors:
        for x in rows:
            for k in ('molecule_id','observed_pIC50','panel_mean_pIC50','source_calibrated_pIC50','assay_calibrated_pIC50','split','seed_absolute_difference_pIC50'):
                if k not in x: raise ValueError(f'panel row missing {k}')
            table.append(f"| {x['molecule_id']} | {x['split']} | {f(x['observed_pIC50'])} | {f(x['panel_mean_pIC50'])} | {f(x['source_calibrated_pIC50'])} | {f(x['assay_calibrated_pIC50'])} | {f(x['seed_absolute_difference_pIC50'])} |")
    if not errors:
        full=analysis['full_validation']; held=analysis['heldout_validation']; cal=analysis['calibration_fit']; checks=analysis['calibration_checks']; boot=analysis['bootstrap']; source=analysis['source_constants']
        for k in ('raw','source_calibrated'):
            if k not in full: raise ValueError(f'full metrics missing {k}')
        for k in ('raw','source_calibrated','assay_calibrated'):
            if k not in held: raise ValueError(f'heldout metrics missing {k}')
        for k in ('full_raw','heldout_assay_calibrated'):
            if k not in boot: raise ValueError(f'bootstrap missing {k}')
        full_lines='\n'.join(metric_row(x,full[x]) for x in ('raw','source_calibrated'))
        held_lines='\n'.join(metric_row(x,held[x]) for x in ('raw','source_calibrated','assay_calibrated'))
        check_lines='\n'.join(f"- `{k}`: {'pass' if v is True else 'fail'}" for k,v in checks.items())
        gate_text=f"Primary transfer gate: **{'PASS' if analysis['primary_transfer_passed'] else 'FAIL'}**. Held-out calibration gate: **{'PASS' if analysis['calibration_gate_passed'] else 'FAIL'}**.\n\nCalibration subset: {cal['n']} compounds; held-out set: 30 compounds. Offset method: {cal['method']}; fitted offset **{f(cal['offset_pIC50'])} pIC50**. The additive correction cannot improve Spearman by construction.\n\nCalibration gate checks:\n\n{check_lines}"
        def interval(block,name):
            vals=boot[block].get('intervals',{}).get(name)
            if vals is None: return 'undefined'
            if not isinstance(vals,list) or len(vals)!=3: raise ValueError(f'missing bootstrap interval {block}/{name}')
            return ', '.join(pct(vals[i]) if name=='mae_improvement_fraction' else f(vals[i]) for i in range(3))
        boot_text=f"- All 50 raw: MAE improvement 2.5th/median/97.5th percentiles **{interval('full_raw','mae_improvement_fraction')}**; Spearman **{interval('full_raw','spearman')}**.\n- Held-out assay-calibrated: MAE improvement **{interval('heldout_assay_calibrated','mae_improvement_fraction')}**; Spearman **{interval('heldout_assay_calibrated','spearman')}**."
        largest=max(rows,key=lambda x:abs(num(x['panel_mean_pIC50'],'prediction')-num(x['observed_pIC50'],'observation')))
        largest_text=f"Largest raw model-mean absolute error: **{largest['molecule_id']}**, {f(abs(largest['panel_mean_pIC50']-largest['observed_pIC50']))} pIC50."
        worst_test=max((x for x in rows if x['split']=='test'),key=lambda x:abs(x['assay_calibrated_pIC50']-x['observed_pIC50']))
        largest_text+=f" The largest calibrated held-out error is **{worst_test['molecule_id']}**, {f(abs(worst_test['assay_calibrated_pIC50']-worst_test['observed_pIC50']))} pIC50; no outlier was excluded."
        gain_bounds=boot['heldout_assay_calibrated']['intervals']['mae_improvement_fraction']
        uncertainty_note=''
        if gain_bounds and gain_bounds[0]<=0<=gain_bounds[2]:
            uncertainty_note='The held-out calibrated improvement interval includes zero and negative values, so these data do not establish a robust improvement over the simple baseline.'
        cal_y=[x['observed_pIC50'] for x in rows if x['split']=='calibration']; test_y=[x['observed_pIC50'] for x in rows if x['split']=='test']
        bias_gap=abs(held['assay_calibrated']['bias_pIC50'])-.25
        specificity=f"Raw transfer passed on all 50 compounds, while the held-out calibration missed only the absolute-bias check by {f(bias_gap)} pIC50. This is a small threshold miss, not evidence of a sharp scientific boundary. The frozen joint decision remains unqualified." if analysis['primary_transfer_passed'] and sum(v is False for v in checks.values())==1 and checks.get('absolute_bias_at_most_limit') is False else ''
        calibration_context=f"The fixed scaffold partition also shifted the observed potency distribution: calibration mean {f(sum(cal_y)/len(cal_y))}, held-out mean {f(sum(test_y)/len(test_y))} pIC50. This helps explain why the calibration-mean baseline is weak on the test set; large percentage improvements must be read alongside absolute error and ranking. It does not isolate the cause of residual bias. The source-only offset performs better here, but choosing it after inspecting test results cannot replace the prespecified assay-calibration gate."
        finite_rank=boot['heldout_assay_calibrated']['finite_resamples']['spearman']
        rank_note=f"Held-out Spearman was defined in {finite_rank} of {boot['heldout_assay_calibrated']['resamples']} bootstrap draws; undefined draws were omitted from its displayed percentiles. With only three test scaffolds, these intervals have limited resolution."
        metrics_text=f'''{specificity}

## Metrics

| Evaluation | n | MAE | RMSE | Bias | Baseline MAE | Improvement | Spearman |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{full_lines}

### Held-out methods

| Method | n | MAE | RMSE | Bias | Calibration-mean MAE | Improvement | Spearman |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{held_lines}

All errors are in pIC50 units. Bias is mean(predicted minus observed); positive bias means predicted potency is too high. The full-panel baseline is the previous assay's frozen mean; the held-out baseline is the mean of the 20 calibration labels. These are different comparisons and their improvement percentages should not be directly compared.

{gate_text}

{calibration_context}

{largest_text}

On the held-out set, the diagnostic observed-on-calibrated-predicted slope is **{f(held['assay_calibrated']['observed_on_predicted_slope'])}** and intercept is **{f(held['assay_calibrated']['observed_on_predicted_intercept'])}**; ideal values are 1 and 0. These test-set regression coefficients are descriptive and are not fitted into the deployed correction. The calibrated fraction within 0.5 pIC50 is **{pct(held['assay_calibrated']['fraction_within_0_5'])}**.

Bootstrap intervals are paired scaffold-cluster resampling (14 clusters for all rows; the held-out set has only 3 clusters). They are descriptive and conditional on the fitted offset; they exclude calibration-fit uncertainty and pretrained-data uncertainty. They must not be read as guaranteeing the point gate: a confidence interval crossing a 20% improvement threshold does not overturn or independently establish the frozen point-estimate decision.

{boot_text}

{rank_note}

{uncertainty_note}'''
    else: metrics_text=atext; boot_text='Bootstrap intervals were not computed because validation failed.'; largest_text='Largest outlier was not computed because validation failed.'
    required=('estimated_gpu_usd_all_phases','estimated_gpu_usd_phase20','total_reserve_including_pending_usd','receipted_cumulative_reserve_usd','budget_cap_usd')
    for k in required:
        if k not in c: raise ValueError(f'costs missing {k}')
    if c.get('all_research_pods_absent') is not True: raise ValueError('cost reconciliation does not confirm cleanup')
    plan='data/phase20/validation-plan.json'
    h=r.get('plan_sha256')
    if h:
        for q in sorted((ROOT/'data/phase20').glob('validation-plan*.json')):
            if hashlib.sha256(q.read_bytes()).hexdigest()==h: plan=str(q.relative_to(ROOT)); break
    source_constants=analysis['source_constants'] if isinstance(analysis,dict) else load(ROOT/'data/phase20/validation-dataset.json')['source_constants']
    comparison_text=comparison_table(r)
    seed_text=f"Median absolute difference between the two seed predictions: **{f(analysis['median_seed_absolute_difference_pIC50'])} pIC50**." if isinstance(analysis,dict) else 'Seed stability was not computed because validation failed.'
    if errors:
        next_text='Resolve the recorded execution or provenance failure before drawing scientific conclusions; retain this attempt and freeze any revised evaluation separately.'
    elif analysis['primary_transfer_passed'] and analysis['calibration_gate_passed']:
        next_text='The model qualifies for provisional prioritization under these criteria. Before a discovery claim, audit training overlap and test candidates or controls in independent biochemical measurements, including an assay that avoids luciferase interference. Cryoprotection and cell function require separate evidence.'
    else:
        next_text='Keep novel screening unqualified under the frozen joint gate. The useful next study is a prespecified calibration-transfer evaluation with broader independent scaffold coverage and an assay-matched reference set. The raw ranking signal justifies testing that question; this small bias miss does not justify changing the threshold or selecting the better source offset after seeing test results. Any revised calibration or model must be frozen and evaluated on fresh held-out data. Preserve the weaker Phase 18 result and make no efficacy claim from these retrospective assays.'
    report=f'''# ROCK2 validation evaluation and calibration

{c.get('verified_at','')[:10]} • Phase 20 • analyzed attempt {r['attempt']}

{verdict} This is a retrospective validation of a known 2019 chromen series in an orthogonal ROCK2 assay. It does not establish that compounds are unseen during pretraining and does not support novelty, cryoprotection, cell function, or prospective efficacy claims.

Boltz-2 version 2.2.1 ran all 50 compounds with fixed seeds 2001 and 2002. Each raw prediction is the arithmetic mean of the two pIC50-equivalent outputs, converted as `6 - affinity_pred_value` from the [documented log10(IC50 in µM) output](https://github.com/jwohlwend/boltz/blob/v2.2.1/docs/prediction.md). No best seed was selected.

{metrics_text}

{comparison_text}

The primary frozen transfer gate required at least 20% MAE improvement over the Phase 17 source mean and Spearman at least 0.5 across all 50 compounds. The calibration gate required held-out MAE ≤0.5 pIC50, absolute bias ≤0.25 pIC50, ≥20% improvement versus the 20-compound calibration mean, Spearman ≥0.5, and no worse held-out MAE than raw. It was evaluated only after an intercept-only median-residual fit on 20 calibration compounds. No cherry-picking, slope fitting, or best-method selection is permitted.

## Compound-level record

| Molecule | Split | Observed pIC50 | Raw model mean | Source-offset model | Assay-calibrated model | Seed difference |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(table) if table else 'Panel rows were not available because validation failed.'}

## Validation status

{validation}

Any validation error makes the primary and calibration conclusions inconclusive; no successful subset is selected. A failed calibration gate means this frozen setup does not qualify for screening, regardless of any descriptive raw or calibrated metric.

## Assay and provenance limits

The source search inventoried 763 ChEMBL ROCK2 assays and retrieved 54 literature assays whose descriptions contained non-luciferase method keywords. These database annotations were screening leads, not verified protocols. The 2019 chromen source was selected because its author-supplied CSV allowed complete structure and potency reconciliation, supported by published assay details and provider documentation. The 2013 urea paper was also acquired but still required manual structure reconciliation. No new model outputs were used in source selection. See the [source inventory](../data/phase20/orthogonal-source-inventory.json) and [identity/split audit](../data/phase20/inventory-identity-audit.json).

The source is the primary [2019 J. Med. Chem. article](https://doi.org/10.1021/acs.jmedchem.9b01143), its [official supporting information](https://ndownloader.figshare.com/files/19066013), and the [supporting-data CSV](https://ndownloader.figshare.com/files/19066016). The audited source table contains 57 records: 50 exact labels and 7 censored records; the frozen validation split contains 20 calibration and 30 test compounds across 14 scaffolds. The [current Eurofins protocol](https://www.eurofinsdiscovery.com/catalog/rock2-human-agc-kinase-enzymatic-radiometric-10-um-atp-leadhunter-fr/14-451KP10) corroborates the historical method, but cannot certify the identity of the historical 2019 reagent lot, so this comparison does not establish current-lot reproducibility. The model retains the Phase 17 542-residue sequence, 512-row MSA, and unforced partial 6ED6 template; assay ATP, substrate, readout, and lot are not explicit physical inputs. The frozen source mean is **{f(source_constants['source_mean_pIC50'])} pIC50** and source-only residual offset is **{f(source_constants['source_median_residual_offset_pIC50'])} pIC50**.

All 50 exact rows are included in the frozen validation dataset; the 20/30 calibration/test partition is scaffold-disjoint across 14 total scaffolds, with 11 calibration scaffolds but only 3 held-out scaffolds (group sizes 27, 2 and 1). Thus 27 of the 30 test compounds share one scaffold, and confidence intervals reflect limited independent structural diversity despite 30 test compounds. Seven censored records remain excluded from exact-label scoring. No molecule ID, canonical isomeric structure or achiral structure matches Phase 17 or Phase 18. Labels were accessible for source auditing, so this is not a blinded benchmark. Pretraining independence is unknown, and this assay cannot support claims about cryoprotection, cell function, or biological efficacy. See [2019 source audit](../data/phase20/rock2-2019-source-audit.json), [source-table reconciliation](../data/phase20/source-table-reconciliation.json), and [validation dataset](../data/phase20/validation-dataset.json).

The [Boltz-2 paper](https://jeremywohlwend.com/assets/boltz2.pdf) names ChEMBL among its affinity-training sources. Its documented filters do not establish whether this particular assay or target was retained. The prior phase overlap review records exact membership as unknown; no pretraining independence claim is made.

## Next step

{next_text}

See the [decision rules recorded before results](../docs/rock2-validation-decision-rules.md).

## Reproduction and diagnostic figures

With the locally archived sources and result archive present, these commands verify and regenerate the analysis without renting compute. The raw files are excluded from Git; a fresh clone alone is insufficient.

```sh
.venv/bin/python -m unittest tests.test_analyze_rock_validation tests.test_boltz_validation_inference tests.test_runpod_boltz_validation tests.test_reconcile_phase20
.venv/bin/python scripts/analyze_rock_validation.py --attempt {r['attempt']}
.venv/bin/python scripts/plot_rock_validation.py
python3 scripts/report_rock_validation.py
```

{chr(10).join(f'![{p.stem.replace("-", " ")}](figures/{p.name})' for p in sorted((ROOT / 'reports/figures').glob('rock2-validation*.png')))}

## Compute and cleanup

{seed_text} The executed plan was [validation-plan]({('../'+plan) if plan.startswith('data/') else plan}). Seed differences measure limited model stochasticity, not independent physical replicate uncertainty.

Reconciled records report **${c['estimated_gpu_usd_phase20']:.4f}** Phase 20 estimate, **${c['estimated_gpu_usd_all_phases']:.4f}** all-phase estimate, **${c['total_reserve_including_pending_usd']:.4f}** total reserve including pending intents, and **${c['receipted_cumulative_reserve_usd']:.4f}** receipted reserve against the **${c['budget_cap_usd']:.2f}** cap. All research Pods are recorded absent. These are estimates, not final invoices.

The [machine-readable result](../data/phase20/validation-results.json), [independent metric review](../data/phase20/independent-results-review.json), and [cost reconciliation](../data/phase20/compute-costs.json) preserve the frozen execution evidence. Any further experiment needs a new frozen plan and fresh cumulative billing reconciliation.
'''
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(report);print(f'Wrote {a.output}')
if __name__=='__main__':
    try: main()
    except (FileNotFoundError,ValueError,json.JSONDecodeError) as e: raise SystemExit(f'error: {e}')
