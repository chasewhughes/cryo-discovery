#!/usr/bin/env python3
"""Build a DOI/PMID-deduplicated discovery backlog from search outputs."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "data/discovery/physical-search.json",
    ROOT / "data/discovery/ice-search.json",
]
PILOT = {study['doi'].lower().strip() for path in (ROOT/'data/extractions').glob('*.json') for study in json.loads(path.read_text())}

def norm(x):
    return x.lower().strip().removeprefix("https://doi.org/") if x else None

groups = {}
for path in FILES:
    data = json.loads(path.read_text())
    query = data["query"]
    for row in data.get("europe_pmc", []):
        doi = norm(row.get("doi"))
        pmid = str(row.get("pmid")) if row.get("pmid") else None
        key = "doi:" + doi if doi else "pmid:" + pmid if pmid else None
        if not key:
            continue
        item = groups.setdefault(key, {"doi": doi, "pmid": pmid, "title": row.get("title"), "pubYear": row.get("pubYear"), "matched_queries": [], "is_pilot": bool(doi and doi in PILOT), "screening_status": "pilot" if doi and doi in PILOT else "unscreened"})
        if query not in item["matched_queries"]:
            item["matched_queries"].append(query)
        if not item.get("doi") and doi: item["doi"] = doi
        if not item.get("pmid") and pmid: item["pmid"] = pmid

out = {"retrieved_at": "2026-09-05", "source_files": [str(p.relative_to(ROOT)) for p in FILES], "successful_query_count": 2, "failed_query_count": 2, "record_count": len(groups), "records": sorted(groups.values(), key=lambda x: (x.get("doi") or "", x.get("pmid") or ""))}
(ROOT / "data/discovery/backlog.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
print(json.dumps({"record_count": len(groups), "output": "data/discovery/backlog.json"}))
