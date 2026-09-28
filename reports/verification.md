# Pilot verification

## Phase 13 same-formula comparison verification

- Completed all six frozen independently prepared trajectories: leucine/isoleucine, three 10-ns productions each, plus 1 ns excluded equilibration per run. Each uses one zwitterion, 2,070 waters, CHARMM36/local TIP4P/Ice, 273 K and 1 bar. All 6,000 frames pass the physical-artifact checks and all six runs pass the four engineering stability criteria.
- Leucine mean count at 0.30 nm is 15.196 ± 0.088 SD across three runs; isoleucine is 14.978 ± 0.075. All cross-compound mean-count differences are positive, while full-PDF pair distances overlap within-compound variation. These are known-label control simulations, not independent efficacy validation, causal inference or new model fitting.
- All 98 distinct tests passed across environments: 79 in the analysis environment and 19 in the dedicated MD environment. Discovery in the analysis environment explicitly skips those 19 MD tests. Added checks cover matched identities/preparations, box-scale single-precision rounding, overlapping-pair summaries, selected result paths, stereochemical inversions and conservative retry reservation.
- Independent coordinate-derived starting identities verify S-leucine and (2S,3S)-isoleucine. Every saved production frame preserves its starting handedness. All-frame maximum rigid-water errors are 9.824e-07 nm (O–H) and 9.585e-07 nm (O–virtual site). Serialized systems/integrators match the parents except RNG seeds; final clocks, barostat/thermostat seeds, PDB boxes, trajectory checksums and finite normalized observables pass.
- All deployed source/input hashes match preserved Git sources: original attempted launch `0de333d`, attempt 2 `71ae10f`, attempt 3 `d1529e4`. The preparation metadata regenerated before deployment and local rounding-smoke history are explicit in the preparation and preflight records. The attempt-3 worker only extends software-installation time; integration settings and all six frozen seeds remain unchanged.
- The provider returned HTTP 500 during the first partial launch; its created Pod was deleted. Three attempt-2 workers later exceeded the package-download timeout before simulation. Only those exact preparation/production seeds were retried; failed logs and all charges remain preserved. The explicit result map prevents outcome-based selection among completed simulations.
- All 21 research Pods across phases are absent, and all Phase 13 local watchdog/monitor processes stopped. Three unrelated user Pods remain untouched. Phase 13 GPU charges are estimated at $2.067593; cumulative charges are $4.077704, below $10. Conservative posted/elapsed reserve is $4.078913; provider billing may be incomplete and include storage.
- A Luna assistant independently recomputed all per-run 0.30-nm count means, four flags, compound means/sample SDs, all six within-compound and nine cross-compound PDF distances and the group-mean PDF distance directly from NPZ arrays, without analyzer helpers. Checked numerical summaries match the main analysis exactly (maximum absolute difference 0.0); the audit retains trajectory hashes.
- Reserved earlier model hashes are unchanged. Root inspected the structures and final four-panel figure. Raw archives remain local in ignored `cryo-adata/`; the GitHub repository remains private.

## Phase 12 longer sampling verification

- Completed four selected 10-ns stochastic branches, totaling 40 ns new production and 0.4 ns excluded re-equilibration. All 4,000 frames use the unchanged 100-bin nearest-water descriptor; no old/new production pooling, new efficacy labels, or fitting.
- All four first-versus-second 5-ns comparisons pass the frozen engineering criteria. PDF TV spans 0.025480–0.031689; count, density and mean-temperature flags are also clear. The secondary 1-ns endpoint comparisons remain above 0.05, supporting sampling-duration sensitivity without proving equilibrium.
- All 80 distinct tests passed across environments: 63 in the existing research environment and 17 in the isolated MD environment. Standard discovery skips the 17 MD tests when OpenMM is absent. A single-precision OpenCL restart smoke check reproduced and verified the precision correction.
- The initial four-Pod attempt stopped before production because a 1e-9 saved-state tolerance rejected GPU rounding. All failed Pods were deleted, at an estimated $0.082034 cost. The successful retry retains the frozen scientific plan, uses separate storage/receipts and records maximum position restoration errors below 4.12e-7 nm; restored velocity errors are zero. Regression tests reject actual 0.001 nm or nm/ps displacements.
- All deployed files match pinned Git source: first attempt `cd6e72a`, successful retry `b1e126c`. Parent checksums, new RNG seeds, trajectory/system checksums, normalized PDFs, finite observations, fixed NVT boxes and density from mass/volume passed validation. The serialized physical system and integrator differ from their parents only in RNG seed attributes.
- Independent checks cover water O–H and O–virtual-site geometry across all 4,000 frames. Maximum errors are 1.039e-6 nm and 1.034e-6 nm; final clocks and PDB/state boxes pass. Reserved Phase 8 model hashes remain unchanged. Root inspected the final figure; a Luna assistant independently recomputed every primary result from NPZ arrays and found exact agreement.
- All eleven research Pods across phases and attempts are absent; all Phase 12 local watchdogs stopped. Three unrelated user Pods remain untouched. Estimated GPU cost is $0.956548 for Phase 12 including its failed attempt and $2.010111 cumulative, within the $10 limit. The conservative reserve using the larger of posted billing or elapsed estimates per Pod is $2.011319; provider records may be incomplete and include storage.
- The results establish engineering measurement stability only for these selected branches. They are not independent starting conformations, physical convergence proof, original DOLMEN-method reproduction, or cryoprotective efficacy validation.

