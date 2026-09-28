# Cryo research and validation plan

Version 0.1 · 2026-09-05

Initial planning snapshot. [Phase 2 findings](../reports/phase2-findings.md) records completed follow-up: 194 title screens, two full-text upgrades, one new primary paper, 27 original cryovial measurements and processed expression-list reconciliation. Current remaining work is stated there; acquisition and analysis statements below describe the original starting point.

## Desired outcomes

1. **An auditable evidence resource:** normalized cell identities, chemical/material identities, growth and recovery conditions, freezing/storage/warming protocols, outcomes, uncertainty, provenance and reuse rights. Success means another researcher can reconstruct why a candidate or process was selected.
2. **A cell-specific preservation benchmark:** reference conditions with reproducible absolute recovery and retained function. An optimum is conditional on cell state, scale, handling, cost and downstream use; there is no defensible universal best CPA from this pilot.
3. **A tested hypothesis portfolio:** prospective comparisons that distinguish physical protection, biological protection, protocol effects and interactions. Negative and inconclusive outcomes are retained.
4. **A validated discovery, if experiments support it:** a formulation, handling improvement or chemically identified dual-action molecule with independent replication. This is a future empirical outcome, not something literature synthesis alone can deliver.

The completed pilot supplies the first evidence slice, source tools and hypothesis handoff. It does not yet contain a comprehensive cell-culture-condition database or raw arm-level measurements.

## Procure and curate data

| Data layer | Sources and access | Required fields and next action |
|---|---|---|
| Literature discovery | Europe PMC, PubMed/NCBI, OpenAlex, Crossref; Exa for leads | DOI/PMID/PMCID, dates, version relationships, query/date/source, inclusion decision and reason. Deduplicate before extraction; supplement keyword searches with backward/forward citation searches. |
| Full text and supplements | Permitted PMC/Europe PMC routes, publisher OA pages, institutional access when supplied | Section/figure/table locators, license and retrieval hashes. Acquire seven currently abstract-only papers, starting with the 2024 iPSC IRI paper. Do not treat a PMCID as a guaranteed downloadable XML file. |
| Cell culture and protocols | Methods/supplements, Cellosaurus, provider protocols, public protocol repositories where reuse permits | Line ID, donor, passage, differentiation day, aggregate size, confluence, medium, matrix, oxygen, dissociation, growth factors, feeding, density, assay timing. Archive protocol versions. Commercial medium ingredients may remain unknown. |
| Chemical identity and activity | PubChem, ChEMBL, BindingDB; structures and synthesis details in supplements | Canonical parent and salt/stereoisomer identity, supplier/lot, purity, concentrations and units. Keep polymer molecular-weight distribution, hydrolysis and lot separate from small-molecule identity. Numbered compounds are unique within a DOI until structures are verified. |
| Mechanism | Primary perturbation assays, Reactome/UniProt context; LINCS/CLUE if access is later available | Target, assay type, cell context, exposure, vehicle, binding versus phenotypic evidence. A pathway annotation is not a measured cryoprotective mechanism. |
| Omics and raw outcomes | GEO/SRA, BioStudies, Zenodo, Figshare, Dryad, article-linked repositories | Accession, sample/condition mapping, biological replicate, raw/processed status, QC and license. Resolve accessions from papers before downloading large files. No expression dataset has been analyzed in this pilot. |
| Commercial leads | Evergreen technical material and any public primary disclosures | Exact product identity, composition disclosure status, controls, actual ice assays, delayed recovery and potency, independent replication. A company presentation belongs in a lead register until evidence is reviewable. |

Existing credentials and public endpoints suffice for continued literature and identity collection. CLUE access, publisher entitlements, proprietary datasets and an experimental partner are additional inputs only when the corresponding stage is selected. AgentMail and Brave MCP are available for access setup; no researcher outreach campaign is part of the current collection.

Use bounded metadata searches first. Preserve total-hit and returned-hit counts, query truncation, date cutoff, and per-query provenance. Treat the current backlog as unscreened. Two-pass screening should include title/abstract triage followed by full-text eligibility, recording exclusion reasons. Reviews guide discovery but do not contribute experimental effect estimates. Link journal/preprint versions, corrections and retraction notices; do not count versions as independent studies.

For each included paper, extract arm-level records into linked study, material, protocol, experiment, measurement and provenance tables. Record raw numerator/denominator where available. Distinguish cells seeded, cells frozen, live cells recovered, live fraction among counted cells, proliferation, and assay fluorescence. Separate biological units from wells/images. Keep reported values separate from digitized or calculated values; digitization requires figure coordinates, uncertainty and reviewer sign-off. Store both reported and normalized units, never an inferred denominator.

## Analyze in stages

**First, measure coverage and comparability.** Build matrices by cell model, material class, mechanism, treatment stage, thermal protocol and endpoint. Prioritize gaps important to the chosen application, not publication count. Identify shared laboratories/material series and repeated experiments across papers.

