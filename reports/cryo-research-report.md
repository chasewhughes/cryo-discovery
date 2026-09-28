# Cryo research report

**What we built, how we tested it, what we learned, and the next steps**

Research status through 6 September 2026 | Private research project | Version 1.0

Cryo now has an auditable research corpus, reproducible analysis code, molecular prediction models, a working molecular-dynamics workflow, and an experimental handoff. The work has narrowed the questions and exposed important failure modes. It has not established a new cryoprotectant, a universal preservation recipe, or a validated predictor of post-thaw cell survival.

The original objective has two parts: organize published evidence about cell growth, preservation and recovery conditions; and identify protective compounds that could combine physical control of ice with biological protection against cell injury. The completed work provides a foundation for both. The condition database remains a focused benchmark rather than a comprehensive inventory of optimal culture and storage conditions.

| Completed asset | Recorded scope |
|---|---|
| Curated evidence corpus | 40 papers and 75 experiment summaries, with source locators and limitations |
| Discovery and protocol records | 194 title-screened records; 79 first-pass abstract screens; 3 studies / 10 protocol conditions |
| Molecular modeling | Baseline and advanced IRI models on separate 63- and 209-compound cohorts |
| New physical simulations | 28 trajectories or branches, totaling 142 ns of production across four stages |
| Experimental handoff | Six literature-prioritized candidates and a four-arm laboratory pilot design |

**The most recent result is limited but useful.** Six same-formula leucine/isoleucine simulations passed the numerical checks. Leucine averaged 0.218 more nearby water molecules, while overall hydration-distribution differences overlapped with variation between preparations. This does not identify the better cryoprotectant. [1]

**The next decision is experimental.** Select a cell system and laboratory partner, qualify the assays and materials, and test physical and biological interventions separately and together. The initial proposal uses human iPSCs and, if warranted, subsequent neuronal confirmation. This cell-system choice remains a planning assumption. [2]

Estimated cumulative GPU spending is **$4.08 of the $10 authorization**, including failed attempts. All 21 research Pods across phases and attempts were confirmed absent at the final reconciliation; three unrelated user Pods were left untouched. This is an elapsed-time GPU estimate, not a final invoice or the total cost of the research program. [3]

<!-- page -->

# What we built

The working product is a private research repository, not a deployed discovery service. It combines structured records, original-data analyses, command-line tools, saved model artifacts, simulation inputs and results, and readable reports. Each layer can be extended without treating an earlier hypothesis as an established result.

| Layer | Implemented capability and boundary |
|---|---|
| Evidence collection | Bounded discovery, publication deduplication, screening, selective retrieval and chemical identity lookups. Coverage is not exhaustive. |
| Structured evidence | Linked study/experiment records with cell context, interventions, protocols, outcomes, source locators and limitations. Missing fields remain explicit. |
| Reanalysis | Deposited-table readers and reproducible recovery, gene-list and formulation calculations; reported and derived quantities remain distinct. |
| Molecular models | Descriptors, grouped evaluation, nested tuning, saved estimators and withheld-fold predictions for a cell-free ice assay. |
| Molecular dynamics | Seeded liquid-hydration simulations, descriptors, sampling diagnostics, physical checks and authenticated result collection. No cell or ice interface is modeled. |
| Operations and provenance | Private Git history, hashes, isolated environments, tests, raw-storage separation, GPU budgets, automatic deletion and receipts. |
| Decision support | Evidence tables, six priorities, hypotheses, advancement rules and a laboratory matrix. No laboratory execution or purchases. |

The reusable workflow is: **source records → curated evidence → comparable datasets → analysis or simulation → documented decision → prospective experiment**. Every transition has a check; an accessible API response is not equivalent to an eligible measurement, and a successful simulation is not equivalent to biological validation.

Europe PMC, publisher/repository materials, Crossref and PubChem supported collection and identity work. Exa supplied bounded discovery leads. NCBI/OpenAlex access and an AgentMail project inbox were configured; browser access supported setup. Additional biological databases were access-audited, which does not mean their contents were comprehensively ingested. The suggested Google Scholar project was assessed and not installed because it serves author-profile extraction rather than the required general search. [4]