## Phase 11 hydration stability verification

- Completed the frozen 12-run NVT/NPT comparison: two compounds × two ensembles × three seeds, 36 ns production plus 6 ns equilibration, and 3,600 saved frames. No new experimental labels or model fitting.
- All 58 distinct tests passed across environments: 48 in the existing research environment and ten MD tests in the isolated environment. Standard discovery skips the ten MD tests when OpenMM is absent. Additional local NPT smoke runs verified numerical operation and corrected PDB box output; these short runs do not establish physical equilibration.
- Reanalysis of all six Phase 10 trajectories exactly reproduced unique-water counts. The new nearest-water descriptor is explicitly versioned, and the small PHE PDF difference is reproduced by the old float32 arithmetic. Original DOLMEN production settings remain unresolved.
- Every cloud input and worker hash matches Git commit `06210fc`, which preserves the deployed source. The subsequent runner fix only updates final PDB box metadata. Original cloud PDBs are preserved alongside corrected copies; NPT trajectory/final-state boxes were already correct.
- Checked configurations, trajectory/system/source hashes, finite coordinates/observables, density from mass/volume and PDF normalization. Counts were independently recomputed on three frames per run. All water O–H and O–virtual-site distances were checked across all 3,600 frames: maximum errors were 7.83e-7 nm and 5.61e-7 nm. Serialized barostat settings, neutral solute charges and corrected PDB box precision passed checks.
- All 12 fine-histogram flags remain; no density, temperature or 0.30 nm count flag triggered. Post hoc mixing of 100 ps blocks and coarser binning are explicitly secondary, assumption-dependent diagnostics. They do not establish convergence or change the primary thresholds. Root and a Luna assistant reviewed the statistical interpretation.
- Root corrected a reporting-variable collision, verified 12 unique run IDs and plot-to-data mapping, and visually checked the final four-panel plot. No MD trajectory or experimental value was changed by the reporting fix.
- Retrieved the 342,322,684-byte result archive. The Phase 11 Pod and both prior research Pods are absent; the local Phase 11 watchdog stopped. Estimated GPU spending is $0.8354 this phase and $1.0536 cumulative, under the $10 user limit. Provider records have begun posting ($0.4569 at the last check), but Phase 11 billed-time coverage is incomplete. Elapsed-time GPU estimates exclude separately billed storage. Three unrelated user Pods were untouched.
- JSON, Python syntax, local report links, unchanged model hashes and deployed-source provenance passed checks. GitHub confirmed the repository is private.
- A deferred leucine/isoleucine control pair passed vacuum template construction and net-charge checks. No solvated MD of this pair or independent activity validation was performed.

## Hydration simulation verification

