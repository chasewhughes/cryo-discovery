# Access setup

This pilot uses a small set of free, publicly available literature and
chemical-data APIs. No paid subscriptions or institutional entitlements are
required to reproduce the public-data pilot.

## Accounts needed

| Service | What it's for | Notes |
| --- | --- | --- |
| Email inbox (any provider) | Registering API keys and confirming service signups | A dedicated address is convenient but not required |
| NCBI | PubMed/E-utilities metadata, GEO/SRA discovery | Free API key, higher rate limit than anonymous access |
| OpenAlex | Scholarly coverage and citation graph | Free API key; small daily allowance without one |
| Exa (optional) | Supplementary literature/company leads | Free-tier key; only used for a handful of bounded searches |

Crossref, Unpaywall, Europe PMC, PubChem, ChEMBL/BindingDB, Cellosaurus,
UniProt/Reactome and RCSB PDB are used through public endpoints that need no
account.

## Credential handling

Store API keys as environment variables or in your OS's credential store
(e.g. macOS Keychain, `pass`, a `.env` file excluded from Git). Never commit
credentials to the repository. Scripts in `scripts/` read secrets from the
environment first and fall back to a local credential store lookup where
supported; see `docs/tooling.md` for the exact variable names.

Detailed endpoint checks and coverage caveats are recorded in
[public-literature-access.md](public-literature-access.md) and
[chemical-data-access.md](chemical-data-access.md).
