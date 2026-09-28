# Strengthening the Cryo pipeline: reference data and a biological-target benchmark

2026-09-06 • Phase 15

We acquired a published permeability/toxicity screen, built a structure-linked ROCK2 benchmark, ran a frozen baseline comparison, and prepared two Boltz-2 input drafts. **No AlphaFold or Boltz inference has been executed.** The current deliverable is a tested reference-data and evaluation foundation; it does not establish that a larger model improves predictions.

## Data acquired

The [transport dataset](../data/phase15/transport-screen.json) contains all 28 Table 1 solute entries (27 test chemicals plus sucrose) at 4 °C and 25 °C, and all 13 Table 2 activation-energy entries from [the published screen](https://doi.org/10.1038/s41598-025-85509-x). Original XML and supplementary material are archived locally with [source hashes](../data/phase15/transport-source-manifest.json).

| Temperature | Numeric fitted permeability | Too fast to measure | Toxic; permeability unavailable |
| --- | ---: | ---: | ---: |
| 4 °C | 16 | 8 | 4 |
| 25 °C | 13 | 9 | 6 |

These are bovine pulmonary artery endothelial cell measurements, not iPSC parameters. Values incorporate the source model's area/volume normalization and cannot simply replace the dimensionless parameters in our Phase 14 oocyte model. Table uncertainties retain their reported values without assuming SD versus SEM. Sucrose's small apparent fitted permeability remains identified as a control estimate.

The screen supplies useful categorical toxicity information. Exact per-compound viability percentages were not available as a machine-readable table in the inspected article or supplement; none were invented or digitized. “Fast,” “toxic,” missing and numeric measurements remain separate states. Measured bath osmolality and temperature are retained.

The [ROCK2 dataset](../data/phase15/rock-benchmark.json) comes from a single selected medicinal chemistry study, [Identification of Selective Dual ROCK1 and ROCK2 Inhibitors Using Structure-Based Drug Design](https://doi.org/10.1021/acs.jmedchem.8b01098), via ChEMBL. It contains:

- 46 acquired human ROCK2 activity records.
- 43 exact IC50 measurements in assay CHEMBL4328667, representing 43 unique compounds and 13 achiral Murcko scaffolds.
- One right-censored measurement, IC50 >10,000 nM, retained as a measured weak control and excluded from exact-value regression.
- Two excluded records: a different endpoint and a different assay.
- An exact chemical-identity match between [6ED6](https://www.rcsb.org/structure/6ED6)'s ligand J0P and CHEMBL4522042, measured at 37 nM in the selected assay.

This provides a biological target benchmark, not evidence that those compounds are cryoprotectants. ROCK2 inhibition is an assay-specific endpoint and must remain separate from ROCK1 activity, cellular recovery and ice inhibition. The 2018 compounds and structures may overlap pretrained model training sets, so they cannot establish prospective generalization.

## The first benchmark result

We froze the [analysis plan](../data/phase15/rock-baseline-plan.json), source dataset and code hashes before execution and committed them in `b12054c`. The test compared a fixed nearest-fingerprint-neighbor predictor against a training-fold mean. Each complete Murcko scaffold was held out in turn. Exact structures and their stereochemical variants could not appear on both sides of a fold. Related analogues with different scaffolds can still resemble one another; this remains a narrow, same-paper benchmark.

| Metric | Nearest chemical neighbor | Training-fold mean |
| --- | ---: | ---: |
| Mean absolute error, pIC50 | 0.8444 | 0.6834 |
| Spearman correlation with measured pIC50 | −0.0757 | Not a frozen decision metric |

The hypothesis required at least 20% lower MAE and Spearman correlation of at least 0.5. It **failed**: nearest-neighbor MAE was about 23.6% higher than the mean control. All 43 held-out predictions are preserved in the [result](../data/phase15/rock-baseline-result.json).

This does not show that Boltz-2 or AF3 will fail. It establishes an honest baseline that a larger model should improve on before we rely on it for candidate ranking. No hyperparameters or eligibility criteria were changed after seeing this result. No statistical claim of population-level superiority or inferiority is made from these dependent folds.

## Model readiness

The [official-source audit](../data/phase15/model-readiness.json) favors **Boltz-2 for an initial affinity smoke test**. Its code and weights are MIT licensed and it exposes affinity outputs. AlphaFold 3 remains useful for structure hypotheses, but its local workflow does not supply an equivalent affinity output and requires its own model-parameter terms and compute setup. Neither supplies a validated whole-cell survival simulator.

Two [Boltz input drafts](../data/phase15/boltz-input-manifest.json) are prepared: the known 37 nM ligand and the measured >10,000 nM weak control. They use the deposited 415-residue protein sequence, a protein-chain template and explicit single-sequence mode. They have not been validated by an installed Boltz parser. Single-sequence mode is a limited installation test; it is not the proposed accuracy-validation configuration. Protein templates do not turn the tool into a fixed-pose ligand affinity scorer.

Before inference and comparison, the remaining work is concrete:

1. Pin a Boltz version, install it in an isolated environment and validate the inputs. Record model-weight identities and hashes.
2. Resolve the difference between the crystallographic construct and the assay construct (reported residues 11–552), and the source assay metadata's mixed HTRF/33P-ATP description. Define the MSA and structural-template policy.
3. Reconcile existing GPU charges, reserve a bounded pilot with automatic shutdown, and measure throughput and memory on the actual input. The official sources reviewed do not establish a reliable per-input runtime for our rentable hardware.
4. Run the two controls as an execution check. Two selected controls cannot validate affinity accuracy.
5. Freeze a larger comparison and evaluate the full eligible panel against the preserved baselines. Preserve censoring and verify the pinned model's output units. Seek an external study or new measured batch before claiming generalization.

Schrödinger FEP+ remains a later option after a validated target, measured ligand series and calibrated protocol exist. No new subscription or API was needed to acquire these data. No GPU spending occurred in this phase; the $10 cumulative authorization is unchanged. We have not yet determined how many Boltz runs fit the remaining budget.

## Reproduce and verify

Use the existing scientific `.venv` pinned by `requirements-iri.txt`. Source downloads remain under ignored `cryo-adata/` storage. ChEMBL-derived data carry CC BY-SA 3.0 attribution/share-alike requirements; PDB data are CC0.

```sh
python3 scripts/with_external_storage.py -- python3 scripts/fetch_rock_benchmark.py
.venv/bin/python scripts/rock_benchmark.py curate
.venv/bin/python scripts/rock_benchmark.py prepare
python3 scripts/extract_transport_screen.py --xml data/raw/phase15/transport/PMC11731021.xml --output data/phase15/transport-screen.json
.venv/bin/python -m unittest tests.test_extract_transport_screen tests.test_rock_benchmark
```

`rock_benchmark.py freeze` and `run` refuse to overwrite the existing plan/start/result. Preserve those records; a revised experiment needs a separately versioned plan and result. Transport acquisition URLs are in its source manifest; the extractor operates on the archived XML. None of these commands installs model weights or rents compute.
