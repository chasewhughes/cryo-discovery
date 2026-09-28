# Public literature access for the cryopreservation corpus

Checked 2026-09-05 (America/New_York) with direct HTTPS requests. No account, API key, or credentials were used.

## Recommended metadata path

Use Europe PMC for DOI/PMID/PMCID joins and open-access flags:

`https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:<doi>&format=json`

The sample request resolved all six seed DOIs. It returned PMIDs for all six; five had PMCIDs and `isOpenAccess=Y`. The 2024 Stem Cell Research paper (`10.1016/j.scr.2024.103583`) had no PMCID and `isOpenAccess=N`. Search syntax and result fields are documented at `https://europepmc.org/RestfulWebService`.

PubMed E-utilities are the stable NCBI fallback for PubMed records and IDs:

`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=<doi>[doi]&retmode=json`

`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=<pmid>&retmode=json`

The DOI search for `10.1038/srep26403[doi]` returned PMID 27216585 (HTTP 200). E-utilities are public without authentication; NCBI requests an API key for higher sustained throughput and asks clients to rate-limit requests. Details: `https://www.ncbi.nlm.nih.gov/books/NBK25501/`.

Crossref is useful for DOI-first bibliographic metadata (title, authors, venue, dates, publisher):

`https://api.crossref.org/works/<url-encoded-doi>`

All six seed DOI requests returned HTTP 200 and complete `message` records. No key is required. Identify the client with a `mailto` query/header for good citizenship and cache results; Crossref metadata can be incomplete, delayed, or inconsistent across publishers. Docs: `https://api.crossref.org/swagger-ui/index.html`.

## Full text and data access

For PMC articles, use the current [PMC Article Datasets documentation](https://pmc.ncbi.nlm.nih.gov/tools/textmining/). The page was retrieved and inspected on 2026-09-05: its August 26, 2026 notice confirms that legacy article dataset files on FTP and Cloud were removed during the week of August 24. Use the current Cloud Service, OAI-PMH, E-utilities, or BioC routes as appropriate, rather than assuming legacy FTP workflows still operate. File formats and license eligibility differ by route.

The formerly common OA endpoint `https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=PMC4877635` returned HTTP 404 on this check. A tooling documentation page returning HTTP 200 is not a successful content retrieval test. A DOI being indexed in PubMed does not imply downloadable PMC XML or permission to redistribute the full text.

For transcriptomic or other assay datasets, query NCBI GEO, SRA, and EMBL-EBI BioStudies:

* GEO landing/query: `https://www.ncbi.nlm.nih.gov/geo/` (the lightweight `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?db=GEO` check returned HTTP 200). GEO is series/sample/platform metadata and processed expression data; it does not guarantee raw reads.
* SRA: `https://www.ncbi.nlm.nih.gov/sra/` (HTTP 200). For programmatic searches use NCBI E-utilities with `db=sra`, for example `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=sra&term=cryopreservation&retmode=json`. SRA records can point to controlled-access or external data and may have large download footprints.
* BioStudies REST: `https://www.ebi.ac.uk/biostudies/api/v1/studies/<accession>`; the sample `https://www.ebi.ac.uk/biostudies/api/v1/studies/S-EPMC4877635` returned HTTP 200. BioStudies is a broad submission layer; accession and file availability vary by study.

For research data repositories, use their public APIs:

* Zenodo search: `https://zenodo.org/api/records/?q=cryopreservation&size=1` (HTTP 200). No key is needed for public records; rate limits and record/file permissions apply. Docs: `https://developers.zenodo.org/`.
* Dryad: `https://datadryad.org/` (HTTP 200). Public metadata and downloads may be accessed without an account; API/search behavior and download rights vary by item. Docs: `https://datadryad.org/api`.
* Figshare: `https://api.figshare.com/v2/articles?page_size=1` (HTTP 200). Public article metadata is unauthenticated; use the API search endpoints for discovery. Docs: `https://docs.figshare.com/`.

None of these dataset APIs should be assumed to contain a record for a given DOI. First extract accession links from the article metadata/full text, then fetch the accession. Prefer metadata-only discovery, cache responses, and defer large files until an experiment-specific inclusion rule is defined.

## Practical retrieval order

1. Europe PMC DOI search; retain PMID, PMCID, DOI, title, authors, year, journal, and OA flag.
2. Crossref DOI lookup to fill bibliographic gaps and preserve the canonical DOI URL.
3. PubMed E-utilities for stable PubMed IDs and richer summaries when needed.
4. If PMCID exists, follow current PMC Article Datasets routes and eligibility rules; otherwise follow publisher links and rights information.
5. Search GEO/SRA/BioStudies and Zenodo/Dryad/Figshare only using accessions or links found in the article.
