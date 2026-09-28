# Cryo evidence pilot protocol

Date: 2026-09-05. Version: 0.1.

## Research question and scope

Which chemical, formulation, and handling interventions improve post-thaw recovery and retained cell function, and what evidence distinguishes physical ice control from biological stress protection?

Primary application: human induced pluripotent stem cells (iPSCs). Include human pluripotent cells and differentiated derivatives as close evidence. Use other mammalian cells, blood cells, and cell-free physical assays as explicitly labeled transfer evidence. Animal semen optimization is methods-transfer evidence, not a result assumed to generalize to iPSCs. Do not pool species, cell types, viability assays, or follow-up times.

Pilot target: 24 distinct primary studies (not a systematic or exhaustive review), with at least 20 if accessible relevant evidence supports inclusion. The completed pilot contains 25 after adding one relevant post-thaw stress-modulation paper discovered during collection. Study-linked preprints and journal versions count once. Exclude reviews from experimental evidence; retain useful reviews only as discovery leads. Date cutoff: 2026-09-05. Retractions and corrections should be checked where metadata supports it; absence of a detected notice is not proof of no notice.

## Inclusion and interpretation

Include an identifiable cryopreservation, cryoprotectant-property, or cytoprotection experiment with a relevant intervention, comparator when available, and measured endpoint. Clearly distinguish full-text extraction from abstract-only screening. Abstract-only evidence is provisional and cannot supply unreported protocol details. Missing conditions remain null or empty; do not infer an experiment's concentration, timing, mechanism, or effect size from a related paper.

Physical ice inhibition, biological pathway effects, and functional recovery are separate evidence axes. Suppression of apoptosis after freezing does not by itself establish direct pathway inhibition; it could follow reduced upstream physical injury. IRI activity does not establish vitrification or replacement of a permeating CPA. Immediate percentage viability is not absolute recovered cell yield. Model accuracy does not establish prospective cell benefit.

## Extraction contract

Write each assigned batch as a JSON array in `data/extractions/<batch>.json`. The following fields are required for each study:

```json
{
  "study_id": "doi:10.example/example",
  "doi": "10.example/example",
  "title": "Exact source title",
  "year": 2024,
  "pmcid": null,
  "source_url": "https://doi.org/10.example/example",
  "source_access": "full_text",
  "raw_source_path": null,
  "retrieved_at": "2026-09-05",
  "evidence_scope": "ipsc_direct",
  "species": ["Homo sapiens"],
  "cell_types": ["human iPSC"],
  "study_design": "Short factual description",
  "interventions": ["compound or formulation"],
  "mechanism_axes": ["physical_ice", "biological_stress"],
  "experiments": [
    {
      "experiment_id": "e1",
      "model": "Exact cell/model context",
      "intervention": "Treatment arm description",
      "comparator": "Comparator or null",
      "formulation": [
        {"compound": "compound name", "concentration": null, "unit": null}
      ],
      "treatment_stage": ["freezing"],
      "cooling": null,
      "warming": null,
      "storage": null,
      "outcome_name": "Named assay/endpoint",
      "outcome_type": "viability",
      "timepoint": null,
      "result": "Source-grounded result without invented numbers",
      "effect_numeric": null,
      "effect_unit": null,
      "sample_size": null,
      "source_locator": "Section, table, figure, or abstract",
      "evidence_excerpt": "Short exact source excerpt supporting the result"
    }
  ],
  "main_finding": "Source-grounded concise summary",
  "limitations": ["Context and reporting limitations"],
  "mechanism_claim": "What was directly measured versus inferred",
  "review_status": "agent_extracted",
  "reviewer": "research assistant batch name"
}
```

Allowed `source_access`: `full_text`, `abstract_only`, `abstract_plus_supplement`. The last category means the main article is available only as an abstract but a linked supplement was inspected; it must not count as complete primary full-text access. Record supplementary paths in `additional_source_paths` and name the supporting source in each experiment locator. Allowed `evidence_scope`: `ipsc_direct`, `pluripotent_related`, `mammalian_transfer`, `physical_assay`, `methods_transfer`. Allowed `mechanism_axes`: `physical_ice`, `biological_stress`, `osmotic_membrane`, `protocol_optimization`. Allowed `outcome_type`: `viability`, `recovery`, `function`, `ice_activity`, `toxicity`, `permeability`, `mechanistic`, `model_performance`.

Use one experiment record per supported intervention/comparator/endpoint/timepoint summary; a record may summarize an explicitly identified dose series rather than pretend to be raw data. Do not equate experiment summaries with independent biological replicates. Keep primary result values in `result`; use `effect_numeric` only for an unambiguous reported or explicitly labeled calculated comparative effect, not an intervention's raw outcome. `sample_size` is text because donors, lines, and technical replicates must not be conflated.

Download publicly accessible source XML/text only through supported services. Store local source files in `data/raw/` (git-ignored) and record relative paths. Record access and license limits; no paywall bypass, CAPTCHA bypass, or assumptions that subscription reading rights permit bulk redistribution. Keep evidence excerpts brief and factual. Never store credentials or credential-bearing request URLs.

## Analysis and quality gates

- Validate required fields, enums, unique DOI identities, source locators, sample-size/timepoint reporting, and valid numeric/unit pairing.
- Preserve missingness rather than filling it with model guesses.
- Root reviews all study summaries and prioritizes verification of numeric claims and high-value hypotheses against original sources. Automated checks are not expert scientific validation. Record review coverage honestly.
- Describe source coverage and screening limits; pilot discovery is purposive and cannot support a PRISMA-style completeness claim.
- Report separate evidence tables by cell context, mechanism, and outcome. No pooled efficacy score or trained predictive model unless sufficient comparable independent observations exist.
- Produce a ranked hypothesis portfolio, falsifiable next experiments, a prospective validation design, and a reproducible report. These are research hypotheses, not validated new CPAs.
- Stop at a concrete experimental handoff: biological validation requires a lab partner, chosen assays, and budget. Do not fabricate wet-lab outcomes.
