"""Render the frozen ROCK2 panel result and reconciled costs without recomputing inference."""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_required(path):
    if not path.is_file():
        raise FileNotFoundError(f"required file missing: {path}")
    with path.open() as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"required JSON object missing: {path}")
    return value


def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"invalid numeric field {label}")
    return float(value)


def fmt(value, digits=3):
    if value is None:
        return 'Undefined'
    return f"{number(value, 'report value'):.{digits}f}"


def pct(value):
    return f"{100 * number(value, 'percentage'):.1f}%"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=ROOT / 'data/phase17/panel-results.json')
    parser.add_argument('--costs', type=Path, default=ROOT / 'data/phase17/compute-costs.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/rock2-panel-benchmark.md')
    args = parser.parse_args()
    results = load_required(args.results)
    costs = load_required(args.costs)

    for key in ('verdict', 'validation_errors', 'metrics', 'bootstrap', 'panel_predictions', 'seeds', 'attempt'):
        if key not in results:
            raise ValueError(f"results missing field: {key}")
    errors = results['validation_errors']
    if not isinstance(errors, list):
        raise ValueError('results validation_errors must be a list')
    metrics = results['metrics']
    bootstrap = results['bootstrap']
    rows = results['panel_predictions']
    if not isinstance(rows, list):
        raise ValueError('results panel_predictions must be a list')

    verdict = results['verdict']
    if errors:
        verdict_text = 'The archived panel result is inconclusive because validation failed.'
        error_text = '\n'.join(f'- `{str(error)}`' for error in errors)
    elif verdict == 'supported_internal_benchmark':
        verdict_text = 'The frozen internal benchmark hypothesis was supported under the prespecified thresholds.'
        error_text = f"All {len(rows) * len(results['seeds'])} predictions passed archive, provenance and output checks; no validation errors."
    elif verdict == 'not_supported_internal_benchmark':
        verdict_text = 'The frozen internal benchmark hypothesis was not supported under the prespecified thresholds.'
        error_text = f"All {len(rows) * len(results['seeds'])} predictions passed archive, provenance and output checks; no validation errors."
    else:
        verdict_text = f'The recorded scientific conclusion is `{verdict}`; it is not a successful benchmark claim.'
        error_text = '- None.'

    if not errors and not isinstance(metrics, dict):
        raise ValueError('valid results must contain metrics')
    full = metrics.get('full') if isinstance(metrics, dict) else None
    per_seed = metrics.get('per_seed', {}) if isinstance(metrics, dict) else {}
    anchor = metrics.get('anchor_excluded') if isinstance(metrics, dict) else None
    if not errors and (not isinstance(full, dict) or not isinstance(anchor, dict) or not isinstance(per_seed, dict)):
        raise ValueError('metrics missing full, per_seed, or anchor_excluded')

    def metric_line(label, m):
        return (f"| {label} | {m['n']} | {fmt(m['panel_mae_pIC50'])} | {fmt(m['mean_control_mae_pIC50'])} | "
                f"{fmt(m['neighbor_baseline_mae_pIC50'])} | {pct(m['mae_improvement_fraction'])} | {fmt(m['spearman'])} |")

    rows_out = []
    for row in rows:
        for key in ('molecule_id', 'observed_pIC50', 'panel_mean_pIC50', 'baseline_predicted_pIC50', 'panel_seed_pIC50', 'seed_absolute_difference_pIC50'):
            if key not in row:
                raise ValueError(f"panel row missing field: {key}")
        rows_out.append(
            f"| {row['molecule_id']} | {fmt(row['observed_pIC50'])} | {fmt(row['panel_mean_pIC50'])} | "
            f"{fmt(row['baseline_predicted_pIC50'])} | {fmt(row['seed_absolute_difference_pIC50'])} |"
        )

    timings = '; '.join(f"seed {s['seed']}: {s['wall_seconds']/60:.1f} minutes" for s in results['seeds'] if isinstance(s.get('wall_seconds'), (int,float)))
    seed_lines = []
    for seed, m in sorted(per_seed.items(), key=lambda item: str(item[0])):
        seed_lines.append(metric_line(f"Seed {seed}", m))

    def interval(name):
        values = bootstrap.get(name) if isinstance(bootstrap, dict) else None
        if not isinstance(values, list) or len(values) != 3:
            return 'not computed because validation failed'
        return f"{fmt(values[0])}, {fmt(values[1])}, {fmt(values[2])}"

    def cost(key):
        return f"${number(costs[key], key):.4f}"

    required_costs = ('estimated_gpu_usd_all_phases', 'estimated_gpu_usd_phase17',
                      'total_reserve_including_pending_usd', 'receipted_cumulative_reserve_usd',
                      'budget_cap_usd')
    for key in required_costs:
        if key not in costs:
            raise ValueError(f"costs missing field: {key}")
    if costs.get('all_research_pods_absent') is not True:
        raise ValueError('costs do not confirm cleanup')

    attempt_records = []
    for path in sorted((ROOT / 'data/phase17').glob('attempt*-provisioning-rejection.json')):
        item = load_required(path)
        attempt_records.append({'attempt': item.get('attempt', path.stem),
                                'outcome': item.get('decision', item.get('reason', 'rejected before allocation')),
                                'estimated_gpu_usd': 0.0, 'deleted': None})
    for path in sorted((ROOT / 'data/phase17').glob('runpod-attempt*-receipt.json')):
        item = load_required(path)
        amount = item.get('estimated_gpu_cost_usd', item.get('estimated_gpu_usd'))
        if amount is None:
            raise ValueError(f"receipt missing GPU estimate: {path}")
        attempt_records.append({'attempt': item.get('attempt', path.stem),
                                'outcome': item.get('worker_state', item.get('status', 'completed')),
                                'estimated_gpu_usd': amount, 'deleted': item.get('deleted')})
    if not attempt_records:
        raise ValueError('no Phase 17 attempt records found')
    attempt_records.sort(key=lambda item: str(item['attempt']))
    attempt_lines = []
    for item in attempt_records:
        deleted = 'Confirmed' if item['deleted'] is True else ('Not applicable' if item['deleted'] is None else 'Unconfirmed')
        attempt_lines.append(f"| {item['attempt']} | {item['outcome']} | ${number(item['estimated_gpu_usd'], 'attempt cost'):.4f} | {deleted} |")

    executed_plan = 'data/phase17/panel-plan-4090.json'
    result_plan_hash = results.get('plan_sha256')
    if result_plan_hash:
        for candidate in sorted((ROOT / 'data/phase17').glob('panel-plan*.json')):
            import hashlib
            if hashlib.sha256(candidate.read_bytes()).hexdigest() == result_plan_hash:
                executed_plan = str(candidate.relative_to(ROOT))
                break

    figure = '![Measured potency and seed comparison](figures/rock2-panel-benchmark.png)' if (ROOT/'reports/figures/rock2-panel-benchmark.png').exists() and not errors else ''
    outlier_text = ''
    if rows and not errors:
        worst = max(rows, key=lambda row: abs(row['observed_pIC50'] - row['panel_mean_pIC50']))
        observed_nm = 10 ** (9 - worst['observed_pIC50'])
        predicted_nm = 10 ** (9 - worst['panel_mean_pIC50'])
        fold_error = 10 ** abs(worst['observed_pIC50'] - worst['panel_mean_pIC50'])
        outlier_text = (f"The largest error was {worst['molecule_id']}: measured IC50 **{observed_nm:,.0f} nM** "
                        f"versus predicted IC50-equivalent **{predicted_nm:.2f} nM**, approximately **{fold_error:.0f}-fold** apart. "
                        "This compound remains in all applicable metrics; the error motivates further calibration and validation.")
    improvement_bounds = bootstrap.get('mae_improvement_fraction') if isinstance(bootstrap, dict) else None
    uncertainty_text = 'The 20% improvement criterion applies to the frozen point estimate.'
    if isinstance(improvement_bounds, list) and len(improvement_bounds) == 3:
        uncertainty_text += f" The descriptive improvement interval is {pct(improvement_bounds[0])}–{pct(improvement_bounds[2])}."
        if improvement_bounds[0] < 0.2 <= improvement_bounds[2]:
            uncertainty_text += ' It includes values below 20%, so scaffold resampling does not robustly establish a margin of at least 20% even within this series.'
    report = f'''# ROCK2 Boltz panel benchmark

{costs['verified_at'][:10]} • analyzed attempt {results['attempt']}

{verdict_text} The prespecified hypothesis required at least 20% MAE improvement over the preserved training-fold mean baseline and Spearman correlation at least 0.5 across all 43 exact compounds. This is retrospective evidence from one known medicinal-chemistry assay, not external validation, prospective generalization, or a biological efficacy claim.

## Primary result

| Evaluation | n | Model MAE (pIC50) | Mean baseline MAE | Nearest-neighbor MAE | Model improvement vs mean | Spearman |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{metric_line('Two-seed model mean', full) if isinstance(full, dict) else 'Metrics were not computed because validation failed.'}

The model prediction is the arithmetic mean of the two fixed seed outputs after conversion to pIC50-equivalent (`6 − affinity_pred_value`), following [Boltz’s documented output units](https://github.com/jwohlwend/boltz/blob/v2.2.1/docs/prediction.md); no best seed or post-hoc offset was selected. The nearest-neighbor column is descriptive context from the preserved baseline. The right-censored `>10 µM` compound is excluded from exact-value regression as frozen.

## Per-seed and stability results

Recorded invocation times: {timings or 'unavailable'}. The first invocation includes reference-data and weight downloads; these are not pure GPU inference timings.

| Run | n | Model MAE | Mean baseline MAE | Nearest-neighbor MAE | Improvement | Spearman |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(seed_lines) if seed_lines else 'Per-seed metrics were not computed because validation failed.'}

Median absolute difference between the two seed predictions: **{fmt(metrics.get('median_seed_absolute_difference_pIC50')) if isinstance(metrics, dict) and metrics.get('median_seed_absolute_difference_pIC50') is not None else 'not computed because validation failed'} pIC50**.

Anchor-excluded sensitivity removes CHEMBL4522042, the compound linked to the 6ED6 structure. It is reported separately and does not change the frozen primary criterion:

| Evaluation | n | Model MAE (pIC50) | Mean baseline MAE | Nearest-neighbor MAE | Model improvement vs mean | Spearman |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{metric_line('42-compound anchor-excluded', anchor) if isinstance(anchor, dict) else 'Anchor-excluded metrics were not computed because validation failed.'}

The scaffold bootstrap resamples the 13 complete scaffold clusters with paired predictions and baseline values. Its percentile intervals are descriptive within this single series, not uncertainty intervals for external generalization:

- MAE improvement fraction, 2.5th / median / 97.5th percentiles: **{interval('mae_improvement_fraction')}**.
- Spearman, 2.5th / median / 97.5th percentiles: **{interval('spearman')}**.

{uncertainty_text}

{outlier_text}

## Compound-level predictions

| Molecule | Observed pIC50 | Two-seed model mean | Nearest-neighbor baseline | Seed absolute difference |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(rows_out)}

## Validation status

{error_text}

If validation errors are present, the scientific conclusion is **inconclusive** and no successful subset is selected. A `not_supported_internal_benchmark` verdict means the complete archived panel ran and the prespecified thresholds were not met; it is evidence against this frozen hypothesis under this setup, not evidence that Boltz cannot predict ROCK2 activity generally.

## Assay and structural scope

The measured labels retain [ChEMBL attribution and CC BY-SA 3.0 provenance](../data/phase15/rock-benchmark.json). The 43 exact labels come from CHEMBL4328667, a single ROCK2 enzyme assay associated with [Hobson et al.](https://doi.org/10.1021/acs.jmedchem.8b01098). The source audit independently maps 11 Table 1 compounds; 32 remaining labels retain their same-assay ChEMBL provenance without a claimed article compound-number mapping. CHEMBL4328667 assays GST-fused human ROCK2 residues 11–552. The routine potency assay used 100 µM ATP, 0.2 µM STK S2 peptide and 0.5 nM ROCK2 for 60 minutes, followed by HTRF detection. The initial discovery screen used radiometric 33P; the routine HTRF procedure is specified separately in the [supporting information](https://acs.figshare.com/articles/journal_contribution/Identification_of_Selective_Dual_ROCK1_and_ROCK2_Inhibitors_Using_Structure-Based_Drug_Design/7458515).

The model uses the corresponding 542-residue human sequence without the GST fusion, a 512-row MSA, and an unforced partial 6ED6 protein template. ATP, peptide and the experimental assay conditions are not explicit physical inputs to inference. The deposited template sequence includes the ROCK2 residues 27–417 core plus an N-terminal purification tag; this sequence audit does not assert that every residue has resolved coordinates. These construct differences limit correspondence between the model and the experimental assay.

The medicinal-chemistry series, its structure-linked ligand, and pretrained model data may overlap. The preserved baseline uses scaffold-grouped folds; Boltz itself is pretrained and is not refit within those folds, so the split cannot establish independence from model pretraining. Predictions are enzyme IC50 model outputs, not Kd, cell activity, ice inhibition, CPA permeability, CEPT mixture efficacy, post-thaw viability, or evidence of a new compound.

## Next scientific gate

After the complete panel result, the next gate is a preregistered evaluation on an independent ROCK2 assay dataset with construct and endpoint metadata, plus calibration analysis on held-out measurements. The [candidate external-assay inventory](../data/phase17/external-benchmark-candidates.json) identifies separate publications, but these older data may also overlap model training; new measurements or a training-overlap audit remain necessary for an unseen-data claim. Any further GPU run needs its own frozen evaluation and a fresh reconciliation under the existing $10 cumulative limit. These affinity results do not establish CEPT effects or biological efficacy.

{figure}

## Compute and cleanup

| Phase 17 attempt | Outcome | Estimated GPU cost | Pod deletion |
| --- | --- | ---: | --- |
{chr(10).join(attempt_lines)}

Reconciled cost records report **{cost('estimated_gpu_usd_phase17')}** for Phase 17, **{cost('estimated_gpu_usd_all_phases')}** cumulative estimated GPU spending, **{cost('total_reserve_including_pending_usd')}** conservative cumulative reserve, and **{cost('receipted_cumulative_reserve_usd')}** receipted reserve against the **${costs['budget_cap_usd']:.2f}** cumulative cap. All research Pods are recorded absent. Attempts 1 and 2 were rejected before allocation; attempt 3 used an RTX 4090 at $0.74/hour with a hard three-hour deadline and a $2.70 maximum reservation. Actual estimated charges are derived from its receipt, rather than equated with that reservation.

The [machine-readable panel result](../data/phase17/panel-results.json), [executed frozen panel plan](../{executed_plan}), [assay review](../data/phase17/assay-review.json), and [source-table audit](../data/phase17/source-table-audit.json) preserve provenance. The report generator reads those recorded artifacts and does not recompute or invent predictions.

## Reproduction

With the archived inputs and result bundle retained under the ignored local research storage, these commands verify and regenerate the analysis without renting a GPU. A fresh clone alone does not contain the raw archive.

```sh
.venv/bin/python -m unittest tests.test_analyze_rock_panel tests.test_boltz_panel_inference tests.test_runpod_boltz_panel tests.test_reconcile_phase17
.venv/bin/python scripts/analyze_rock_panel.py --attempt 3
.venv/bin/python scripts/plot_rock_panel.py
python3 scripts/report_rock_panel.py
```
'''
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report)
    print(f'Wrote {args.output}')


if __name__ == '__main__':
    try:
        main()
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f'error: {exc}')
