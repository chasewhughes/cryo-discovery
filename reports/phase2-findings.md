# Phase 2 findings

Historical phase 2 snapshot. [Phase 3](phase3-findings.md) supersedes its current corpus counts and abstract-screening status.

This bounded computational follow-up covers **26 selected papers and 41 experiment summaries**: 21 reviewed from accessible full-text material and 5 from abstracts. All 194 backlog records received root-reviewed title screening: 67 advance to abstract review, 51 remain background, 64 are excluded at title level, and 12 remain uncertain. Seven priority abstracts represent five apparent studies after grouping two journal/preprint pairs. The 67-record abstract-review queue is not complete. This is a discovery corpus, not an exhaustive systematic review. [Screening](../data/phase2/backlog-screening.json), [priority abstracts](../data/phase2/priority-abstract-review.json).

## Direct iPSC evidence

Independent recalculation of all 27 cryovial recovery values and six overall recovery/viability means reproduces the 2024 study's deposited spreadsheets. Three donor lines each have three technical vials per arm. The SD below is between donor-line means, not uncertainty across 27 independent donors. [Study](https://doi.org/10.1016/j.scr.2024.103583), [original dataset](https://doi.org/10.5281/zenodo.14038512), [calculations and cell locators](../data/phase2/iri-2024-analysis.json).

| Formulation | Immediate recovery, mean ± SD | Immediate viability, mean ± SD |
| --- | ---: | ---: |
| CS10 | 51.2 ± 9.7% | 84.3 ± 2.6% |
| 15 mM IRI-I in CS5 (IRI-I5) | 64.1 ± 11.6% | 85.3 ± 0.9% |
| 15 mM IRI-I in CS10 (IRI-I10) | 49.2 ± 10.9% | 80.7 ± 5.0% |