Efficient Luna research assistants handled bounded collection, engineering and independent checks. The primary agent reviewed selected sources, corrected extraction and interpretation errors, and retained disagreements and access gaps. These are AI-assisted reviews, not independent expert peer review. [4, 5]

<!-- page -->

# How we assembled and analyzed the evidence

Collection began with bounded searches and a separate discovery backlog. Records were deduplicated by publication identity, and related preprint/journal versions were grouped. Full texts, supplements and deposited measurements were selectively retrieved where available. The final curated corpus contains **31 papers reviewed from accessible full-text material, eight abstract-only records, and one abstract-plus-supplement record**. A remaining queue contains 57 full-text candidates, including three high-priority access gaps. [5]

Extraction preserves the cell model, timing, formulation and outcome denominator. Immediate live-cell fraction, absolute recovered-cell yield, later growth and retained function are separate quantities. The 75 experiment summaries are literature records; they are not 75 experiments conducted by Cryo or a complete arm-level numeric training table.

Validation checks required fields, duplicate identifiers and numeric-unit pairing. A source audit compares stored metadata and excerpt provenance with archived sources. Source and retrieval hashes document the exact material used. These checks establish traceability and consistency, not the truth of every published conclusion.

Two original-data analyses illustrate the approach:

| Deposited dataset | Reproduced result | Why the qualification matters |
|---|---|---|
| 2024 iPSC cryopreservation study | Recomputed 27 cryovial recovery values and six overall recovery/viability means. One IRI formulation improved mean immediate recovery by 12.86 percentage points versus CS10. | Three donor lines, not 27 donors. No CS5-only arm; handling differed. Later growth did not consistently follow immediate recovery. |
| 2025 cardiomyocyte study | Read 60 recovery observations, 18 calcium summaries and 72 optimizer entries. Final Solution A recovery averaged 92.06%, versus 80.19% for DMSO. | One engineered donor line; formulation mapping and calcium normalization remain unresolved. High recovery alone did not establish preserved function. |

These are recalculations of published deposits, not new experimental results or pooled efficacy estimates. The iPSC archive inventory covered 4,141 files; selective range retrieval acquired 15 relevant files without a full 3.5 GB download. Processed gene-list arithmetic reproduced 492 genes in the union and 166 shared genes. No independent RNA-seq alignment or differential-expression model was performed because the necessary raw count/sample inputs were not identified. [6, 7]

The six-candidate shortlist prioritizes research usefulness, not a cross-study efficacy score: 2FA, CEPT, a polyampholyte formulation, ethylene glycol/trehalose, CAMP bioink and recombinant CspB. These include mixtures, materials and a protein as well as a small molecule. They cannot all be treated as interchangeable drug candidates. [2]

<!-- page -->

# How we built and evaluated the molecular models

The modeling task predicts **percent mean grain size (% MGS)** in a cell-free ice-recrystallization-inhibition assay. Lower values indicate stronger inhibition under that assay's conditions. The endpoint is not percent cell survival. Public DOLMEN data and descriptors were downloaded at a pinned source commit, with attribution, license and hashes retained. [8]

Two assay cohorts were kept separate: 63 Amino compounds at nominal 20 mM in 10 mM NaCl, and 209 Glyco2 compounds explicitly at 22 mM in PBS. The overlapping Glyco dataset was not counted as independent data. Primary evaluation withheld entire molecular scaffold groups in five folds. A secondary connectivity split kept stereoisomers together but allowed related scaffolds in training.

Baseline models used 16 locally computed 2D descriptors. The advanced pipeline added 45 published descriptors, 100 published hydration bins, 10 hydration indices, and chiral molecular fingerprints. Grouped inner validation selected hyperparameters within the outer training folds; scaling and imputation were fitted only on training data. The three advanced components also formed a fixed equal-weight ensemble. [8, 9]

| Model | Amino MAE | Glyco2 MAE |
|---|---:|---:|
| Training-median baseline | 33.72 | 22.55 |
| Ridge regression | 35.11 | 21.38 |
| Random forest | 27.13 | 21.47 |
| Standard-descriptor support-vector regression | 28.79 | 22.03 |
| Hydration support-vector regression | 26.08 | 22.42 |
| Fingerprint kernel ridge regression | 30.29 | 22.31 |
| Fixed advanced ensemble | 28.11 | 21.41 |

