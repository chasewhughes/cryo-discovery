# Phase 5: shortlist and experimental handoff

This focused pass adds four selected studies and eight experiment summaries, bringing the corpus to **40 papers and 75 summaries**. Three new papers were reviewed from primary full text; the amino-acid trehalose paper remains abstract-only. The complete corpus has 31 full-text-material records, eight abstract-only records and one abstract-plus-supplement record. All three previously identified high-priority access gaps remain unresolved after a bounded additional pass. [Review status](../data/phase5/review-status.json), [access-gap log](../data/phase5/high-priority-access.json).

The main output is a **ranked research shortlist and a concrete four-arm experiment matrix**. The ranking is a judgment about usefulness for the proposed iPSC program, considering reproducibility, functional evidence, toxicity and transfer limits. It is not a pooled efficacy score or a claim of a newly discovered drug. [Machine-readable shortlist](../data/phase5/ranked-shortlist.json), [experiment matrix](../data/phase5/experiment-matrix.json).

## Ranked shortlist

| Priority | Candidate | Why pursue it | Main limitation / next gate |
| --- | --- | --- | --- |
| 1 | 2FA | Disclosed physical IRI with direct iPSC and neuronal recovery/function evidence | Reconcile recovery co-treatment and dose effects; confirm identity and lot |
| 2 | CEPT | Defined biological recovery cocktail with multi-line hPSC evidence | No established ice activity; lineage-specific function and combination with 2FA remain unvalidated |
| 3 | Polyampholyte formulation | Delayed THP-1 recovery plus direct intracellular-ice imaging | Leukemia-line transfer evidence; polymer identity and plate nucleator effects need separation |
| 4 | EG + trehalose | Supplement confirms a defined DMSO-free mixture and iPSC microsphere comparisons | Main loading/thermal methods unavailable; cluster size and culture age matter |
| 5 | CAMP | Material-level ice control plus FAK-inhibitor perturbation | Multicomponent bioink, not a small molecule; adhesion and physical-injury controls needed |
| 6 | Recombinant CspB | Physical ice assay plus biological-pathway perturbation | Animal oocyte evidence; protein construct and kit handling need confirmation |

