# Cryo workspace storage

The user transferred the research files into `cryo-adata/` inside this repository
and now authorizes local storage. Use that local copy; an external drive is not
required. Keep source code, curated JSON and reports versioned in Git.

- Read [docs/storage.md](docs/storage.md) before downloading or extracting data.
- Use `data/raw` for original sources, `data/downloads` for bulk archives and
  `data/tmp` for staging; these are ignored relative links into `cryo-adata/`.
- Run downloads and extraction through `scripts/with_external_storage.py` to
  verify the local paths and set child-process temporary storage. The command
  retains its old name for compatibility; it no longer checks an external drive.
- Keep `cryo-adata/` excluded from Git, including large original downloads.
- Explicitly direct application outputs and caches into these research paths.
- Do not change personal Downloads or move unrelated projects.

# GPU spending

- As of 2026-09-06, the user authorizes at most **$10 total cumulative GPU
  spending** for this research, including completed pilots and failed attempts.
  The previously mentioned $17 account credit is not the spending authorization.
- The completed Phase 10 attempts have an estimated combined GPU cost of
  $0.2181551203502549; reconcile provider billing before further rentals.
- Before renting more compute, count costs across all research phases and
  reserve the full maximum cost of each proposed job, including setup and
  shutdown time, with a margin for billing uncertainty. Keep automatic deletion
  and confirm cleanup. Do not launch a job that could exceed the remaining budget.
- The existing $3 Phase 10 pilot guard remains a narrower limit; this new total
  does not by itself change the pilot launcher or authorize spending all $10.

- Phase 11 is complete and its Pod was deleted. Cumulative estimated research
  GPU charges through Phase 11 are $1.0535631704833772, including both Phase 10
  attempts. See `data/phase11/compute-costs.json`; this is not a final invoice.
  Count this spending against the same $10 total before any future rental.

- Phase 12 is complete: four 10-ns branches passed the frozen measurement
  stability criteria. Its initial failed four-Pod attempt and successful retry
  are both preserved and all Pods were deleted. Cumulative estimated research
  GPU spending is **$2.010110793032911**, including all failed attempts;
  conservative posted/elapsed reserve is $2.0113193684325785. See
  `data/phase12/compute-costs.json` and reconcile again before any further rental.
  Do not remove batch state or overwrite prior receipts to rerun completed jobs.

- Phase 13 is complete: leucine/isoleucine, three independently prepared 10-ns
  trajectories each (60 ns production, 6 ns excluded equilibration), with all
  six runs passing the engineering stability checks. All attempt-1/2/3 Pods are deleted;
  completed production must not be rerun by removing batch state or receipts.
  Cumulative estimated GPU spending is **$4.077704162975152**; conservative
  posted/elapsed reserve is $4.07891273837482. See
  `data/phase13/compute-costs.json` and reconcile before future rental under the
  unchanged **$10 cumulative limit**. Full-PDF differences overlap replicate
  variation despite a consistent small water-count difference; no efficacy
  validation or new model fitting was performed.

- Phase 16 completed a Boltz-2 two-control execution pilot. Both controls produced
  structures and affinity outputs; exploratory ordering passed, quantitative accuracy
  remains unvalidated. All 24 allocated research Pods are confirmed absent as of
  2026-09-06 15:54 UTC. Cumulative estimated GPU spending is **$4.2375473805990485**;
  receipted posted/elapsed reserve is **$4.239140075162026**. An ambiguous attempt-3
  provisioning intent still reserves **$0.90** (no Pod observed), making the total
  conservative reserve **$5.139140075162026**. Its independent local watchdog remains
  responsible for deadline reconciliation; inspect its raw intent reconciliation
  and rerun billing reconciliation before another rental. See
  `data/phase16/compute-costs.json` and `data/phase16/attempt3-unresolved-intent.json`.
  Preserve all attempt directories, receipts and frozen plans; do not rerun completed
  pilot controls by deleting history. The cumulative user cap remains **$10**.