MAE is mean absolute error in % MGS points on the same withheld-scaffold folds; lower is better. More complexity did not provide dependable improvement across both cohorts. The known strong inhibitor 2FA had an observed value of 3.0% MGS; the scaffold-held-out advanced ensemble predicted 71.63. That is a model failure case, not evidence against the experimental compound. [9]

The evaluation has only 11 Amino and 23 Glyco2 scaffold groups, with substantial imbalance. Later models were developed after earlier outcomes had been inspected, so these comparisons are not an untouched final test. Published hydration descriptors have missing rows and unresolved molecular-state conventions; 15 of 63 Amino training records show roughly one-proton mass differences. The models reused published hydration summaries. The new Cryo simulations were not fed into a newly trained efficacy model. [9, 10]

A later reconciliation separated 17 old prediction records into 14 nominal 20 mM and three 10 mM measurements. A frozen-model check was retrospective, and no eligible independent external numeric test rows were added. Saved model bundles remain available and unchanged. [10]

<!-- page -->

# How we conducted the virtual experiments

We built a molecular-dynamics workflow using OpenMM, CHARMM36 solute parameters and a local TIP4P/Ice water model. The experimental question was whether measurable liquid-water hydration differences could be reproduced and usefully distinguish known controls. The system contains no ice surface, membrane, cell-death pathway, or whole-cell model. [11]

| Stage | New production | What the stage established |
|---|---:|---|
| Initial glycine/phenylalanine pilot | 6 runs × 1 ns = 6 ns | Compute feasibility; exposed molecular-size and descriptor-definition ambiguities. |
| Fixed-volume / fixed-pressure comparison | 12 runs × 3 ns = 36 ns | Sensitivity to ensemble and sampling; all 12 fine-histogram drift flags remained. |
| Longer selected branches | 4 branches × 10 ns = 40 ns | All four passed frozen 5-ns-half stability checks; shorter-window drift persisted. |
| Same-formula controls | 6 runs × 10 ns = 60 ns | Three new preparations each for leucine and isoleucine; all six passed the numerical criteria. |

The stages total **142 ns of production and 13 ns of excluded equilibration**. This is an accounting total, not a pooled dataset: the stages differ in design and descriptor history. The four extension branches used selected earlier states, so they are not independent starting preparations. Passing a stability threshold does not prove equilibrium or force-field accuracy. [11-13]

For the latest comparison, we verified the intended S-leucine and (2S,3S)-isoleucine structures and generated independent starting conformations and velocities. Each box contained one zwitterion and exactly 2,070 water molecules. Conditions were 273 K and 1 bar, with a 2 fs integration step, 1 ns excluded equilibration and 10 ns production. Each trajectory saved 1,000 frames at 10 ps intervals. Inputs, preparation seeds, production seeds and analysis rules were recorded before production. [1]

The local descriptor counts each water oxygen once by its nearest distance to any solute atom, including hydrogens. It uses 100 bins over 0-0.5 nm, normalized within that range per frame and then averaged. It is not a radial distribution function or an exposed-surface-normalized quantity. The original DOLMEN descriptor and complete simulation settings remain unresolved. [12]

Verification checks source/input/trajectory hashes, finite values, normalized histograms, density from mass and volume, saved clocks and boxes, and unchanged physical settings. All 6,000 latest frames preserve the audited molecular handedness and rigid-water geometry. The four prespecified per-run flags cover PDF drift, count drift, density drift and mean-temperature offset. Independent recalculation from the saved arrays reproduced the reported primary summaries exactly. [1, 3]

<!-- page -->

# What the matched comparison found

Leucine and isoleucine have the same formula, C6H13NO2, modeled mass of 131.175 Da and solute atom count. Matching these controls reduces the size confound, while shape, stereochemistry and exposed surface remain different.