The first experiment should test the top two as **separate timed interventions**, retaining their individual arms. It should not assume that either molecule or cocktail already provides both mechanisms. Prior full-text evidence supports this nomination, with important limits: the CEPT motor-neuron MEA comparison at day 7 reports p=0.5023, so it does not establish significant neuronal functional superiority. Its early viability evidence is stronger than that particular functional comparison. [2FA](https://doi.org/10.1093/stmcls/sxad059), [CEPT](https://doi.org/10.1038/s41592-021-01126-2).

## What the new evidence adds

The polyampholyte study used **THP-1 monocytic leukemia cells**, not primary donor monocytes. At 24 hours, the reported recovered-cell fractions were 77% with polyampholyte versus 34% with the DMSO comparison and 17% with CS5. It also assessed delayed apoptosis, growth and macrophage-like differentiation. Cryo-Raman examined five cells per condition; the numerical ice estimates should not be read as population percentages of ice-positive cells. Plate experiments added a pollen-derived nucleator as well as polymer. These are useful physical-mechanism and handling references, not proof of a direct cell-death target or iPSC benefit. [Primary monocyte study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12147442/), [reviewed extraction](../data/extractions/phase5-biological.json).

The enzymatic L-PTAA oligomer showed sequence-specific ice inhibition, yet its best sheep-red-cell recovery was only 34% in the reported freeze/thaw assay. Recovery was derived from hemolysis, rather than absolute counted viable-cell yield. Other sequence orders did not provide the same protection, and higher doses were not necessarily better. It is therefore a lower-priority physical structure–activity lead. [Primary peptide study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12651731/).

The amino-acid trehalose diesters combine acellular radical scavenging with physical-property measurements, but their abstract reports **lower overall recovery than 10 wt% DMSO**. Favorable compatibility or radical scavenging alone does not demonstrate a useful dual-action cellular mechanism. Exact dose, handling and cryopreservation-model allocation remain unresolved, so these derivatives stay below the more reproducible leads. [Trehalose primary record](https://doi.org/10.1039/d6tb01172a), [chemistry extraction](../data/extractions/phase5-chemistry.json).

## Combination benefit is not the same as synergy

The porcine-parthenote paper includes single and combined treatment groups, making it useful for testing the interpretation of combination claims. Using its **reported survival means**, the additive interaction is `I = R11 − R10 − R01 + R00`:

| Comparison | Combination minus better component | Additive interaction |
| --- | ---: | ---: |
| Berberine × melatonin | +6.71 pp | −1.34 pp |
| Fe₃O₄ × AFP I | +5.37 pp | +0.29 pp |
| Antioxidant pair × nanoparticle/AFP pair | +8.64 pp | −3.58 pp |

The combinations have higher means than either component arm, but these figures do not establish supra-additive synergy. The source reports one-way ANOVA/Tukey group comparisons, not an interaction or equivalence test. These calculations are descriptive, depend on the response scale and may be affected by ceiling effects. Without replicate-level outcomes/covariance, no interaction uncertainty or significance was calculated. A Luna assistant independently checked this interpretation. [Primary combination study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12729773/), [reproducible arithmetic](../data/phase5/combination-analysis.json).

Two displayed percentages differ from their parenthetical count ratios beyond ordinary rounding. For example, the combined hatching entry in Table 4 is 83.90% with 73/85, while that aggregate ratio is 85.88%. Replicate-averaged percentages can differ from pooled ratios, so these are **requests for aggregation clarification**, not proof of errors. Table 6 also appears to misalign fresh-control cytoskeleton/ROS entries; the dataset preserves them without repair and excludes them from interpretation. Embryo morphology/hatching and zona digestion do not establish implantation, offspring outcomes or iPSC efficacy.

## Proposed first experiment

For planning, use undifferentiated human iPSCs for initial recovery/clonogenic qualification, then test nominated conditions in iPSC-derived forebrain neurons. This is a proposed research scope, not a finalized laboratory SOP. The lab must confirm lineage, materials and assay capacity.

| Arm | Physical factor during freezing | Recovery factor |
| --- | --- | --- |
| A00 | No added 2FA | Defined standard recovery |
| A10 | 2FA | Same standard recovery |
| A01 | No added 2FA | CEPT |
| A11 | 2FA | CEPT |

CEPT replaces the defined standard recovery treatment in its factor arm; it must not silently be added on top of another ROCK inhibitor. Hold base freezing medium, vehicle, loading, density, container, thermal handling, storage and wash constant except for the declared factors. Mirror the exposure combinations in nonfrozen controls and measure physical ice behavior separately. The matrix contains literature dose anchors; they are not universal recommended doses.

A proposed feasibility design uses **three donor lines × two batches per donor × two technical cryovials per arm**, or **48 core frozen vials**, plus nonfrozen controls. This is not a power calculation. Analyze donor/batch contrasts; vials, wells, images and electrodes are nested observations. Choose confirmatory sample size after measuring variation.

The pilot's proposed screening rule is a ≥10-percentage-point improvement in 24-hour viable-cell yield over both individual-factor arms, positive direction in at least two donor lines, and no donor losing more than five points against its better individual-factor arm. Matched nonfrozen viability and identity-qualified clonogenic output should not fall more than 10% relative to the handling reference. **These are planning thresholds, not literature-derived or clinical acceptance standards.** Assay precision and margins must be finalized before testing. Passing only nominates a candidate for confirmation.

Count live prefreeze input, immediate post-wash recovered cells and 24-hour live-cell yield separately. Assess identity-qualified clonogenic output as a separate advancement gate. For neuronal confirmation, predeclare a fixed-age MEA endpoint and functional margin, alongside neuronal yield. Do not multiply an arbitrary network metric by cell recovery and call it “functional yield.” Test both planned component contrasts, and estimate a replicate-aware interaction if a synergy claim is intended.

## Requirements and completion status

No additional public API subscription is needed. The three high-priority papers still require a usable author manuscript, institutional reading access or another legitimate complete source. The remaining full-text queue has **57 records: three high, 25 medium and 29 low priority**; the focused shortlist does not depend on exhausting that queue. [Remaining queue](../data/phase5/fulltext-queue.json).

The computational handoff is ready for laboratory planning. Execution requires a laboratory partner, selected cell lines, confirmed material/formulation details, calibrated potency/counting assays, and a quoted experimental budget. No materials were purchased, authors contacted, experiments run or new molecule validated. Broader literature curation can continue, but it cannot substitute for these prospective measurements.

Reproduce the arithmetic and corpus checks with:

```sh
python3 scripts/with_external_storage.py -- python3 scripts/analyze_combination_tables.py
python3 scripts/validate_pilot.py
python3 scripts/audit_sources.py
python3 -m unittest discover -s tests
```

Original sources and research temporary files remain in local `cryo-adata/`, excluded from Git. The findings, shortlist, experiment matrix and source-linked calculations are versioned in the private repository.
