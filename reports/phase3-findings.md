# Phase 3 findings

Historical phase 3 snapshot. [Phase 4](phase4-findings.md) updates the corpus, priority full-text review and remaining queue.

The corpus now contains **29 selected papers and 50 experiment summaries**, including three newly curated studies. Twenty-four records use accessible full-text material and five remain abstract-only. This phase adds original cardiomyocyte-data recomputation, a structured preservation-condition benchmark, and first-pass abstract screening of all 79 priority/uncertain backlog records. It identifies research leads and replication gaps; it does not establish a novel compound or a universal optimum. [Dataset](../data/pilot-studies.json), [condition benchmark](../data/phase3/protocol-benchmarks.json).

## Findings that change the research priorities

**Dual physical and biological protection is a plausible research direction, but the strongest newly reviewed example is a protein in animal oocytes.** Recombinant Polaribacter CspB showed ice-recrystallization inhibition and protected mouse/bovine oocytes in a DMSO-free formulation that still contained 15% ethylene glycol. Mouse survival with 2 mg/mL CspB was 89.93% versus 61.33% without CspB in the EG-only comparison. Removing both DMSO and EG lowered survival to 28.43% even with CspB. An mTOR activator reversed stress-marker protection, supporting pathway involvement without demonstrating direct CspB–mTOR binding or selective inhibition. GFP localization at the oocyte periphery is a separate experiment from the ice assay. Developmental endpoints followed parthenogenetic activation; they were not live-birth outcomes. [CspB primary study](https://doi.org/10.3390/antiox15010107), [reviewed extraction](../data/extractions/cspb-2026.json).

This makes CspB a useful mechanistic reference for the proposed dual-action strategy, not an established human-iPSC drug lead. Its reported recombinant construct is 21.9 kDa; sequence, tag and purity must be confirmed rather than substituting another protein called CspB. The existing disclosed small-molecule lead, 2-fluorophenyl gluconamide (2FA), has direct iPSC-neuron recovery/function evidence, but no established direct cell-death target in the curated study. CEPT supplies a separate biological-protection reference. Combining these interventions remains an untested hypothesis in this corpus. [2FA study](https://doi.org/10.1093/stmcls/sxad059), [CEPT study](https://doi.org/10.1038/s41592-021-01126-2).

**High immediate recovery can coexist with impaired function.** The 2025 DMSO-free cardiomyocyte study uses trehalose, glycerol and isoleucine in Normosol R. Recalculation of its original supplement reproduces these final-validation results:

| Final formulation | Recovery mean | Population SD | Sample SEM | Observations |
| --- | ---: | ---: | ---: | ---: |
| Solution A | 92.0625% | 2.5023 pp | 1.4447 pp | 4 |
| Solution B | 89.8750% | 4.1740 pp | 2.4098 pp | 4 |
| 10% DMSO | 80.1875% | 4.2219 pp | 2.4375 pp | 4 |

Recovery is live post-thaw cells divided by live prefreeze cells, not the live fraction among remaining cells. Solution A exceeds the final DMSO comparator by **11.875 percentage points**. The earlier optimization-stage DMSO value of 69.4% is a different comparator and cannot be substituted here. Solution B retained high recovery but had reduced calcium-signal amplitude. The study used one engineered CCND2 donor line, so four observations are not four independent donors. [Primary study and supplement links](https://pmc.ncbi.nlm.nih.gov/articles/PMC12150479/), [recomputed observations and cell locators](../data/phase3/cm-2025-analysis.json).

The supplement contains 60 recovery observations across three panels, 18 calcium summary observations, and 72 optimizer population entries across eight generations. These are different panels/populations, not 150 independent experiments. Repeated optimizer survivors may recur between generations. Original XLSX data were read without modifying the workbook; Figures 2 and 6 were visually inspected. [Retrieval URLs and hashes](../data/phase3/dmso-free-cm-review.json).

Three limitations prevent treating this as a transferable optimized recipe. Figure 2 uses arbitrary-unit ingredient levels and the inspected supplement provides no absolute concentration map. DMSO-free loading lasts 60 minutes versus 30 minutes for DMSO, confounding formulation and loading effects. Finally, the recovery prose's ± values reproduce population SD despite a general SEM legend, and all 18 stored calcium amplitudes equal peak minus minimum while the paper labels the endpoint F/F0. Upstream normalization is unresolved; the analysis preserves the stored values and does not silently relabel them. Nonsignificance versus fresh cells is not evidence of equivalence. [Analysis and explicit limitations](../data/phase3/cm-2025-analysis.json).

**Physical process design matters, and a relative scale-up advantage can mask lower absolute performance.** In one engineered WTC11 iPSC line, bottom-up nucleation with 5% DMSO, 90-second seeding and 2 °C/min cooling produced reported vial values of 87% membrane integrity and 62% metabolic signal. At 30 mL, bottom-up versus passive-bag values were 69% versus 60% membrane integrity and 31% versus 23% metabolic signal. Neither assay establishes absolute recovered viable-cell yield. The passive bag's cooling rate was not reported, so geometry cannot be separated cleanly from thermal history. Neuronal differentiation was assessed morphologically on days 5–8, without electrophysiology. [Journal record](https://doi.org/10.1002/btpr.70019), [institutional manuscript](https://sapientia.ualg.pt/bitstreams/4474ed9c-3a46-4a50-ac33-6736025b8720/download).

That extraction uses selected indexed methods/results from an institutional manuscript; exact agreement with the journal version remains unverified. Methods describe 72-hour storage, while results describe two days. The benchmark retains the inconsistency and the full medium context, including serum replacement and ROCK inhibition. [Reviewed extraction](../data/extractions/geometry-2025.json).

## Screening and next acquisition queue

All 79 records selected from phase 2 received assistant abstract screening, using four cached Europe PMC requests. Root review checked publication metadata and selected abstracts/scope assignments. The final counts are 66 advance to full-text review, eight background, two excluded, one uncertain and two linked preprint versions. Three advancing records were curated this phase, leaving **64 full-text candidates: seven high, 28 medium and 29 low priority**, including the unresolved-model record. This is not independent expert screening of every abstract. The other 115 records in the original title-screened backlog were not reassessed here. [Screening decisions and review provenance](../data/phase3/abstract-screening.json), [retrieval log](../data/phase3/abstract-retrieval.json), [remaining queue](../data/phase3/fulltext-queue.json).

Review articles are retained as background, adult stem cells are separated from pluripotent cells, and nonmammalian ice assays are retained only as transfer/context leads. The cardiomyocyte journal/preprint relationship is supported by Europe PMC links; the geometry version group uses matching bibliographic/manuscript evidence. Neither preprint is counted as an additional curated study.

The next acquisition pass should prioritize the seven high-priority full texts, especially cardiomyocyte contractile impairment, GMP cardiomyocyte aggregates, encapsulated iPSCs, and CAMP bioink. CAMP's abstract reports both ice inhibition and phospho-FAK-associated protection, but it remains an abstract-level lead here. Amino-acid-functionalized trehalose remains a medium-priority chemistry lead; the attempted publisher route did not yield usable full text. Include negative results and failed formulations when extracting these sources. [CAMP](https://doi.org/10.1002/adma.72714), [trehalose derivatives](https://doi.org/10.1039/d6tb01172a).

## Analysis and sharing plan

Build toward a condition-level dataset whose rows specify cell identity/donor, growth medium and passage, CPA composition and exposure, container/density, cooling/nucleation, storage, warming/wash, recovery medium, assay denominator and follow-up time. The new three-study benchmark demonstrates this structure, explicitly retaining unknown values. It is a research extraction, not an executable laboratory SOP. [Benchmark](../data/phase3/protocol-benchmarks.json).

The highest-value prospective comparison separates physical protection, biological protection and their combination under matched thermal/loading conditions, with vehicle/background controls. Assess absolute functional-cell recovery, delayed function and toxicity alongside ice behavior, and distinguish independent donor lines from vials and assay wells. An ice-inactive protein/material control and an ice-matched comparator would help determine whether biological signaling changes merely follow reduced freezing injury. This is a proposed validation design, not a tested combination or an experimental result.

Keep descriptive analyses separated by cell domain and endpoint. Fifty heterogeneous experiment summaries do not support a pooled efficacy score or a validated discovery model. Before any predictive modeling, obtain arm-level composition/outcome matrices and sample identities, deduplicate publication versions, and plan validation that holds out whole studies and donor lines. Continue sharing curated facts, source links, uncertainty fields and reproducible code through the private repository.

**No additional API or paid service is required for the next public-source pass.** Existing public literature routes and supplied credentials are sufficient. Exact formulation maps, underlying cell-count/calcium data, protein construct details and independent donor validation are scientific inputs that another search API cannot supply. Author clarification or laboratory collaboration would be needed for those gaps; no author outreach was performed. Original downloads remain local in `cryo-adata/`, excluded from Git. [Storage](../docs/storage.md).

## Reproduce this phase

```sh
python3 scripts/with_external_storage.py -- python3 scripts/fetch_screening_abstracts.py
python3 scripts/with_external_storage.py -- python3 scripts/analyze_cm_data.py
python3 scripts/with_external_storage.py -- python3 scripts/analyze_iri_data.py
python3 scripts/validate_pilot.py
python3 scripts/audit_sources.py
python3 -m unittest discover -s tests
```

Screening and protocol judgments are curated records, not an automatically reproduced scientific review. Source-dependent analyses require the archived files; public URLs and hashes document acquisition. Automated validation checks consistency and provenance, not scientific validity, exhaustive literature coverage or novelty/patent clearance.