| Nearby-water count at 0.30 nm | Mean ± sample SD across three preparations |
|---|---:|
| Leucine | 15.196 ± 0.088 |
| Isoleucine | 14.978 ± 0.075 |
| Leucine minus isoleucine | +0.218 water molecules, about 1.5% |

![Hydration comparison across all six trajectories](matched-hydration.png)

All nine overlapping cross-compound count contrasts have the same positive sign. However, full distribution pair distances overlap: cross-compound total variation is 0.0195-0.0246, versus 0.0196-0.0253 within compounds. The equally weighted group-mean distribution distance is 0.0140. The nine pairs share six trajectories and are not nine independent observations. No calibrated significance test was claimed. [1]

**Interpretation:** this setup detected a small, consistently directed count difference, but the broader hydration profiles do not clearly separate the compounds. The salt-free simulations realized about 26.16-26.17 mM solute, rather than reproducing the source ice assay's 20 mM, 10 mM NaCl and -8°C annealing conditions. These known-label controls do not establish better ice inhibition or cell recovery.

<!-- page -->

# What is established, and what remains open

**The engineering outcome is established within the recorded checks.** Cryo can collect and trace selected evidence, reproduce selected deposited calculations, evaluate molecular models with grouped validation, run bounded GPU simulations, and recover verified results. The latest software verification records 98 distinct passing tests across the analysis and dedicated MD environments; standard discovery skips the MD tests when OpenMM is absent. Tests do not replace scientific validation. [3]

**The scientific outcome is a narrower decision boundary.** Immediate viability, recovered-cell yield and later function cannot be treated as interchangeable. The tested molecular models do not reliably recover all known strong inhibitors on withheld scaffolds. The matched hydration experiment offers a small count difference alongside overlapping full-profile variability. None of these results supports a validated new-compound efficacy ranking.

| Claim | Current evidence status |
|---|---|
| A reusable, auditable research and simulation workflow exists | Supported by repository artifacts, source hashes, tests and saved results. |
| Selected published numerical results were reproduced | Supported for the identified deposited tables and processed gene lists. |
| Leucine has a slightly higher nearby-water count in this setup | Supported descriptively by three preparations per compound. |
| More nearby water means better cryoprotection | Not established. |
| A new dual-action CPA or a superior combined formulation was discovered | Not established; no prospective laboratory experiment was conducted. |
| A universal optimum for cell growth, freezing and storage was found | Not established; the protocol benchmark is small and cell-context dependent. |

The effort also produced useful operational lessons. Source label conflicts, missing structures, endpoint normalization and molecular-state differences were retained rather than silently repaired. Fine-bin hydration metrics required longer sampling before they met the chosen engineering thresholds. A provider launch failure and three slow package-download failures in the latest stage were recorded, charged and cleaned up; only failed pre-simulation jobs were retried with the same planned inputs and seeds.

At the final check, cumulative GPU charges were estimated at **$4.077704**, with a conservative posted/elapsed reserve of **$4.078913**. All research Pods were absent and Phase 13 watchdogs/monitors stopped. Original downloads, trajectories and model binaries remain in local ignored `cryo-adata/`; code, curated records and reports are versioned in the private repository. Credentials remain outside Git. The GPU figure excludes other services, research labor and future laboratory costs. [3, 4]

<!-- page -->

# Next steps: obtain evidence about cryoprotection

The next budget should support a controlled laboratory feasibility study. Our proposed starting point is undifferentiated human iPSCs for recovery and identity qualification, with neuronal confirmation only after a condition earns advancement. The lab must confirm this scope and the available assays before a final protocol is written. [2]

**First, qualify materials and measurements.** Resolve the exact identity, formulation, exposure and washout of the shortlisted physical intervention, 2FA, and biological recovery cocktail, CEPT. Reproduce appropriate reference behavior, test nonfrozen tolerability, and measure ice-recrystallization inhibition separately in relevant formulations. The literature supports considering each intervention; their combined benefit remains an untested project hypothesis. [14, 15]

| Frozen treatment | Purpose |
|---|---|
| Standard freezing + defined standard recovery | Establish the matched reference. |
| Added 2FA + the same standard recovery | Estimate the physical-intervention contribution. |
| Standard freezing + CEPT recovery | Estimate the biological-recovery contribution. |
| Added 2FA + CEPT recovery | Test combined benefit and a prespecified interaction. |

