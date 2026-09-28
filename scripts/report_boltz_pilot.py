"""Render the recorded pilot outcomes and costs without recomputing inference."""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=ROOT/'data/phase16/pilot-results.json')
    args = parser.parse_args()
    results = json.loads(args.results.read_text())
    costs = json.loads((ROOT/'data/phase16/compute-costs.json').read_text())
    valid = not results['validation_errors']
    rows, telemetry = [], []
    for c in results['cases']:
        known = c['input'].startswith('CHEMBL4522042')
        aff = c.get('affinity_fields', {})
        value = aff.get('affinity_pred_value')
        pred = f"{10**(value+3):.3f}" if isinstance(value, (int, float)) and math.isfinite(value) and -100 < value < 100 else 'Unavailable'
        prob = aff.get('affinity_probability_binary')
        prob = f'{prob:.4f}' if isinstance(prob, (int, float)) and math.isfinite(prob) else 'Unavailable'
        label = 'Known bound ligand' if known else 'Measured weak control'
        rows.append(f"| {label} | {'37' if known else '>10,000'} | {pred} | {prob} | {c.get('status','missing')} |")
        memory = []
        for sample in c.get('gpu_samples', []):
            try:
                memory.append(float(sample['raw'].split(',')[0]))
            except (KeyError, ValueError):
                pass
        wall = c.get('wall_seconds')
        wall_text = f'{wall:.1f} seconds' if isinstance(wall, (int, float)) else 'unavailable'
        mem_text = f'{max(memory)/1024:.2f} GiB' if memory else 'unavailable'
        telemetry.append(f'- {label}: {wall_text}; highest sampled GPU memory {mem_text}.')
    receipts = []
    for p in sorted((ROOT/'data/phase16').glob('runpod-attempt*-receipt.json')):
        r = json.loads(p.read_text())
        receipts.append(f"| {r['attempt']} | {r.get('worker_state','unknown')} | ${r['estimated_gpu_cost_usd']:.4f} | {'Confirmed' if r['deleted'] else 'Unconfirmed'} |")
    ordered = results.get('directional_ordering_known_pIC50_higher_than_weak_control')
    order_text = ('The two outputs ordered the known bound ligand as stronger than the measured weak control.' if ordered is True else
                  'The two outputs did not order the known bound ligand as stronger than the measured weak control.' if ordered is False else
                  'A directional comparison is unavailable because the required outputs are incomplete.')
    quantitative = ''
    if valid:
        a, b = [c['affinity_fields'] for c in results['cases']]
        nma, nmb = 10**(a['affinity_pred_value']+3), 10**(b['affinity_pred_value']+3)
        quantitative = f"The known ligand is predicted at {nma:.0f} nM versus the measured 37 nM ({nma/37:.1f} times higher). The weak control is predicted at {nmb:.0f} nM, below its measured >10,000 nM bound. Correct ordering therefore does not establish quantitative agreement. The binder probabilities also {'follow' if a['affinity_probability_binary']>b['affinity_probability_binary'] else 'do not follow'} the expected ordering; that is a descriptive observation, not a new acceptance criterion."
    verdict = 'The two-control Boltz-2 execution check passed.' if valid else 'The two-control Boltz-2 execution check did not pass all validation gates.'
    report = f'''# Boltz-2 reference pilot

2026-09-06 • Phase 16 • analyzed attempt {results['attempt']}

{verdict} {order_text} This is an installation and execution milestone, not a validation of affinity accuracy, cryoprotection or discovery of a new compound.

## Recorded predictions

| Control | Measured ROCK2 IC50, nM | Model IC50-equivalent, nM | Predicted binder probability | Execution |
| --- | ---: | ---: | ---: | --- |
{chr(10).join(rows)}

{quantitative}

The displayed model concentration is `10^(affinity_pred_value + 3)` nM, following [the documented Boltz output units](https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md). The corresponding pIC50-equivalent is `6 − affinity_pred_value`. These are learned predictions, not measured biochemical IC50 values or binding Kd. Binder probability is a separate model output and has not been calibrated on this assay. Boltz recommends that classifier for binder/decoy screening and the continuous affinity score for comparing active molecules. Our frozen continuous-score comparison against the weak control is therefore exploratory and outside the documented recommended use; it is retained transparently, not treated as an accuracy validation. The weak control remains a **right-censored >10 µM measurement**, never an exact 10 µM value.

The [measured source dataset](../data/phase15/rock-benchmark.json) links the known ligand to PDB 6ED6/J0P by exact chemical identity. Both compounds are known literature controls. Two selected points cannot establish MAE, correlation, ranking performance across a library, or prospective generalization.

## What was executed

The frozen configuration requests Boltz 2.2.1, PyTorch 2.8.0, one A6000 GPU, a 415-residue ROCK2 sequence, and a protein-chain template from 6ED6. It uses explicit single-sequence mode, three recycling steps, 200 structure sampling steps, one structure diffusion sample, 200 affinity sampling steps and five affinity diffusion samples, with optional kernels disabled. No explicit random seed was supplied through the CLI. The saved `pip freeze`, commands, input hashes, model checkpoint hashes, structures, confidence outputs and logs provide execution provenance. Checkpoint hashes were captured during this run; they were not compared with a preregistered expected weight digest. The analyzer verifies recorded package versions before accepting execution.

{chr(10).join(telemetry)}

Timing includes each CLI invocation's preprocessing, loading and any downloads; the first invocation can have a cold cache. GPU memory is sampled every five seconds and can miss transient peaks. These measurements are not a general runtime guarantee for other proteins or compounds.

The final [machine-readable result](../data/phase16/pilot-results.json) records validation errors, if any, and artifact provenance. The result archive is stored under ignored `data/raw/phase16/attempt{results['attempt']}` and checked against its receipt checksum. Model weights remain outside the returned archive; their hashes are recorded.

## Limits that remain

- The crystallographic construct differs from the assay construct reported as residues 11–552. Original assay ATP/HTRF metadata still needs reconciliation.
- Single-sequence mode is a limited smoke-test configuration. A proper benchmark needs a defined MSA/template policy and repeated sampling.
- The 2018 known ligands and structure may overlap model training data. This is not a blinded external test.
- Affinity predictions do not measure ice inhibition, CPA permeability, CEPT mixture effects or post-thaw viability/function.

The next scientific gate is a frozen evaluation on the larger measured ROCK2 panel, comparing against the [Phase 15 baselines](biological-benchmark.md), followed by an external assay source or new measurements. A passing two-control result alone is insufficient to recommend a new candidate.

## Spending and cleanup

| Allocated attempt | Worker outcome | Estimated GPU charge | Pod deletion |
| --- | --- | ---: | --- |
{chr(10).join(receipts)}

The first two allocated attempts stopped at the GPU check before inference. The first lacked detailed diagnostics; the second confirmed working CUDA and showed that the initial memory threshold was too strict for exposed memory. Driver/ECC reservations are a plausible explanation for the difference from nominal capacity. The corrected check retains the GPU-identity and single-device requirements and accepts at least 40 GiB exposed memory; a regression test uses the observed A6000 memory. A separate provisioning request is recorded in the attempt-3 intent audit; no Pod was observed for that request. Its reservation and watchdog disposition must be read alongside the cost record.

Estimated Phase 16 GPU spending is **${costs['phase16_estimated_gpu_usd']:.4f}**. Cumulative estimated research GPU spending is **${costs['cumulative_estimated_gpu_usd']:.4f}**, with a conservative total reserve of **${costs['conservative_cumulative_reserve_usd']:.4f}**, including **${costs['pending_reserve_usd']:.2f}** for unresolved provisioning intents. The receipted posted/elapsed reserve alone is **${costs['receipted_cumulative_reserve_usd']:.4f}**. The cap remains **$10 total**. These are reconciled estimates, not a final invoice. [Cost records](../data/phase16/compute-costs.json) preserve prior attempts and confirmed cleanup; unrelated Pods were not changed.

## Reproduction

```sh
python3 -m unittest tests.test_runpod_boltz tests.test_boltz_pilot_inference tests.test_analyze_boltz_pilot tests.test_reconcile_boltz_compute
python3 scripts/analyze_boltz_pilot.py --attempt {results['attempt']}
python3 scripts/report_boltz_pilot.py
```

These commands inspect the saved run; they do not rent compute. Restore the ignored raw archive on a fresh clone. Do not remove an attempt directory, receipt or frozen plan to force a rerun. Any new inference run needs its own recorded inputs, reconciled budget reservation and cleanup controls.
'''
    (ROOT/'reports/boltz-pilot.md').write_text(report)
    print('Wrote reports/boltz-pilot.md')


if __name__ == '__main__':
    main()
