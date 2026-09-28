# Phase 4 findings

Historical phase 4 snapshot. [Phase 5](phase5-findings.md) adds the ranked shortlist, experimental handoff, updated corpus and remaining queue.

The seven highest-priority candidates have now received a bounded acquisition and evidence review. Four were curated from primary full text, one from its abstract plus a verified public supplement, and two remain abstract-only. The corpus now contains **36 papers and 67 experiment summaries**: 28 full-text-material records, seven abstract-only records and one abstract-plus-supplement record. These categories describe inspected evidence, not independent replication or scientific validity. [Review status](../data/phase4/priority-review.json), [dataset](../data/pilot-studies.json).

## What changes the research direction

**CAMP provides a second concrete example of combined physical and biological protection, this time in a material system.** Its concave hyaluronic-acid/collagen microcarriers maintain cell attachment within an alginate/gelatin matrix. In the ice assay, reported mean large grain size was 21 ± 2.6 µm for CAMP versus 91.01 ± 9.3 µm for DPBS after annealing. In a separate perturbation, FAK inhibitor treatment reduced the reported post-thaw viability fraction from 0.68 ± 0.02 to 0.47 ± 0.10. These support distinct ice-control and adhesion-associated protection axes. They do not establish a dual-action small molecule, direct material–target binding or iPSC efficacy. The primary cells were human umbilical-cord MSCs; HUVECs and C2C12 cells provided additional checks. [Primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC13378309/), [reviewed extraction](../data/extractions/phase4-materials.json).

The inspected CAMP cell experiments used three days of cryostorage. Three-month bone regeneration in the article is a later animal outcome, not three-month storage validation. The explicit ice-grain endpoint also should not be substituted for the abstract's approximately tenfold IRI claim. The material system warrants a mechanistic comparison; its current data do not supply a universal cryoprotectant recipe.

**Extra ROCK-inhibitor pretreatment is not automatically beneficial.** In the R26 GMP iPSC cardiomyocyte-aggregate study, the condition labeled “10% HSA” includes CryoSure and final 10% DMSO. It had the highest observed day-5 mean recovery, 91.2 ± 50.1%, versus 71.2 ± 34.2% for CS10. Adding 10 µM Y-27632 for one hour before freezing did not significantly improve recovery or apoptosis outcomes. Both groups already received ROCK inhibition during the first 48 hours after thawing. Thus the comparison concerns additional pretreatment timing. [Aggregate study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12800097/).

Recovery above 100% immediately after thawing reflects uncertain aggregate counting, not proven cell creation during thawing. High variability and one donor line limit generalization. Spontaneous beating differed with pretreatment, but fresh age-matched aggregates showed little or no beating; that comparison cannot establish unchanged mature function. The exact HSA stock/label interpretation also needs clarification before replication. [Extraction and caveats](../data/extractions/phase4-cardiac.json).

