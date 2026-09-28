# IRI assay reconciliation and independent-data acquisition

This pass resolves the concentration mapping for the old Amino prediction set, records molecular-state inconsistencies, and acquires a newer experimental supplement. **It does not add new training labels or establish an independent external test.** The existing model artifacts and prior benchmark results remain unchanged.

## Resolved assay records

We downloaded the original 27-page Warren supplementary PDF through Europe PMC and visually checked its structure diagram on page 16. Combined with the main Figure 4 caption, it identifies the three compounds measured at 10 mM despite the CSV listing 20 mM:

| Main figure number | Compound | Curated concentration |
| --- | --- | ---: |
| 7 | Ethyl 2-amino-5-methyl-1,3-oxazole-4-carboxylate | 10 mM |
| 8 | Dichlorotyrosine derivative: (2s)-2-amino-3-(3,5-dichloro-4-hydroxyphenyl)propanoic acid | 10 mM |
| 9 | 5-Nitropyridine-2-carboxylic acid | 10 mM |

The mono-chlorotyrosine is compound 6 and remains at nominal 20 mM. The generic Supplement Figure S10 caption also says 20 mM; the curated record follows the main text's explicit exceptions while retaining that conflict. No source CSV or experimental outcome was overwritten. [Main paper](https://doi.org/10.1038/s41467-024-52266-w), [reconciled records](../data/phase9/assay-reconciliation.json).

This separates the 17 old prediction records into **14 at nominal 20 mM and three at 10 mM**. Two of the 14 share molecular connectivity/normalized parent identity with training compounds, although their stereochemistry differs. Excluding those leaves **12 records without normalized-parent overlap**. Related chemical series can still overlap.

The supplement also contains an unrelated biological-methods inconsistency: page 4 names a thiazole carboxylic acid as compound 7, whereas the IRI structure diagram identifies an oxazole ester. We do not repair that wording or use it to establish a new compound-to-cell-protection link.

## Frozen-model retrospective check

We evaluated the existing Phase 8 Amino fingerprint model without refitting. The standard-descriptor SVR is a secondary comparison; the full ensemble was not used because compatible hydration vectors for these records are absent from the repository.

| Diagnostic subset | n | Frozen fingerprint MAE | Frozen standard SVR MAE | Training-median MAE |
| --- | ---: | ---: | ---: | ---: |
| Nominal 20 mM records | 14 | 20.24 | 20.16 | 22.24 |
| Excluding normalized-parent overlap | 12 | 20.82 | 21.37 | 22.42 |

Errors are in % mean grain size points. The three 10 mM records were not scored against the 20 mM model. The modest differences do not establish strong predictive reliability: this is a small, source-selected set whose labels were already visible to the research team. It is **retrospective diagnostic evidence**, not a newly blinded or independent test. [Diagnostic plan](../data/phase9/retrospective-plan.json), [predictions and metrics](../data/phase9/retrospective-diagnostic.json).

## Molecular-state audit

Across the 80 Amino records, 19 archived exact-mass features disagree with masses recomputed from supplied SMILES; 15 are in the 63-record training cohort. The differences are approximately one proton in mass, consistent with differing molecular states but insufficient to identify the original preparation or simulation state. Some names specify chloride salts while their SMILES omit chloride.

The new records preserve source SMILES, formal charge, both masses and the discrepancy. Charge/tautomer normalization is used only to detect potential overlap, not to assert a measured pH or replace all compounds with a presumed assay species. Recomputing a single feature would not reconcile the rest of a state-dependent representation. [Molecular-state review](../data/phase9/molecular-state-audit.json).

## New external sources

Two post-cutoff experimental sources were identified; neither DOI appears in the existing 40-paper corpus. We acquired the public 24-page ACS supplement, verified its checksum, and inspected its assay methods. Its panel includes small molecules alongside proteins and polymers. Reported low-molecular-mass conditions include 1 mM, and the analysis produces grain-area distributions over several times. A table with normalization directly compatible with the current 20/22 mM %MGS models has not been obtained. It is a useful **condition-shift source**, not a poolable test set. [ACS source and public supplement](https://acs.figshare.com/articles/journal_contribution/Do_Inhibition_Studies_of_Ice_Crystallization_Indicate_Cryoprotectant_Efficacy_/29185191).

The second source studies a triphenyl-imidazolium ionic-liquid series with different counterions and self-assembled structures. Full methods, source-supported machine-readable structures and numeric activity tables remain to be acquired. Its physical assembly mechanism also requires a separate applicability assessment. [Publisher record](https://doi.org/10.1016/j.jcis.2026.140021).

Two additional theoretical/simulation papers were screened out as sources of new experimental labels. No activity values from the newer papers were added to model training, and no results were digitized from their plots. Source screening included public abstracts and assistant review, so it is not a formally blinded trial. [Acquisition and eligibility log](../data/phase9/external-source-leads.json).

## Evaluation reservation and next acquisition

The [external-evaluation plan](../data/phase9/external-evaluation-plan.json) specifies assay compatibility, structure overlap, frozen models and reporting rules. The [reservation record](../data/phase9/model-reservation.json) fixes model hashes and records **zero eligible external numeric rows so far**. Publication date alone is not proof of independent measurements, and a new measurement of a known compound is distinct from new chemistry.

The next required data are source-level grain measurements with compound identities, final concentrations, buffer/pH, anneal conditions, endpoint normalization and replicate grouping. The acquired ACS supplement says its analysis generated Excel grain data, but those machine-readable observations have not been located in the acquired material. Full method/data access for the ionic-liquid study is also unresolved. Public repository acquisition can continue; obtaining unpublished records would require an explicitly authorized data request, and producing new measurements would require a laboratory.

No additional paid API is needed for the available public sources. More subscriptions alone would not resolve assay incompatibility. The present deliverables improve provenance and clarify which data can be compared; they do not demonstrate improved prospective efficacy prediction.

## Reproduction and checks

With the existing pinned scientific environment and Phase 7/8 sources/models:

```sh
python3 scripts/with_external_storage.py -- python3 scripts/fetch_iri_reconciliation.py
python3 scripts/with_external_storage.py -- .venv/bin/python scripts/reconcile_iri_data.py
python3 scripts/with_external_storage.py -- .venv/bin/python -m unittest discover -s tests
```

The two source PDFs, acquisition metadata and temporary page renders remain local in ignored `cryo-adata/`. Source hashes, original model hashes, concentration exceptions, overlap counts and script provenance were checked. The PDF pages used for structure mapping and selected methods were visually inspected. No purchases, author messages, model retraining or laboratory work occurred.