Recovery is post-thaw viable yield divided by prefreeze viable yield. Viability is the live fraction among counted post-thaw cells. IRI-I5 improves mean recovery over CS10 by **12.86 percentage points**, but line-specific differences are +15.87, +2.75 and +19.95 points. Corresponding 24-hour confluence differences are −12.61, −3.59 and +3.05 points. Immediate recovery therefore does not consistently predict faster growth. The recovery workbook retains legacy iPSC-1/2/3 labels in one column; clone IDs and the viability workbook establish the final iPSC-4/5/6 mapping. Original files were preserved unchanged. [Deposited measurements](https://doi.org/10.5281/zenodo.14038512).

The separate pluripotency workflow lost iPSC-5 during thaw/recovery in IRI-I10 and by first passage in CS10 and IRI-I5. After two passages, three surviving line/arm combinations were classified pluripotent and three borderline. All recovery arms used a ROCK inhibitor background. There is no CS5-only freezing arm, and IRI arms equilibrated differently from CS10; the comparison cannot isolate IRI causality. Full-text review used an author-uploaded pre-proof's methods/results, checked alongside deposited figures and measurements; a complete local published PDF was not obtained. [Curated extraction and limitations](../data/extractions/biological.json).

The 2024 study’s exact tested structures are proprietary N-aryl glyconamides. The available materials do not support mapping its IRI-I and IRI-II labels to the named compounds in the 2023 neuron study; those are distinct nomenclatures.

The newly curated 2023 study identifies **2-fluorophenyl gluconamide (2FA)** and three other IRIs. In iPSC-derived neurons, 5 mM 2FA increased recovered-cell yield to 50.3% versus 32.2% for CS10; immediate viability itself did not improve significantly. Cultures with 2.5 or 5 mM 2FA developed robust synchronous activity by day 27 and bursting by day 48, versus synchronous activity after day 130 in CS10 and 10 mM 2FA. Figure 5 reports 3–4 MEAs and data representative of two differentiations; electrodes are readout replicates. Y27632 allocation and inconsistent control labels in figure legends need clarification for replication. This prioritizes a **known compound for further testing**, without establishing a direct cell-death target mechanism. [Primary full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC10631806/), [extraction](../data/extractions/neurons-2023.json).

## Physical and protocol evidence

The upgraded mouse-oocyte full text reinforces warming-rate dependence, but assesses morphology and osmotic viability rather than long-term development or iPSC function. [Oocyte study](https://doi.org/10.1016/j.cryobiol.2010.10.159), [review](../data/phase2/oocyte-fulltext-review.json).

Priority abstracts identify bottom-up freezing geometry, DMSO-free cardiomyocyte formulations and GMP cardiomyocyte aggregates as leads for full-text curation. Journal/preprint pairs must each count once in study-level synthesis. These differentiated-cell results do not establish an optimum for undifferentiated iPSCs. [Geometry](https://doi.org/10.1002/btpr.70019), [DMSO-free cardiomyocytes](https://doi.org/10.1186/s13287-025-04384-5), [GMP aggregates](https://doi.org/10.1038/s41598-025-32439-3). Multifunctional trehalose derivatives are also relevant, but the screened abstract reports lower recovery than its DMSO comparator. [Trehalose study](https://doi.org/10.1039/d6tb01172a).

## Omics and hypotheses

The complete archive header inventory covers **4,141 files**. Fifteen selected files were retrieved using bounded HTTP ranges, with original RAR headers, decompressed CRCs and SHA-256 hashes checked. A full 3.5 GB download was unnecessary; whole-archive MD5 was not verified. [Retrieval manifest](../data/phase2/archive-index.json), [data deposit](https://doi.org/10.5281/zenodo.14038512).

The deposited lists reproduce Figure 3:

| Gene-list operation | Downregulated | Upregulated | Total |
| --- | ---: | ---: | ---: |
| Union across treatments | 399 | 93 | **492** |
| Shared by all three treatments | 128 | 38 | **166** |

These inputs were already intersected across cell lines by the authors. A different analysis of combined contrast tables yields 712 shared Ensembl IDs after adjusted p ≤ 0.05 and absolute fold change >3. It must not be substituted for Figure 3's comparison. [Calculations and definitions](../data/phase2/iri-2024-analysis.json), [author analysis code](https://gitlab.com/uniluxembourg/lcsb/developmental-and-cellular-biology/mommaerts_2022).

This reproduces processed-list arithmetic, not RNA-seq alignment, normalization, model fitting or multiple-testing adjustment. No count matrix or sample annotation table was identified in the complete archive inventory. The exploratory code includes several analysis branches and later hg38 paths; its earlier hg19 path alone does not establish the published reference version. Unfrozen baseline and 24-hour post-thaw samples differ in handling and culture time. Count/sample data and final analysis-version clarification are needed before independent differential-expression or pathway inference.

The leading hypothesis is a paired strategy: a disclosed physical-ice intervention such as 2FA plus a separately timed biological-protection arm, retaining vehicle, physical-only and biological-only controls. Measure recovered functional cells, with viability, yield and delayed function separate. Second, match formulation and thermal handling to identify whether benefit comes from chemistry, protocol or their interaction. Third, curate DMSO-free cardiomyocyte formulations as cell-domain-specific comparators. These are research priorities, not demonstrated synergistic combinations.

No new CPA is validated by this phase. The next handoff is a prospective lab study using multiple independent donor lines, blinded matched freeze/thaw runs, immediate viability plus recovered cell yield, delayed confluence/function, and a formulation-matched thermal control. Access to proprietary 2024 materials and complete author raw data remains necessary for a definitive replication; no additional public API access is required.

## Reproduction and storage

Original articles, tables, figures and temporary data now reside in the local `cryo-adata/` directory through relative repository links, using the user's transferred copy. Code, curated data and reports remain in the private repository; original downloads remain excluded from Git. No author outreach or experimental validation was performed. [Storage instructions](../docs/storage.md).

```sh
python3 scripts/with_external_storage.py -- python3 scripts/collect_zenodo_tables.py
python3 scripts/with_external_storage.py -- python3 scripts/analyze_iri_data.py
python3 scripts/validate_pilot.py
python3 scripts/with_external_storage.py -- python3 scripts/audit_sources.py
python3 -m unittest discover -s tests
```

XLSX inputs were read as ZIP/XML and relevant calculations independently recomputed with standard-library Python. Workbooks were not edited or authored; the spreadsheet authoring runtime was unavailable. Figure 2 and Figure 3 were visually checked against extracted data. Source availability remains a reproducibility dependency; five corpus papers remain limited to abstracts.
