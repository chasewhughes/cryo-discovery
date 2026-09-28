# Pilot tooling

The pilot uses the standard-library scripts `scripts/discover_sources.py` and
`scripts/validate_pilot.py`, so the repository does not need a package install.

`discover_sources.py QUERY` searches Europe PMC and writes sanitized metadata to
`data/discovery/sources.json`. Add `--fetch-pmc` to retrieve only publicly
available Europe PMC full-text XML into `data/raw/`. Add `--exa` for an
optional Exa research-paper search (the CLI caps results at five). It reads
`EXA_API_KEY`, or the macOS Keychain item service `cryo.exa.api-key` and an
account label matching the `CRYO_CONTACT_EMAIL` environment variable (placeholder
default `your-contact@example.com`); secrets are sent only in the request
header and never printed or persisted. NCBI/OpenAlex keychain names are reserved
for future clients.

Exa's official documentation specifies `POST https://api.exa.ai/search`, the
`x-api-key` header, `query`, `numResults`, and research-paper `category`:
[Search API reference](https://exa.ai/docs/reference/search-api-guide-for-coding-agents).
Two bounded searches were performed: one research-paper verification query and
one root-led Evergreen/Everlast discovery query. No automatic top-up or purchase
is supported.

`validate_pilot.py` reads JSON arrays from `data/extractions/*.json`, checks the
required fields, allowed enums, duplicate DOI identities, source locators, and
numeric effect/unit pairing, then writes `data/pilot-studies.json`,
`reports/coverage.json`, and `reports/evidence-table.md`. Missing fields remain
missing. It reports counts by evidence scope, mechanism axis, outcome, and
required-field missingness; it does not calculate pooled effects or train a
model. A nonzero exit status indicates validation errors.

The requested `fredrike/googlescholar-api` assessment found a small MIT-licensed
PHP project whose README says it parses a Google Scholar author profile and
returns first-page publications/citation indices, with a required Scholar user
ID. Its files are `googlescholar.php` and `simple_html_dom.php`; it is not a
general scholarly search API and was not installed. Europe PMC remains the
reproducible primary discovery source, with Exa as an optional discovery lead.
[Repository README](https://github.com/fredrike/googlescholar-api).

## Additional tools and checks

- `collect_pubchem.py`: public identity/property lookup for nine reference compounds.
- `fetch_sources.py`: bounded DOI metadata retrieval into a separate raw file;
  preserves original metadata and validates XML before writing. Existing sources
  are reused, abstract-only records remain in that scope, and missing HTML needs
  separate retrieval. A run during service disruption retrieved four of 25
  metadata records; the earlier 24-record archive and Crossref fallback were retained.
- `audit_sources.py`: source-file hashes, bibliographic comparison and normalized
  excerpt matching against XML, HTML or abstract metadata. Failed metadata refreshes
  cannot replace successful archived records. Zero flags is a provenance check,
  not a scientific validity verdict. Raw files are required to repeat the check.
- `build_backlog.py`: merges the two successful stored search outputs by DOI or
  PMID, records matched queries and derives pilot membership from the extraction files.
  Both searches reached their 100-result cap; two other queries returned HTTP 503.
  The backlog is intentionally incomplete and unscreened. Stored search hit counts
  are returned counts, not the database's total number of matching records.

Run `python3 -m unittest discover -s tests` for offline validation/provenance
regressions. Use `python3 scripts/validate_pilot.py` to regenerate the combined
dataset and evidence table. Network calls are explicit CLI actions; no recurring
job or unbounded crawler was installed.
