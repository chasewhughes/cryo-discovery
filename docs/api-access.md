# API and data-source access

Status checked 2026-09-05. No additional credential is required to continue the public-data pilot.

| Resource | Purpose | Access status |
|---|---|---|
| Europe PMC | Literature search, DOI/PMID/PMCID, abstracts, available XML | Used for pilot and discovery; intermittent HTTP 503 failures recorded |
| PubMed / NCBI E-utilities | Biomedical metadata, GEO/SRA discovery | Supplied key stored in Keychain and verified |
| OpenAlex | Broader scholarly coverage and citation graph | Supplied key stored in Keychain and verified; allowance endpoint checked |
| Crossref | Canonical DOI metadata, version/correction links where deposited | Public endpoint verified; used as metadata fallback |
| Unpaywall | Locate permitted open-access versions | Public lookup verified using project email |
| PubChem | Compound identities and properties | Used successfully for nine reference compounds |
| ChEMBL / BindingDB | Target activity and affinity evidence | Public endpoints verified; large-scale activity acquisition remains future work |
| Cellosaurus | Cell-line identities | Public endpoint verified |
| UniProt / Reactome | Target and pathway context | Public endpoints verified |
| RCSB PDB | Experimental structural context | Public endpoint verified; optional for later target-specific work |
| GEO / SRA / BioStudies | Linked expression and other assay datasets | Public discovery available; study accessions and sample maps must be resolved before analysis |
| Zenodo / Figshare / Dryad | Supplements and deposited datasets | Public access options documented; dataset-specific availability varies |
| Exa | Additional literature and company/patent leads | Supplied key stored in Keychain; two bounded searches used |
| AgentMail | Project access-registration inbox | Dedicated inbox created for source-access registrations |
| Brave through Chrome MCP | Access setup and interactive source inspection | Connection verified during setup |
| Google Scholar repository supplied by user | Author-profile citation parser | Assessed; not installed because it is not a general literature search API |
| LINCS / CLUE | Optional perturbational expression signatures | Anonymous API returned 401; a user key/access entitlement would be needed for that route |
| Publisher/institutional content | Full text and supplements not obtainable through public routes | Institutional entitlement or a permitted copy may be needed; current seven abstract-only records remain provisional |
| Proprietary protocols / laboratory results | Cell-specific growth/storage conditions and prospective validation | Not supplied; requires a data owner or laboratory partner |

Detailed endpoint checks and caveats: [literature sources](public-literature-access.md),
[chemical sources](chemical-data-access.md), [credential setup](access-setup.md).
Endpoint availability is not confirmation of complete cryopreservation coverage.