- Installed an isolated OpenMM environment; the existing model-fitting environment and model hashes are unchanged. The local CPU smoke run timed out, mixed-precision OpenCL context creation failed, and single-precision OpenCL completed a 2 ps production smoke test. These are numerical/compute checks, not experimental validation.
- Five MD tests passed: stereochemical/parent identity and terminal charge checks, water charge/LJ parameters and rigid virtual-site geometry, independent water-dimer energy, periodic unique-water counting, and rejection of unsupported box geometry. The existing 35 tests plus four mocked Pod lifecycle/budget tests passed separately; the MD tests use the isolated MD environment.
- Root checked main-paper MD methods, corrected an assistant's malformed WRAP URL, and verified downloaded source hashes. Original per-compound simulation topology/state and complete MD settings were not recovered. The reconstruction and its fixed-volume/duration limitations are explicit.
- Acquired the 2026 JCIS DOCX supplement and the 2025 ACS presentation supplement. Root inspected DOCX text and OLE relationships, presentation ZIP inventory/slide text and one preview image. Embedded OLE data and videos were not executed or numerically analyzed. No qualifying independent experimental rows were added.
- The first RunPod attempt failed CUDA PTX compatibility before producing a trajectory, and deletion was confirmed. CUDA components were pinned to 12.4 for the retry; the worker now requires an explicit successful CUDA force check. Lifecycle tests refuse deletion of a differently named Pod and distinguish a deletion request from confirmed absence.
- Completed all six prespecified production trajectories (three seeds each for glycine and phenylalanine, 1 ns per run). Result collection retrieved a 59,753,867-byte archive and confirmed deletion. A subsequent account inventory contained neither pilot Pod. Estimated GPU charges across both attempts total $0.2182; itemized billing records were not yet returned. Completed local watchdogs were stopped.
- Root inspected the descriptor discrepancy and pinned HIN routines. Post hoc nearest-water/radial-definition diagnostics retain all alternatives, without claiming the closest one proves the original DOLMEN settings. Simulated hydration outputs remain separate from experimental labels; no model was refitted.
- Verified all 600 trajectory frames for finite coordinates/energies and rigid-water geometry; maximum checked O–H and O–virtual-site distance errors were below 0.000001 nm. Source, trajectory, model and script hashes, Python syntax, Phase 10 JSON and local report links passed checks. Root visually inspected the final comparison figure.
- All 24 staged files were checked against four stored API keys, both transfer tokens, and AgentMail/RunPod key patterns with zero matches. Raw sources, trajectories and environments were excluded. GitHub confirmed the repository remains private.

## IRI data reconciliation verification

- Acquired the original Warren supplementary PDF through Europe PMC and the newer ACS experimental supplement through official Figshare. Root visually checked Warren pages 4 and 16 and inspected the ACS image-analysis methods; source hashes and the ACS metadata checksum are retained.
- Reconciled 80 Amino records without modifying source CSVs or prior models: 14 old prediction rows at nominal 20 mM, three explicit 10 mM exceptions, and 19 molecular-mass discrepancies (15 in training). A normalized-parent overlap check reduces the 14-row diagnostic to 12 nonoverlapping-parent records.
- Applied frozen Phase 8 fingerprint and standard models to the compatible legacy records; no refitting or full-ensemble claim. The small retrospective result is explicitly separate from independent external validation.
- Two newer experimental sources and two screened-out computational sources were logged. The ACS supplement was acquired but its conditions/endpoint are not yet compatible with pooled benchmark scoring; zero eligible external numeric rows are claimed. Model hashes and external-evaluation rules are reserved.
- All 35 tests passed, including four new concentration and molecular-parent checks. Python syntax, eight JSON documents, local report links, source/model/script hashes, cohort counts and concentration exclusions passed verification. The separate assistant mass audit agrees with the generated records. Root visually checked ACS supplement page 7, including its grain-area endpoint and reference to generated Excel observations.
- All 15 staged files were checked against three stored API keys and the AgentMail pattern with zero matches; raw sources and environments were excluded. GitHub confirmed the repository remains private.

## Advanced IRI model verification

- Acquired four hydration-descriptor files at the pinned DOLMEN commit, totaling 243,063 bytes. Normalized-name joins retain missing and ambiguous data; standard rows were checked by name/order. Descriptor and molecular-state uncertainties remain documented.
- Ran three inner-tuned model families and a fixed equal-weight ensemble on the exact Phase 7 outer folds, with preprocessing confined to training folds. Saved all parameter trials, nested splits, out-of-fold predictions and paired group-error summaries. These reused development folds are not an independent final test.
- Root and a Luna assistant reviewed the descriptor joins and nested-validation logic. Full-cohort models were saved separately from evaluation, and their custom estimators have importable module identities for later loading.
- All 31 tests passed, including six new identity, nesting, kernel and serialization tests. Figure layout was visually checked. No new molecule, reliable improvement on unseen scaffolds or biological efficacy was claimed.
- Both saved model bundles loaded in a fresh process and produced finite component predictions. Saved nested groups, Python syntax, JSON, links and recorded hashes passed checks. All 13 staged files were checked against three stored API keys and the AgentMail pattern with zero matches; raw sources/models and environments were excluded. GitHub confirmed the repository remains private.

## First virtual IRI benchmark verification

