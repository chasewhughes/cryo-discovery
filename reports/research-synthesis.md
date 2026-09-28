# Cryo research pilot: findings and decisions

Historical phase 1 snapshot. Counts and acquisition status below describe the initial pilot; see [phase 2 findings](phase2-findings.md) for the current corpus, original-data analysis and revised interpretation of the 2024 IRI study.

2026-09-05 · Computational pilot, not laboratory validation

The most useful near-term outcome is a reproducible benchmark that links a preservation formulation and handling process to **absolute recovered cells and retained function**. The strongest next research direction is to test physical ice protection together with timed biological stress protection. A single molecule with both activities is a worthwhile discovery objective, but the present evidence does not establish such a molecule for human iPSCs.

## What this pilot delivers

The [dataset](../data/pilot-studies.json) contains 25 distinct primary papers and 36 selected experiment summaries: 18 papers reviewed from accessible full text and seven from abstracts. Six papers are classified as direct iPSC evidence, three as related pluripotent-cell evidence, ten as other mammalian-cell transfer evidence, five as methods-transfer evidence, and one as a cell-free physical-assay study. Classification is at paper level; individual experiments can use different models. The [evidence table](evidence-table.md), [coverage report](coverage.json), and [source audit](source-audit.json) are generated from the extraction files.

These summaries are not raw treatment-arm data, independent biological replicates, or a systematic review. Selection was purposive, beginning with relevant physical-protection, cytoprotection and protocol papers. The separate discovery backlog is unscreened and does not enlarge the evidence denominator. A larger reproducible search cannot retrospectively make this pilot exhaustive.

The [reference-compound table](../data/reference-compounds.json) resolves nine named reference compounds through PubChem. A CID or SMILES establishes a database identity, not cryoprotective efficacy. Polymers, commercial mixtures and numbered compounds in papers need separate material, lot, stereochemistry and structure curation.

## Findings that change the research design

