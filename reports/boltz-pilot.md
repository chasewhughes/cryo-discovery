# Boltz-2 reference pilot

2026-09-06 • Phase 16 • analyzed attempt 4

The two-control Boltz-2 execution check passed. The two outputs ordered the known bound ligand as stronger than the measured weak control. This is an installation and execution milestone, not a validation of affinity accuracy, cryoprotection or discovery of a new compound.

## Recorded predictions

| Control | Measured ROCK2 IC50, nM | Model IC50-equivalent, nM | Predicted binder probability | Execution |
| --- | ---: | ---: | ---: | --- |
| Known bound ligand | 37 | 323.183 | 0.8930 | completed |
| Measured weak control | >10,000 | 3411.171 | 0.2928 | completed |

The known ligand is predicted at 323 nM versus the measured 37 nM (8.7 times higher). The weak control is predicted at 3411 nM, below its measured >10,000 nM bound. Correct ordering therefore does not establish quantitative agreement. The binder probabilities also follow the expected ordering; that is a descriptive observation, not a new acceptance criterion.

The displayed model concentration is `10^(affinity_pred_value + 3)` nM, following [the documented Boltz output units](https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md). The corresponding pIC50-equivalent is `6 − affinity_pred_value`. These are learned predictions, not measured biochemical IC50 values or binding Kd. Binder probability is a separate model output and has not been calibrated on this assay. Boltz recommends that classifier for binder/decoy screening and the continuous affinity score for comparing active molecules. Our frozen continuous-score comparison against the weak control is therefore exploratory and outside the documented recommended use; it is retained transparently, not treated as an accuracy validation. The weak control remains a **right-censored >10 µM measurement**, never an exact 10 µM value.

The [measured source dataset](../data/phase15/rock-benchmark.json) links the known ligand to PDB 6ED6/J0P by exact chemical identity. Both compounds are known literature controls. Two selected points cannot establish MAE, correlation, ranking performance across a library, or prospective generalization.

## What was executed

The frozen configuration requests Boltz 2.2.1, PyTorch 2.8.0, one A6000 GPU, a 415-residue ROCK2 sequence, and a protein-chain template from 6ED6. It uses explicit single-sequence mode, three recycling steps, 200 structure sampling steps, one structure diffusion sample, 200 affinity sampling steps and five affinity diffusion samples, with optional kernels disabled. No explicit random seed was supplied through the CLI. The saved `pip freeze`, commands, input hashes, model checkpoint hashes, structures, confidence outputs and logs provide execution provenance. Checkpoint hashes were captured during this run; they were not compared with a preregistered expected weight digest. The analyzer verifies recorded package versions before accepting execution.

- Known bound ligand: 364.1 seconds; highest sampled GPU memory 4.53 GiB.
- Measured weak control: 105.0 seconds; highest sampled GPU memory 4.55 GiB.

Timing includes each CLI invocation's preprocessing, loading and any downloads; the first invocation can have a cold cache. GPU memory is sampled every five seconds and can miss transient peaks. These measurements are not a general runtime guarantee for other proteins or compounds.

The final [machine-readable result](../data/phase16/pilot-results.json) records validation errors, if any, and artifact provenance. The result archive is stored under ignored `data/raw/phase16/attempt4` and checked against its receipt checksum. Model weights remain outside the returned archive; their hashes are recorded.

## Limits that remain

- The crystallographic construct differs from the assay construct reported as residues 11–552. Original assay ATP/HTRF metadata still needs reconciliation.
- Single-sequence mode is a limited smoke-test configuration. A proper benchmark needs a defined MSA/template policy and repeated sampling.
- The 2018 known ligands and structure may overlap model training data. This is not a blinded external test.
- Affinity predictions do not measure ice inhibition, CPA permeability, CEPT mixture effects or post-thaw viability/function.

The next scientific gate is a frozen evaluation on the larger measured ROCK2 panel, comparing against the [Phase 15 baselines](biological-benchmark.md), followed by an external assay source or new measurements. A passing two-control result alone is insufficient to recommend a new candidate.

## Spending and cleanup

| Allocated attempt | Worker outcome | Estimated GPU charge | Pod deletion |
| --- | --- | ---: | --- |
| 1 | failed | $0.0379 | Confirmed |
| 2 | failed | $0.0257 | Confirmed |
| 4 | complete | $0.0963 | Confirmed |

The first two allocated attempts stopped at the GPU check before inference. The first lacked detailed diagnostics; the second confirmed working CUDA and showed that the initial memory threshold was too strict for exposed memory. Driver/ECC reservations are a plausible explanation for the difference from nominal capacity. The corrected check retains the GPU-identity and single-device requirements and accepts at least 40 GiB exposed memory; a regression test uses the observed A6000 memory. A separate provisioning request is recorded in the attempt-3 intent audit; no Pod was observed for that request. Its reservation and watchdog disposition must be read alongside the cost record.

Estimated Phase 16 GPU spending is **$0.1598**. Cumulative estimated research GPU spending is **$4.2375**, with a conservative total reserve of **$5.1391**, including **$0.90** for unresolved provisioning intents. The receipted posted/elapsed reserve alone is **$4.2391**. The cap remains **$10 total**. These are reconciled estimates, not a final invoice. [Cost records](../data/phase16/compute-costs.json) preserve prior attempts and confirmed cleanup; unrelated Pods were not changed.

## Reproduction

```sh
python3 -m unittest tests.test_runpod_boltz tests.test_boltz_pilot_inference tests.test_analyze_boltz_pilot tests.test_reconcile_boltz_compute
python3 scripts/analyze_boltz_pilot.py --attempt 4
python3 scripts/report_boltz_pilot.py
```

These commands inspect the saved run; they do not rent compute. Restore the ignored raw archive on a fresh clone. Do not remove an attempt directory, receipt or frozen plan to force a rerun. Any new inference run needs its own recorded inputs, reconciled budget reservation and cleanup controls.