**Second, establish matched contrasts.** Compare treatments within a study at matched cell state, CPA base, concentration basis, exposure, storage and warming. Report delayed absolute recovery separately from immediate viability and lineage-specific function. Keep unfavorable conditions. Use effect sizes with uncertainty only when raw data or adequate summaries and replicate definitions support them.

**Third, analyze accessible molecular datasets.** Confirm sample identities and experimental design before differential expression. Preserve donor/batch pairing, normalize appropriately for the assay, correct multiple testing, and conduct pathway analysis with an explicit tested-gene background. Changes associated with freeze–thaw injury are hypotheses; treatment reversal is not proof of causality. No omics download or analysis should be represented as completed until accession-level data are available.

**Fourth, model only after a comparable benchmark exists.** Begin with interpretable baselines and prospective prioritization. Split by chemical scaffold, study and biological batch as relevant; avoid leakage from the same compound, donor or replicate across folds. Include negative examples and uncertainty. Use active learning to select informative, feasible experiments rather than maximize a literature-derived survival score. The 25-paper pilot is insufficient for a validated prediction model.

## Prospective validation handoff

Primary proposed use case: human iPSC banking, initially in suspension. This is a planning assumption, not a user-selected cell product. Define the exact lines, intended differentiation/function and vessel scale with the laboratory before choosing operating conditions. Adherent and aggregate formats should be separate transfer stages.

Start by reproducing a documented reference freezing/recovery workflow. Run a factorial comparison of physical additive present/absent and biological recovery intervention present/absent while holding the base CPA and thermal process fixed. Include fresh untreated cells, fresh cells exposed to each intervention/vehicle, and the frozen reference. Later compare CPA reduction or alternate nucleation/warming in separate prespecified blocks; do not change all variables simultaneously.

Measure the following as distinct outcomes:

- Absolute live-cell yield relative to input, immediate and delayed after thaw, including detached cells where meaningful.
- Membrane integrity plus an orthogonal death/metabolic assay; delayed measurements after washout distinguish lasting benefit from transient assay effects.
- Pluripotency/identity and subsequent differentiation or application-specific functional potency.
- Direct physical ice activity in the actual formulation, along with nucleation temperature, cooling/warming history, osmotic load and material compatibility.
- Nonfreezing biological stress protection and target/perturbation evidence to test a mechanism independently of ice injury.

For a dual-action molecule, require verified chemical identity and purity, direct ice activity at a cell-compatible dose, independently supported biological protection, and combined functional recovery. Membrane effects may represent a useful second activity, but must not automatically be relabeled as death-pathway inhibition. Assess mixtures separately from single compounds.

Use independent lines/donors and experimental batches; randomize condition positions within each batch and blind outcome analysis. Technical wells improve measurement precision but do not increase donor-level sample size. Estimate variance in a feasibility run, then prospectively set biological sample size and power for the primary endpoint. Specify a biologically meaningful recovery threshold and noninferiority margin for function before confirmatory experiments, with the laboratory's application requirements. Do not select these thresholds after seeing results.

Analyze treatment effects and interactions with the appropriate biological blocking structure. A positive combination effect is not automatically synergy: test an interaction on a predefined outcome scale. Report confidence intervals, multiplicity handling and all planned outcomes. Confirm selected hits in a new batch and, ideally, another laboratory. Test storage duration, shipping excursions and scale only after the basic comparison passes.

**Advance** when a reproducible recovery benefit meets the predeclared functional criteria with acceptable toxicity and workable handling. **Revise** when benefit is limited to a surrogate assay, one line, or an uncontrolled thermal condition. **Reject or deprioritize** when the result fails replication, impairs function, depends on incompatible doses, or cannot be chemically reproduced. All three decisions become data.

## Share results and operate efficiently

Keep code, curated metadata, brief evidence summaries and hypothesis decisions in the private repository. Raw publisher XML/HTML stays outside Git pending source-specific rights review. Use hashes and retrieval manifests for provenance; credentials stay in Keychain/environment variables. A future public release should contain eligible data, schema, methods, code and an explicit license inventory. Do not blanket-license third-party content under the code license.

Maintain a living evidence report with a versioned dataset and a separate unscreened backlog. Share a concise decision brief after each experimental batch, including null results and next experiments. Manuscripts, preprints or public datasets become separate publication actions after scientific review and appropriate release authorization.

Use lower-cost research assistants for metadata acquisition, identity lookups, screening suggestions and engineering chores. Require primary-source citations and machine-readable outputs. Reserve root/expert review for quantitative extraction, causal interpretation, novelty and study design. This pilot required substantive corrections to assistant extractions; schema success and self-reported review are insufficient quality gates. Batch tasks by source family, cache downloads and cap paid discovery queries. Do not pay for data until a documented gap justifies it.

Next decision inputs are the target cell product, laboratory partner, success criteria and experiment budget. They are not prerequisites for the completed computational pilot, but they are necessary to make its experimental recommendations operational.
