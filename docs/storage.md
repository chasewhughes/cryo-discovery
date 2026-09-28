# Local research storage

Cryo's downloaded sources, bulk downloads and research temporary files live at
`<local-storage>/cryo-adata/` (a local path outside the repo, on external storage
the operator provisioned). No external drive is required for the repository itself. Code, curated datasets and reports
remain versioned in Git. Personal Downloads and other projects are unchanged.

| Repository path | Local target | Purpose |
| --- | --- | --- |
| `data/raw` | `cryo-adata/raw` | Source articles, metadata and original research data |
| `data/downloads` | `cryo-adata/downloads` | Large archives and new bulk downloads |
| `data/tmp` | `cryo-adata/tmp` | Download fragments, extraction staging and temporary analysis files |

These three repository paths are relative symbolic links, excluded from Git.
`cryo-adata/` is also excluded: local repository storage does not mean original
downloads are uploaded to GitHub. `.cryo-storage.json` records the local layout
but is not required by the command wrapper.
Existing scripts that write to `data/raw` follow its link automatically.

Run research downloads and archive extraction with this wrapper to verify the
local paths and direct the command's temporary files into the project. Its old
name is retained so existing commands continue to work:

```sh
python3 scripts/with_external_storage.py
python3 scripts/with_external_storage.py -- python3 scripts/fetch_sources.py
```

For new download commands, explicitly select `data/downloads/<filename>` as
the output, and select `data/raw/<dataset>` for extracted research data. The
wrapper exposes `CRYO_RAW_DIR` and `CRYO_DOWNLOAD_DIR` and sets `TMPDIR`, `TEMP`
and `TMP` for its child process. It does not override an application's explicit
cache or output location; configure those paths when applicable. Browser-based
research downloads should select `cryo-adata/downloads` in the save dialog.
The browser's global download preference is unchanged.

The wrapper checks local paths only; it does not call `diskutil` or access
`/Volumes/ADATA HV300`. New downloads now consume internal disk space. Continue
using selective acquisition where possible. On a fresh clone, restore the
original data into `cryo-adata/` and create the relative `data/` links before
running source-dependent analyses.

The transferred copy was checked against the initial 45-file migration manifest
and all 15 subsequently selected archive files: every SHA-256 hash matched.
The initial inventory is preserved in `cryo-adata/migration-manifest.json`.