**Biological protection has direct pluripotent-cell support.** The CEPT study compared several freezing and recovery conditions across five hPSC lines. Recovery-stage treatment produced much greater variation than the freezing additives in that experiment. CEPT contains Chroman 1, emricasan, a polyamine supplement and trans-ISRIB. It is a multicomponent cytoprotection reference; the study does not establish direct ice inhibition by the cocktail or its individual components. Its live-cell fraction and ATP measurements should not be relabeled as absolute recovered yield. [Primary study](https://doi.org/10.1038/s41592-021-01126-2).

**There is already direct iPSC evidence for small-molecule IRIs.** A 2024 study reports a 15 mM IRI formulation with 5% DMSO and examines recovery, viability, pluripotency and transcriptomic changes in three lines. The accessible abstract does not supply numerical effects or enough detail to reproduce the formulation. Obtaining and reviewing this paper's full text, supplements and linked expression dataset is a high-priority acquisition task. Reduced DMSO in this context is not evidence that all permeating CPAs can be removed. [Primary study](https://doi.org/10.1016/j.scr.2024.103583).

**Function and immediate viability can disagree.** In cord-blood progenitors, certain IRIs improved long-term culture-initiating cell yields in 10% DMSO, although immediate viability showed no general improvement and lower-DMSO conditions were not rescued. The long-term assay used only two cord-blood units. This is useful transfer evidence and a reason to measure potency separately from dye exclusion. [Primary study](https://doi.org/10.1021/acsomega.6b00178).

**Ice activity alone is an inadequate ranking target.** A modified antifreeze glycoprotein improved RBC recovery despite reduced IRI activity; membrane-interaction measurements suggested another contributor. Separately, PVA did not significantly improve platelet recovery or function in a small paired experiment. Neither finding invalidates IRI as a mechanism; both limit extrapolation across materials and cells. [Antifreeze-protein study](https://doi.org/10.1021/acs.biomac.1c01477), [platelet null result](https://doi.org/10.1111/trf.15395).

**Handling can rival chemistry.** Soluble extracellular nucleators reduced intracellular ice in A549 cells and improved preservation of monolayers and spheroids more consistently than suspensions. In a separate iPSC study, magnetic nanowarming improved viability in large-volume samples. Nucleation, sample geometry and warming therefore belong in the dataset and in experiments testing any new compound. They are potential confounders if left uncontrolled. [Nucleation study](https://doi.org/10.1021/jacsau.3c00056), [iPSC nanowarming study](https://doi.org/10.1038/s41598-020-70707-6).

**A combination approach is experimentally plausible.** Proline preconditioning and PVA co-cryoprotection improved A549 monolayer recovery in a reported combination. Proline was not itself an IRI in the physical assay. This is a useful precedent for complementary activities, with cell-type transfer and post-thaw growth as important qualifications. It is not evidence for a single dual-action molecule. [Primary study](https://doi.org/10.1039/d1md00078k).

**Prediction needs prospective biological validation.** A QSAR study achieved nine active compounds among 11 synthesized predicted-active candidates, measured by an ice assay. It did not demonstrate cell preservation. A separate semen-optimization study's final follow-up comparison was not significantly superior to commercial medium, despite promising earlier optimization. Cryo should test predictions on independent batches and report null results. [IRI QSAR study](https://doi.org/10.1038/srep26403), [optimization study](https://doi.org/10.1038/s41598-022-25104-6).

## Evergreen / Everlast and the dual-action objective

Exa identified [Evergreen Biosciences' Everlast technology page](https://www.evergreenbiosciences.com/technology). The company describes targeting intracellular stress pathways and presents viability/function claims. The page reviewed does not disclose a chemical structure or a direct ice-inhibition experiment. Treat this as a commercial lead requiring a technical evidence package, not a peer-reviewed mechanism result or proof of a dual-action CPA.

The separate [RevitalICE hematopoietic-progenitor paper](https://doi.org/10.3390/cells11020278) supports investigating post-thaw stress modulation. It must not be conflated with Everlast. Its full text alternates the names n-acetyl cystine and n-acetyl cysteine, and contains ambiguous concentration reporting. Those ambiguities remain explicit in the dataset; a supplier identity and corrected dose are needed before replication. Metabolic recovery in that paper is not engraftment validation.

For this project, call a candidate **dual-action** only after showing both (a) a direct physical effect in a cell-free, formulation-relevant ice assay and (b) biological protection separable from reduced upstream freezing damage, at compatible exposure concentrations. Lower caspase or ROS signals after freezing alone cannot distinguish those mechanisms. A combination of two agents remains a combination, even when it performs well.

## Prioritized hypothesis portfolio

The ranking below is an analyst judgment based on relevance, testability and evidence gaps. It is not a fitted efficacy score or a claim of chemical or patent novelty.

| Priority | Testable hypothesis | Evidence basis | Decisive next result |
|---|---|---|---|
| 1 | An iPSC-compatible IRI plus timed cytoprotection improves delayed absolute recovery without sacrificing pluripotency or differentiation | Direct iPSC IRI evidence and hPSC CEPT evidence, currently from separate studies | Combined treatment outperforms both single interventions across independent lines/batches; function passes predefined criteria |
| 2 | Nucleation and warming explain a substantial part of apparent additive performance in adherent or aggregate models | Direct ice measurements, geometry effects, iPSC nanowarming | Additive effect persists when actual thermal histories and sample geometry are controlled |
| 3 | Preconditioning can reduce the additive dose needed during freezing | Proline/PVA combination in A549; biological recovery-stage effects in hPSCs | Benefit survives washout and transfers to selected iPSC context without altered cell identity |
| 4 | A small-molecule scaffold can combine ice activity with compatible membrane or stress protection | IRI structure–activity data and protein membrane-interaction evidence; no validated iPSC single-molecule bridge | The same chemically verified molecule passes both independent mechanism assays and functional recovery gates |
| 5 | Data-driven formulation selection improves on expert baselines | Published IRI QSAR and formulation-optimization examples | Prespecified, blinded predictions improve on reference conditions in held-out biological batches |

See the [research and validation plan](../docs/research-plan.md) for experimental comparisons, outcomes and decision gates. No new molecule was synthesized, no prospective model was trained, and no laboratory efficacy was validated in this pilot.

## Quality and interpretation limits

Each selected summary has a DOI, source locator and short supporting excerpt. The source audit checks metadata and text matching; it does not prove that an interpretation is scientifically correct. Root review checked selected source passages and quantitative claims; it is not an independent expert review of every figure, supplement or paper.

Missing sample sizes, temperatures and follow-up times remain null or explicitly untranscribed. Missingness combines reporting gaps, extraction gaps and fields that do not apply to cell-free/nonfreezing experiments. Do not interpret it as an estimate of author reporting quality. Numeric effect fields are deliberately sparse because reported series and heterogeneous assays do not yield comparable effect estimates.

Seven abstract-only papers need full-text review before supplying laboratory conditions. No exhaustive retraction/correction or patent search has been completed. Related papers can share laboratories, chemical series or cells. The small, heterogeneous, correlated evidence base does not justify pooled efficacy estimates or machine-learning claims. The next computational investment should be deeper arm-level extraction, linked data acquisition and expert adjudication.
