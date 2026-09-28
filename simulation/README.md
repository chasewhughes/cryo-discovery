# Reconstructed hydration pilot

This workflow runs molecular dynamics of one free amino acid in liquid water.
It measures hydration descriptors. It does not simulate ice growth, freezing a
cell, toxicity, cell-death pathways, or post-thaw function. Results are kept
separate from experimental data and existing trained models.

## Design

The [prespecified plan](../data/phase10/simulation-plan.json) selects
L-phenylalanine (Amino line 8, published 11.8% MGS) and glycine (line 14,
97.7% MGS) as known activity-range controls. They differ in size and chemistry.
Three independent seeds per compound produce 100 ps of equilibration and 1 ns
of production, with 100 sampled frames per trajectory. Frames are correlated;
only seeds are counted as simulation replicates.

The reconstruction uses OpenMM 8.6, its CHARMM36 distribution, and a local
conversion of TIP4P/Ice. Free amino-acid zwitterions are explicit assumptions;
the source CSV's neutral SMILES remain unchanged. OpenMM matches residue
connectivity to charged terminal templates. Tests check parent/stereochemical
identity, net charge, ammonium partial-charge sums, water charge, oxygen LJ
parameters, rigid geometry and virtual-site placement.

The published study reports CHARMM36, TIP4P/Ice, a 4 nm cube, 273 K and 20 ns.
Original per-compound topology/state and several integration/equilibration
settings were not recovered. Our Langevin NVT settings, 1.0 nm cutoff with
switching from 0.8 nm, timestep and short duration are explicit reconstruction
choices. Solvent starts from OpenMM's TIP4P-Ew packing, but the actual water
charges, oxygen LJ parameters and virtual-site displacement come from the
TIP4P/Ice XML. Fixed-volume density is recorded, not pressure-equilibrated.
One solute in 64 nm³ is approximately 25.95 mM, with no added NaCl; this liquid
model does not reproduce the 20 mM / 10 mM NaCl splat assay.

Hydration numbers count each water oxygen once if it lies within the cutoff
of any solute atom, with periodic minimum-image distances. Pair histograms
instead include all oxygen-to-solute-atom distances and are normalized within
0–0.5 nm. This is a literal reading of the paper's prose; the precise definition
used to generate the archived histograms is unresolved. Post hoc nearest-water
and radial-normalization diagnostics are retained separately. A comparison is
a descriptor consistency check, not experimental validation. Molecular-weight
normalization is reported separately; the source model's volume-normalized
hydration indices are not reconstructed or substituted into its model.