- Acquired ten small DOLMEN files at commit `10ed726bed8158544222b5f16298a54013b6ad62`, plus primary article XML and Figure 4. Inputs are hashed and retained locally in ignored storage; upstream code was not executed.
- Parsed all structures and separated assay conditions. Used 63 Amino training/test rows and 209 Glyco2 22 mM rows; the 124-record Glyco overlap was not added. All 17 Amino prediction records remain quarantined because of concentration metadata conflicts.
- Root visually checked Figure 4 and rejected an assistant's incorrect compound-8 mapping. Primary-source concentration exceptions are retained without unsupported CSV corrections.
- Ran fixed median, ridge and random-forest baselines under five-fold scaffold and connectivity grouping. Saved fold membership, out-of-fold predictions, metrics, paired group-error intervals, environment versions and provenance hashes. Cross-validation is retrospective, not new experimental validation.
- A Luna assistant reviewed the split/fitting code for label leakage and candidate interpretation. Root checked the model results, exact 2FA membership and poor held-out 2FA prediction. No novel hit or biological prediction was claimed.
- All 25 tests passed in the scientific environment; the six new tests were rerun after strengthening the held-out-label test to exercise the actual evaluation function. Figure layout was visually inspected.
- Python syntax, Phase 7 JSON, report links, recorded result hashes, saved split membership and installed dependency pins passed checks. All 16 staged files were checked against the three stored API keys and AgentMail pattern with zero matches; no raw sources or environment files were staged. GitHub confirmed the repository remains private.

## Phase 5 verification

- Four medium-priority studies were added after root selected-source review: three primary full texts and one abstract. Corpus: 40 papers/75 experiment summaries, comprising 31 full-text-material, eight abstract-only and one abstract-plus-supplement record.
- Three high-priority access gaps received one bounded additional route check each; no complete new source was obtained for them. The remaining primary full-text queue has 57 records.
- Published porcine-embryo survival means were used for three descriptive additive-interaction calculations. Results are −1.34, +0.29 and −3.58 percentage points. These are not replicate-level hypothesis tests or proof against other interaction models.
- Two percentage/aggregate-count discrepancies were retained as aggregation-clarification flags, not silently corrected. Potential fresh-control column misalignment was excluded from inference. An independent Luna read-only review confirmed that the source reports group-comparison ANOVA, not interaction/equivalence tests.
- CEPT motor-neuron evidence was revisited; its nonsignificant day-7 MEA comparison is now explicit. No significant functional superiority was inferred from it.
- The six-candidate ranking is an ordinal research judgment, not a pooled efficacy score. The four-arm matrix, 48-vial feasibility design and advancement thresholds are proposed planning choices; no experiment or power claim is implied.
- Schema validation passed for all 40 papers and 75 experiment summaries, and the automated source audit returned zero metadata/excerpt flags. These provenance checks are separate from the two scientific aggregation-clarification flags above. All 19 offline tests passed. Python syntax, Phase 5 JSON, local report links, the 48-vial arithmetic, remaining-queue consistency and Git whitespace checks passed.
- Sources/downloads remain local in `cryo-adata/`; no author outreach, purchases or laboratory execution occurred.
- All 22 staged files were checked against the three locally stored API keys and the AgentMail key pattern: zero matches and no raw-storage files staged. GitHub confirmed `chasewhughes/cryo` remains private.

## Phase 4 verification

- Seven high-priority records were reviewed: four primary full texts, one abstract plus an independently downloaded public supplement, and two abstracts. The corpus has 36 unique papers and 67 unique experiment summaries (28 full-text material, seven abstract-only, one abstract-plus-supplement).
- Root checked selected full-text methods/results and corrected assay denominators, ROCK-inhibitor dose/timing, formulation context, negative results and replicate layers before publishing the dataset.
- The ACS supporting PDF is 15 pages and 1,972,053 bytes; its SHA-256 matches the recorded download. Root read its captions and visually inspected Figures S11 and S12 on PDF pages 10 and 11. No bar heights were digitized or underlying measurements independently reanalyzed.
- The supplement remains explicitly separate from main-article access. The updated audit checks declared supplemental text together with abstract metadata. The queue builder retains partial-access records: 60 primary full-text candidates remain, including three high-priority access gaps.
- Schema validation passed for all 36 papers/67 experiment summaries; the local source audit returned zero metadata/excerpt flags. All 17 offline tests passed, including preservation of partially reviewed records in the queue and support from declared supplementary sources. Python syntax, JSON, report links and whitespace checks passed.
- No new public omics count matrix or author-request dataset was acquired. Source interpretation is not independent expert review, wet-lab validation, retraction clearance or novelty/patent clearance.
- Original sources and temporary images remain local in `cryo-adata/`, excluded from Git. No messages to authors or paid-service setup were performed.
- Staged content was checked against all three locally stored API keys and the AgentMail key pattern, with no matches and no raw-storage files staged. GitHub confirmed the repository remains private.