**Good appearance or marker expression can coexist with altered delayed function.** A separate Phoenix-line cardiomyocyte study recovered about 39% of frozen cells with CS10 and 46% with KSR. Its recovery denominator is the number frozen, not the number remaining after thaw. At day 35, both frozen groups had lower twitch amplitude and altered contraction timing than fresh controls, despite relatively limited changes in sarcomeric gene/protein expression. Measurements came from one donor line, two differentiations and a small number of vials, with repeated cell/twitch observations. This supports delayed functional testing, not a pooled estimate that one medium is universally superior. [Contractile-function study](https://pmc.ncbi.nlm.nih.gov/articles/PMC13328489/).

**The EG/trehalose supplement clarifies chemistry and exposes culture-state constraints.** It specifies 12% **v/v** ethylene glycol plus 4% **w/v** trehalose, compared with 10% v/v DMSO plus 10% v/v FBS. Figure S11 concerns caspase-3 after CPA incubation; Figure S12 concerns TUNEL after cryopreservation. These are distinct exposure stages. Figures S2 and S14 additionally report crosslinking-associated iPSC injury and poorer protection with larger clusters/longer preculture. This argues for tracking matrix fabrication and culture age alongside CPA chemistry. [Public supplement](https://doi.org/10.1021/acs.biomac.5c00559.s001), [main article record](https://doi.org/10.1021/acs.biomac.5c00559).

The 15-page supplement was downloaded, checked by SHA-256 and read as a PDF; root visually inspected the caspase-3 and TUNEL panels. Exact bar heights were not digitized. The main article remains unavailable, and the supplement does not establish a complete loading/cooling/warming/storage schedule or donor-level replication. This record is explicitly classified as **abstract plus supplement**, rather than full primary text. [Retrieval details](../data/phase4/materials-access.json).

**Stored-cell usefulness is different from CPA causality.** The dopaminergic-progenitor paper reports approximately 84% immediate recovery after three months of storage, retained dopaminergic identity after thawing, and functional graft outcomes in rats. It uses a combined commercial freezing/recovery and differentiation workflow. The compound n-butylidenephthalide is a differentiation intervention here; the study does not establish it as an ice inhibitor or isolate its effect on freezing survival. Methods and results differ on spheroid diameter, and underlying raw imaging is author-request-only. [Primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC13316032/), [extraction](../data/extractions/phase4-neural.json).

## Remaining access and analysis work

The spaceflight culture paper remains abstract-only. Its reported survival above 85% is useful feasibility context, but formulation, replication and detailed handling remain unresolved. Cryoaerosolization also remains abstract-only and is a preprint. It reports high throughput and post-thaw outcomes, but its cached abstract contains an inconsistent CPA-range rendering; no exact composition was inferred. Public indexed snippets are insufficient for a complete method extraction, and failed/rate-limited requests were not repeatedly retried. [Spaceflight study](https://doi.org/10.1016/j.lssr.2025.08.002), [cryoaerosolization preprint](https://doi.org/10.64898/2026.07.24.740597), [access log](../data/phase4/process-access.json).

The remaining primary full-text queue contains **60 records: three high, 28 medium and 29 low priority**. Partial curation does not remove an inaccessible main article from that queue. The immediate public-source continuation is to review accessible medium-priority mechanistic studies while retaining these three access gaps. No new API subscription is necessary; author manuscripts, institutional reading access or author-supplied data would address the specific gaps more directly. [Queue](../data/phase4/fulltext-queue.json).

Several newly reviewed papers offer underlying data only on request. This phase therefore adds reviewed experimental summaries and constraints, not an independent raw-data reanalysis. It did not acquire a new omics count matrix, infer drug-target binding from expression changes or train a predictive model. The CAMP caption/results distinction between ATAC-seq peaks and gene-expression comparisons needs clarification before omics work.

## Concrete experimental handoff

The next research outputs should be evaluated against four questions:

1. Does physical ice protection add to biological protection under matched loading and thermal handling? Include vehicle/background, physical-only, biological-only and combined arms, with independent donor replication.
2. Does a material preserve function through adhesion signaling beyond the benefit explained by reduced ice injury? Include matrix-only, carrier-only and combined material controls, plus a pathway perturbation and a nonfreezing toxicity control.
3. Does a promising formulation remain effective across cell formats and culture ages? Compare formats within a matched cell source and keep aggregate counting, matrix processing and preculture duration explicit.
4. Does early recovered-cell yield predict delayed functional-cell yield? Measure the two separately; use lineage-relevant function, not marker expression alone.

The recommended iPSC discovery track remains a disclosed physical lead such as 2FA paired with a separately timed biological-protection reference; the new material evidence supplies mechanistic controls and transfer hypotheses, not permission to assume synergy. The prospective study must select its cell lineage, potency assay, independent donor/batch structure and budget with a laboratory partner. No experiments, author outreach or clinical validation were performed. [Existing 2FA/CEPT evidence and limitations](phase3-findings.md), [machine-readable research priorities](../data/phase4/hypothesis-portfolio.json).

## Reproduction and storage

```sh
python3 scripts/build_phase4_status.py
python3 scripts/validate_pilot.py
python3 scripts/audit_sources.py
python3 -m unittest discover -s tests
```

Sources, the PDF supplement and research temporary images remain in local `cryo-adata/`. Curated facts, scripts and reports are versioned in the private repository. Acquisition logs and [file hashes](../data/phase4/source-files.json) record the local evidence; a fresh clone requires those originals for the source-dependent audit. Screening and interpretation remain curated judgments rather than automated scientific validation.