- Phase 17 completed the 43-compound ROCK2 panel with two fixed Boltz-2 seeds
  (86 validated predictions). The frozen internal benchmark point estimate passed:
  35.8% lower MAE than the mean baseline, Spearman 0.744. The scaffold-bootstrap
  improvement interval is 6.4–43.2%, crossing the 20% criterion. This is not
  external validation, a novel-compound discovery, or cryoprotection evidence.
  All 25 allocated research Pods are confirmed absent as of 2026-09-06 20:17 UTC.
  Cumulative estimated GPU spending is **$5.044127053637637**, conservative
  posted/elapsed reserve **$5.046261394191754**, and pending intent reserve **$0**.
  Phase 17 itself cost an estimated $0.8065796730385886. These are not final
  invoices; reconcile again before renting under the unchanged **$10** total cap.
  See `data/phase17/compute-costs.json`. The Phase 16 pending intent described
  above was resolved with no Pod; see `data/phase17/prior-intent-resolution.json`.
  Preserve all attempt directories, receipts, archives and frozen plans. Do not
  rerun the completed panel by deleting state or altering frozen scientific code.

- Phase 18 completed the separate 30-compound ROCK2 assay evaluation (60 outputs,
  seeds 1801/1802) with a frozen 12-compound calibration / 18-compound test split.
  All outputs passed archive/provenance checks. Raw transfer failed (MAE 0.834
  versus source-mean baseline 0.586; Spearman 0.448). Held-out assay calibration
  reduced MAE from 0.843 to 0.433, but Spearman 0.441 and 12.4% improvement over
  the calibration-mean baseline missed the 0.5 and 20% gates. Novel screening
  remains unqualified; do not retune on the 18 test compounds and reuse them as
  validation. The dataset preserves 17 source-supported unit corrections.
  The executed plan is `data/phase18/external-plan-transport.json`; preserve the
  original unallocated plan, all frozen sources, attempt state, archive and receipt.
  Attempt 1 Pod `zphm3xolawgfsz` was deleted and its local watchdog stopped.
  All 26 research Pods are confirmed absent as of 2026-09-06 22:38 UTC.
  Phase 18 estimated GPU cost is $0.7309103458735677; cumulative estimate is
  **$5.775037399511205**, conservative reserve **$5.782577468230589**, pending
  reserve **$0**. See `data/phase18/compute-costs.json`; these are not final invoices.
  Reconcile before future rentals under the unchanged **$10 cumulative cap**.

- Phase 19 completed an exploratory paired-readout diagnostic on 13 reused Phase18
  compounds. Raw MAE was 0.744 against luciferase and 0.445 against IMAP;
  Spearman remained weak (0.423/0.457). No new calibration, independent validation
  or novel screening was performed. Four candidate source audits did not yield
  an eligible independent non-luciferase panel; see `data/phase19/eligibility-decision.json`.
  Phase19 cloud adapters are locally tested but unfrozen; no GPU allocated.
  All26 prior research Pods were absent at 2026-09-06 23:05 UTC. Cumulative
  estimate remains $5.775037399511205; conservative reserve $5.782577468230589,
  pending reserve zero. See `data/phase19/compute-costs.json`. Reconcile again
  before renting under the unchanged $10 total cap. Do not treat the reused
  Phase18 compounds as a fresh held-out test or relax eligibility to force a run.

- Phase20 completed the 50-compound2019 chromen radiometric ROCK2 evaluation:
  100 validated outputs, seeds2001/2002,20 calibration/30 heldout compounds.
  Raw transfer passed (MAE0.442,48.8% gain,Spearman0.864). Heldout calibrated
  MAE0.484/rho0.681 passed, but absolute bias0.262740 exceeded0.25; the joint
  screening gate remains failed. The better source-only offset is diagnostic,
  not permission to replace the frozen calibration gate after seeing results.
  Preserve the plan `data/phase20/validation-plan.json` SHA256
  `9d2ccdde7e18c6afca971a8455210c16985a663a7b2223195bc1116d20771da6`,
  source audits, attempt1 archive and receipts. Do not rerun or retune on the
  30 test compounds (only3 scaffold groups). No cryoprotection conclusion.
  Pod `0yxtfvfbx9ll7u` was deleted, local watchdog stopped, and all27 research
  Pods confirmed absent at 2026-09-07T00:45:24.563945+00:00;3 unrelated Pods untouched.
  Phase20 estimated GPU cost $0.976284955888; cumulative
  estimate $6.751322355400, conservative reserve
  $6.763735318538, pending zero; remaining
  $3.236264681462 under the unchanged $10 total cap.
  See `data/phase20/compute-costs.json`; estimates are not final invoices.
  Reconcile again before any rental and create a new frozen plan for a
  different experiment. See `reports/rock2-radiometric-validation.md`.