CEPT replaces the defined recovery treatment in its arm; it is not silently stacked onto an existing ROCK-inhibitor cocktail. Hold base medium, vehicles, thermal handling, cell input and washing matched except for the declared factors. Mirror the four exposures in nonfrozen controls. Randomize allocation and blind outcome analysis.

**Second, measure yield and function separately.** Record live cells loaded before freezing, immediate live cells recovered after washing, and live-cell yield at 24 hours. Measure identity-qualified clonogenic output as a separate advancement gate. For neuronal confirmation, predeclare a functional readout and culture age alongside viable neuronal yield.

The draft feasibility design uses three donor lines, two independent batches per donor and two technical vials per arm: **48 core frozen vials**, plus controls and additional assays. This is not a power calculation. Biological inference uses donor/batch structure, not 48 supposedly independent donors.

**Third, confirm a promising result in new biological material.** The draft screening threshold proposes at least a 10-percentage-point 24-hour yield gain over both individual-factor arms, with donor consistency and tolerability/function gates. These are planning thresholds, not clinical standards. Finalize them before testing, estimate variability in the pilot, and size a separate confirmation study. Combined benefit does not automatically establish synergy; an interaction needs a defined scale and replicate-aware uncertainty. [2]

<!-- page -->

# How the pilot leads to discovery

A successful 2FA-CEPT comparison would nominate a formulation strategy. The original ambition of a **single dual-action molecule** remains a separate discovery task. A candidate must show direct physical ice protection at a compatible exposure, independently supported biological protection, and improved post-thaw functional recovery. Pathway annotation or docking alone would not establish suppression of a cell-death mechanism.

After assay qualification, assemble a small, chemically coherent panel with positive and negative controls. Verify identity, purity, solubility and formulation compatibility. Screen ice activity and nonfreezing biological protection separately, then advance qualifying candidates to the controlled cell-recovery assay. Confirm concentration dependence and the relevant mechanisms before claiming dual action. An improved mixture should be reported as a mixture, not as discovery of a multifunctional molecule.

The computational workflow can then become more useful: add assay-compatible measurements with structure, dose, buffer, timing, normalization and biological replicate metadata; freeze a source-separated or newly measured evaluation set before model selection; and compare models against simple baselines. Use predictions to prioritize experiments only after useful performance is demonstrated in the intended domain. Preserve unsuccessful candidates and experiments as well as successes. [8-10]

| Required input | Who provides it / why it matters |
|---|---|
| Target cell product and desired use | Project owner and laboratory; determines what recovery and function mean. |
| Laboratory partner and cell access | Experimental team; supplies qualified lines, handling and measurements. |
| Confirmed materials and assay capability | Laboratory, with source reconciliation from Cryo; makes the comparison interpretable. |
| Quoted experimental budget | Laboratory quote and project decision; separate from the $10 GPU authorization. |
| Prespecified decision and analysis plan | Joint planning; defines meaningful benefit, toxicity/function margins and confirmation design. |

No additional API or GPU service is required for this handoff. Missing source methods may require legitimate access or an authorized author request. Laboratory outreach, purchases and execution have not occurred. Costs and timelines require a laboratory scope and quote.

**Immediate deliverable:** a laboratory-ready study brief derived from the existing experiment matrix, with open material questions, counting definitions, controls, metadata template, proposed decision rules and a request for a feasibility quote. The present report and repository supply the scientific and computational background for that brief.

The eventual success criterion is independently replicated improvement in recovered, functional cells with acceptable toxicity and verified material identity. Claims should remain limited to the tested cell system and formulation until transfer, storage duration and scale are established.

<!-- page -->

# Sources and reusable project artifacts

This report synthesizes the completed repository state at commit `6b9dc855bca2b8de329367c49243f83dbc33bd82`. It adds no new experimental observations, molecular-model fits or GPU simulations. Source numbers below identify the supporting reports and primary publications. Repository links use the fixed evidence snapshot; access requires permission to the private repo.