Sources: [Warren et al.](https://doi.org/10.1038/s41467-024-52266-w),
[OpenMM installation](https://docs.openmm.org/latest/userguide/application/01_getting_started.html),
[TIP4P/Ice parameter table](https://doc.lammps.org/stable/Howto_tip4p.html),
[methods review](../data/phase10/simulation-methods-review.json).

## Local execution

Use an isolated environment to preserve the fitted models' environment:

```sh
python3 scripts/with_external_storage.py -- python3 -m venv cryo-adata/envs/md
python3 scripts/with_external_storage.py -- cryo-adata/envs/md/bin/python -m pip install --no-cache-dir -r requirements-md.txt
python3 scripts/with_external_storage.py -- cryo-adata/envs/md/bin/python -m unittest tests.test_hydration_pilot
python3 scripts/with_external_storage.py -- cryo-adata/envs/md/bin/python scripts/run_hydration_pilot.py --compound phe --seed 20260906 --platform OpenCL --equilibration-ps 2 --production-ps 2 --frames 10 --max-wall-seconds 180 --output data/raw/phase10/new-smoke
```

Output directories must be new. On this Mac, OpenCL requires single precision;
the CUDA production runs use mixed precision. A 2 ps smoke test is only a
numerical/throughput check. The in-script time check occurs between integration
batches; an external process timeout is needed to bound setup/minimization too.

## RunPod lifecycle

The current user-authorized cumulative GPU budget is **$10**, including prior
successful and failed research runs (updated 2026-09-06). Phase 10 GPU spending
is estimated at $0.2181551203502549, leaving approximately $9.78 before billing
reconciliation and a shutdown margin. The original $17 account credit recorded
in the historical simulation plan is not the current spending limit. Future
launchers must account for all phases before reserving another job's maximum
cost. The existing launcher's narrower $3 Phase 10 guard remains unchanged.

The launcher reads `cryo.runpod.api-key` from macOS Keychain and sends a small
reviewed code bundle to a new Secure Cloud RTX 4090 Pod. It accepts a GPU quote
up to $0.80/hour, uses a 10 GB container disk with no persistent volume, and sets
a 90-minute absolute deletion deadline. Both a separate local watchdog and the
worker enforce deletion. The remote watchdog needs the RunPod key in the Pod's
environment; the worker never writes it to result files. Existing user Pods are
not modified. These timers are safeguards, not an account-level billing cap.

```sh
python3 scripts/with_external_storage.py -- python3 scripts/runpod_hydration.py launch
python3 scripts/with_external_storage.py -- python3 scripts/runpod_hydration.py status
python3 scripts/with_external_storage.py -- python3 scripts/runpod_hydration.py collect
```

`collect` retrieves a bounded, authenticated result archive and deletes the Pod.
Deletion is checked with a follow-up API request and recorded in a receipt.
The launcher refuses a second launch while its state file exists. Archive a
completed attempt only after confirming deletion. Do not run `launch` merely
to inspect the workflow: it rents compute.

For any later retry in this phase, the launcher sums recorded GPU estimates
and reserves $1.30 for the next attempt (maximum timed GPU charge plus a disk
allowance), rejecting a projected phase total over $3 or an unconfirmed prior
deletion. This ledger still depends on complete receipts and provider behavior.

The first attempt exposed a CUDA 12.9 NVRTC / driver 12.4 incompatibility and
was deleted without producing trajectories. The corrected environment pins
CUDA components to 12.4 and requests a compatible host. The worker explicitly
checks the CUDA force-test result because `openmm.testInstallation` can exit
successfully even when that platform fails.

No provider invoice is inferred from elapsed runtime. Receipts distinguish the
quoted-rate estimate from actual billing. Raw trajectories, systems, logs,
archives and transfer tokens remain under ignored local research storage.

## Analyze saved results without further rental

With all six trajectories restored under `data/raw/phase10/runpod/runs`, use the
existing scientific environment to regenerate the curated JSON and figure:

```sh
python3 scripts/with_external_storage.py -- env MPLCONFIGDIR=data/tmp/matplotlib .venv/bin/python scripts/analyze_hydration_pilot.py
```

The analysis preserves the primary all-pairs comparison and all three post hoc
definition variants. The closest match is not proof of the original processing
method. See the [results report](../reports/hydration-pilot.md).


## Phase 11: measurement and ensemble stability

Phase 11 uses a new, explicit nearest-water representation. It preserves the
original Phase 10 scripts and results, and does not feed replacement descriptors
into any frozen activity model. See [descriptor definition](../reports/hydration-definition.md)
and the [design frozen before production](../data/phase11/stability-plan.json).
The study compares three seeds for each of glycine and phenylalanine under NVT
and NPT, using 500 ps equilibration and 3 ns production per trajectory.

The new cloud launcher reserves at most $3 for a batch and accounts for prior
research receipts under the $10 cumulative GPU authorization. It requires a
recent billing reconciliation and GPU quote, accepts at most $0.80/hour, and
sets a three-hour deadline. Local and remote deletion watchdogs are safeguards,
not provider-enforced account billing caps. Research resources are explicitly
named; unrelated user Pods are untouched.

```sh
python3 scripts/with_external_storage.py -- cryo-adata/envs/md/bin/python -m unittest tests.test_hydration_stability tests.test_hydration_pilot
python3 -m unittest tests.test_runpod_stability tests.test_runpod_hydration
python3 scripts/with_external_storage.py -- cryo-adata/envs/md/bin/python scripts/audit_hydration_descriptor.py
python3 scripts/with_external_storage.py -- .venv/bin/python scripts/fix_hydration_pdb_boxes.py
python3 scripts/with_external_storage.py -- .venv/bin/python scripts/analyze_hydration_stability.py
python3 scripts/with_external_storage.py -- .venv/bin/python scripts/diagnose_hydration_sampling.py
```

The analysis uses the existing plotting environment; simulation uses the
isolated MD environment. Cloud lifecycle commands are `launch`, `status` and
`collect` in `scripts/runpod_stability.py`. `launch` rents compute and must only
be used after inspecting the plan, budget, receipts and current quote. A saved
state blocks accidental duplicate launches. Keep original state/receipt records.

The analyzer reports all three time blocks, between-seed variability, ensemble
contrasts, stride sensitivity and exploratory correlation diagnostics. Its
predeclared thresholds are engineering flags rather than convergence guarantees.
Leucine/isoleucine are a deferred size-matched control pair; successful vacuum
template construction does not mean additional solvated MD or efficacy
validation has been performed.

The deployed Phase 11 source is preserved in Git commit `06210fc`; every input
and worker hash matches the launch record. The later runner correction updates
only the final PDB box metadata. Original cloud PDBs are preserved, and
`fix_hydration_pdb_boxes.py` writes `topology-final-box.pdb` copies from the final
trajectory boxes. NPT trajectory and state boxes were already correct. See
[deployment provenance](../data/phase11/deployment-provenance.json).

## Phase 12: longer sampling controls

The [frozen plan](../data/phase12/sampling-plan.json) selects four stochastic
branches from Phase 11 final states. Each retains positions and velocities,
sets new thermostat/barostat RNG seeds, excludes 100 ps re-equilibration, and
records 10 ns new production at 10 ps intervals. XML state files do not preserve
RNG internals; these are not exact continuations or independent starting
conformations. The original 3 ns is not pooled with the new segment.

The unchanged 100-bin descriptor compares first and second 5-ns halves. The
[offline calibration](../reports/hydration-sampling-calibration.md) retains the
original 0.05 TV criterion. All five 2-ns windows and the full resolution,
block-length and endpoint-duration grid are secondary diagnostics.

`runpod_phase12.py` reserves four one-hour Pods at at most $0.80/hour plus a
$0.50 uncertainty margin, counting all prior research spending against $10.
Parent files travel in authenticated, checksum-verified uploads; credentials
remain outside Git. Each Pod has local and remote deletion watchdogs. These
are operational safeguards, not a provider-enforced billing cap.

```sh
python3 scripts/reconcile_sampling_compute.py
python3 scripts/with_external_storage.py -- .venv/bin/python scripts/calibrate_hydration_sampling.py
python3 -m unittest tests.test_runpod_phase12
cryo-adata/envs/md/bin/python -m unittest tests.test_hydration_extension
python3 scripts/with_external_storage.py -- python3 scripts/runpod_phase12.py status
python3 scripts/with_external_storage.py -- python3 scripts/runpod_phase12.py collect
python3 scripts/with_external_storage.py -- env MPLCONFIGDIR=data/tmp/matplotlib .venv/bin/python scripts/analyze_hydration_extensions.py
```

The launcher also has `launch` (rents compute) and `cleanup` (deletes this batch)
commands. An exclusive batch record prevents duplicate rentals. Do not remove
state or receipt files to rerun a completed batch. Exact deployed source hashes
are recorded in `data/phase12/deployment-provenance.json` before launch.

The first Phase 12 attempt stopped before production because a 1e-9 restoration
check was tighter than GPU coordinate/velocity rounding. All four failed Pods
were deleted; receipts and exact source remain preserved. The corrected retry
uses `data/raw/phase12/runpod-attempt2/`, separate receipts, and the same frozen
scientific design. The restoration check records actual errors and bounds each
component by four float32 rounding units; a 0.001 nm displacement is rejected.
See `data/phase12/retry-rationale.json` for the local reproduction and costs.

After collection, run `scripts/verify_hydration_extensions.py` with `.venv/bin/python`
for source/physics/geometry checks, and `scripts/reconcile_sampling_compute.py --final`
for a fresh absence and billing snapshot. The second command preserves the
prelaunch reconciliation and writes `data/phase12/compute-costs.json`.

## Phase 13: same-formula controls

The [frozen design](../data/phase13/sampling-plan.json) compares L-leucine and
L-isoleucine, three independently seeded preparations per compound. Both have
formula C6H13NO2 and 22 solute atoms. Exactly 2,070 water molecules make total
mass and solvent number identical across all six boxes. NPT volume determines
realized concentration; fixed water count does not imply fixed concentration.
There is no added salt. All six runs use 273 K, 1 bar, 1 ns excluded equilibration
and 10 ns production, with the same nearest-water descriptor and five-nanosecond
stability comparison used in Phase 12.

Preparation uses local OpenCL minimization and validates the final serialized
formula, neutral partial charge and coordinate-derived S / 2S,3S stereochemistry.
The periodic restart check allows float32 rounding at the greater of coordinate
and box-length scales, while still rejecting actual 0.001 nm displacements.
Both compounds passed small local restart smoke checks before rental.

The Phase 13 runner wraps the shared integration engine and records both source
hashes. The historical internal engine result is preserved as `core-result.json`;
`result.json` carries Phase 13 identity and provenance. Raw outputs stay in local
`cryo-adata/`. The six-Pod reservation is $5.40 (six one-hour resources at at most
$0.80/hour, plus $0.60 margin) and counts all prior costs toward the $10 total.
An initial provider HTTP500 interrupted resource creation; its single created
Pod was deleted and receipted. The retry uses separate `runpod-attempt2` storage.

```sh
python3 scripts/reconcile_matched_compute.py
python3 scripts/with_external_storage.py -- .venv/bin/python scripts/audit_matched_preparations.py
python3 scripts/with_external_storage.py -- python3 scripts/runpod_phase13.py status
python3 scripts/with_external_storage.py -- python3 scripts/runpod_phase13.py collect
python3 scripts/with_external_storage.py -- .venv/bin/python scripts/verify_matched_hydration.py
python3 scripts/with_external_storage.py -- env MPLCONFIGDIR=data/tmp/matplotlib .venv/bin/python scripts/analyze_matched_hydration.py
python3 scripts/reconcile_matched_compute.py --final
```

As before, `launch` rents compute and `cleanup` deletes the recorded batch.
Keep all batch state and receipts; do not remove them to rerun completed jobs.
The exact generation and deployment source is pinned in the Phase 13 manifest;
a subsequent preparation-script comment/duplicate-key cleanup does not change
the generated states or physical settings.

The six Phase 13 production trajectories are selected by the explicit
`data/phase13/result-locations.json` map. Three attempt-2 workers hit the
420-second package-download deadline before simulation. Attempt 3 retries only
those same preparation/production seeds, with a 900-second installation limit
and unchanged one-hour Pod lifetime. The retry reservation includes all prior
charges and the full lifetimes of both ongoing and replacement workers.
Attempt-3 deployment source is pinned separately in
`data/phase13/deployment-provenance-attempt3.json`; scientific integration code,
inputs, force fields, output cadence and analysis criteria are unchanged.

```sh
python3 scripts/with_external_storage.py -- env MPLCONFIGDIR=data/tmp/matplotlib .venv/bin/python scripts/analyze_matched_hydration.py
python3 scripts/with_external_storage.py -- .venv/bin/python scripts/verify_matched_hydration.py
```

Verification compares serialized physical settings, uploaded source/input hashes,
final clocks and boxes, all-frame rigid-water geometry and preservation of the
audited starting stereochemistry. These are numerical and provenance checks.
They do not validate the force field against experiment or establish efficacy.