## Phase 3 verification

- Corpus: 29 unique papers and 50 unique experiment summaries; 24 full-text-material and five abstract-only records. Geometry uses selected indexed institutional-manuscript text, with journal-version agreement unverified.
- All 79 selected priority/uncertain backlog records have archived abstracts and assistant first-pass screens. Root checked metadata and selected abstracts/scope assignments; this is not independent expert review of every abstract. Two preprint versions are grouped with journal records.
- The 2025 cardiomyocyte supplement was downloaded through its publisher link, validated as an XLSX ZIP, and checked by SHA-256. All 60 recovery observations, 18 calcium summary observations and 72 optimizer population entries were read without modifying the original workbook.
- Final recovery means reproduce 92.0625% for Solution A, 89.875% for B and 80.1875% for DMSO. Population SD and sample SEM are explicitly separated. The calcium amplitude/normalization discrepancy and missing composition map remain unresolved.
- Root visually inspected cardiomyocyte Figures 2 and 6. A Luna assistant performed a separate read-only check of the original-data analysis. No new significance tests or donor-independence claims were made.
- The prior iPSC original-data analysis reran successfully after adding optional worksheet selection to the shared XLSX reader.
- Three structured protocol records retain 10 conditions, source locators, null values, endpoint definitions and replication gaps. They are not validated laboratory SOPs.
- Final schema validation passed for all 29 papers/50 experiment summaries. The local source audit returned zero metadata/excerpt flags, and all 15 offline tests passed. Python syntax, phase 3 JSON, local report links and Git whitespace checks passed.
- Staged files were checked against all three locally stored API keys and the supplied AgentMail key pattern, with zero matches. No raw/download/storage files were staged. GitHub confirmed `chasewhughes/cryo` is private.
- Sources and downloads remain in local `cryo-adata/`, excluded from Git; no additional account setup or author outreach was required.

## Phase 2 verification

- Corpus: 26 papers, 41 experiment summaries; 21 full-text and 5 abstract-only records.
- All 27 deposited recovery values and six overall recovery/viability means independently recomputed; cross-workbook sample labels checked.
- Fifteen selected archive files verified against actual RAR headers and decompressed CRCs; SHA-256 provenance recorded. Whole-archive checksum was not verified.
- Figure 3 gene-list arithmetic reproduces 492 genes in the union and 166 shared across treatments; this is not independent differential-expression modeling.
- Raw sources moved to ADATA: all 45 initial research files verified by SHA-256 before local removal; temporary-file routing and wrong-volume rejection checked.
- The user subsequently transferred the research files into local `cryo-adata/`. All 45 initial migration hashes and all 15 selected archive-file hashes match. Relative repository links now point there, and temporary-file writes were verified locally.
- Dataset validation passes; 11 offline tests pass. The original-data analysis reran successfully from local storage, and the source audit passed for 26 papers and 41 experiments with zero flags. No external drive is required.
- These checks establish consistency and provenance, not scientific validity.

## Initial pilot snapshot

Checked 2026-09-05.

- Dataset validation: 25 unique papers, 36 uniquely identified experiment summaries, zero schema errors.
- Local source audit: zero metadata/excerpt-provenance flags across the 36 summaries. This is an automated provenance check, not independent scientific validation.
- Offline tests: seven passed, covering schema rejection, missing fields, nonfinite effects, Europe PMC response structure, HTML text extraction, and preservation of successful metadata when a refresh fails.
- Python scripts/tests compiled successfully.
- Nine PubChem identity lookups succeeded. The stored response includes available fields; absence of an isomeric representation must not be filled from a guessed structure.
- Two successful, capped discovery queries produced 194 deduplicated records; none overlaps the selected pilot DOI set. All 194 remain unscreened. Two other queries failed with HTTP 503 and are logged separately.
- A later metadata refresh succeeded for four of 25 DOIs during service disruption. Previously archived metadata remained intact; a Crossref lookup supplied the additional paper's metadata. Failed refresh records cannot replace successful records in the audit.
- Repository candidate files were checked against the three locally stored API keys and the supplied AgentMail key pattern; no credential matches were found. Raw downloaded sources and Python caches are excluded from Git.

Selected source claims were reviewed and corrected by the root agent. This is not a completed systematic review, exhaustive supplement extraction, independent expert audit, retraction/patent clearance, or laboratory validation. The evidence summaries explicitly retain transfer limits, abstract-only status and untranscribed fields.