[1] [Matched hydration comparison: methods, all six runs and figure](https://github.com/chasewhughes/cryo-discovery/blob/main/reports/matched-hydration.md).

[2] [Candidate shortlist and proposed four-arm laboratory handoff](https://github.com/chasewhughes/cryo-discovery/blob/main/reports/phase5-findings.md). The executable planning record is `data/phase5/experiment-matrix.json`.

[3] [Verification across phases](https://github.com/chasewhughes/cryo-discovery/blob/main/reports/verification.md); [final GPU reconciliation](https://github.com/chasewhughes/cryo-discovery/blob/main/data/phase13/compute-costs.json). Phase 13 also retains numerical and independent-summary audits.

[4] [Tooling and collection implementation](https://github.com/chasewhughes/cryo-discovery/blob/main/docs/tooling.md); [access setup](https://github.com/chasewhughes/cryo-discovery/blob/main/docs/access-setup.md); [local research storage](https://github.com/chasewhughes/cryo-discovery/blob/main/docs/storage.md). Historical setup counts are superseded by current coverage.

[5] [Current coverage and missingness](https://github.com/chasewhughes/cryo-discovery/blob/main/reports/coverage.json); [curated corpus](https://github.com/chasewhughes/cryo-discovery/blob/main/data/pilot-studies.json).

[6] [iPSC original-data analysis and limitations](https://github.com/chasewhughes/cryo-discovery/blob/main/reports/phase2-findings.md); [original deposited data](https://doi.org/10.5281/zenodo.14038512).

[7] [Cardiomyocyte original-data analysis and protocol benchmark](https://github.com/chasewhughes/cryo-discovery/blob/main/reports/phase3-findings.md); [primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12150479/).

[8] [Baseline IRI benchmark](https://github.com/chasewhughes/cryo-discovery/blob/main/reports/iri-benchmark.md); [Warren et al., original IRI study](https://doi.org/10.1038/s41467-024-52266-w); [pinned DOLMEN source](https://github.com/gcsosso/DOLMEN/tree/10ed726bed8158544222b5f16298a54013b6ad62).

[9] [Advanced model methods, errors and limitations](https://github.com/chasewhughes/cryo-discovery/blob/main/reports/advanced-iri.md).

[10] [Assay reconciliation and external-evaluation reservation](https://github.com/chasewhughes/cryo-discovery/blob/main/reports/iri-data-reconciliation.md).

[11] [Hydration pilot](https://github.com/chasewhughes/cryo-discovery/blob/main/reports/hydration-pilot.md); [ensemble/stability study](https://github.com/chasewhughes/cryo-discovery/blob/main/reports/hydration-stability.md).

[12] [Local descriptor definition](https://github.com/chasewhughes/cryo-discovery/blob/main/reports/hydration-definition.md); [sampling calibration](https://github.com/chasewhughes/cryo-discovery/blob/main/reports/hydration-sampling-calibration.md).

[13] [Longer hydration branches](https://github.com/chasewhughes/cryo-discovery/blob/main/reports/hydration-extensions.md).

[14] Alasmar et al. (2023). [Improved Cryopreservation of Human iPSCs and iPSC-derived Neurons Using Ice-Recrystallization Inhibitors](https://pmc.ncbi.nlm.nih.gov/articles/PMC10631806/). Stem Cells, 41, 1006-1021. DOI: 10.1093/stmcls/sxad059.

[15] Chen et al. (2021). [A versatile polypharmacology platform promotes cytoprotection and viability of human pluripotent and differentiated cells](https://www.nature.com/articles/s41592-021-01126-2). Nature Methods, 18, 528-541. DOI: 10.1038/s41592-021-01126-2.

**Terms used:** CPA = cryoprotective agent; iPSC = induced pluripotent stem cell; IRI = ice-recrystallization inhibition; MD = molecular dynamics; ns = nanosecond, one billionth of a second of modeled time. In the analysis, PDF means probability density function and MAE means mean absolute error.

**Named interventions:** 2FA is 2-fluorophenyl gluconamide. CEPT combines Chroman 1, emricasan, polyamines and trans-ISRIB; it is a recovery cocktail rather than a single molecule. [14, 15]
