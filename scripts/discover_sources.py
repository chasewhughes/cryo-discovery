#!/usr/bin/env python3
"""Discover cryopreservation records and optionally fetch Europe PMC XML.

Network use is opt-in. Credentials are read from the environment or macOS
Keychain and are never printed or written to output.
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

def secret(name, service, account=None):
    if account is None:
        account = os.environ.get("CRYO_CONTACT_EMAIL", "your-contact@example.com")
    value = os.environ.get(name)
    if value: return value
    if sys.platform == "darwin":
        try:
            return subprocess.check_output(["security", "find-generic-password", "-s", service, "-a", account, "-w"], stderr=subprocess.DEVNULL, text=True).strip()
        except (subprocess.CalledProcessError, OSError): pass
    return None

def get_json(url, headers=None):
    req = Request(url, headers=headers or {"Accept": "application/json", "User-Agent": "cryo-pilot/0.1"})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as r: return json.load(r)
        except Exception:
            if attempt == 2: raise
            time.sleep(1 + attempt)

def europe_pmc(query, limit):
    params = urlencode({"query": query, "format": "json", "pageSize": min(limit, 100), "resultType": "core"})
    data = get_json("https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + params)
    out = []
    for x in data.get("resultList", {}).get("result", []):
        out.append({k: x.get(k) for k in ("doi", "title", "pubYear", "pmid", "pmcid", "journalTitle") if x.get(k) is not None} | {"source": "Europe PMC"})
    return out

def exa(query, limit):
    key = secret("EXA_API_KEY", "cryo.exa.api-key")
    if not key: return [], "missing EXA_API_KEY/keychain item"
    body = json.dumps({"query": query, "numResults": min(limit, 5), "category": "research paper"}).encode()
    try:
        req = Request("https://api.exa.ai/search", data=body, headers={"Content-Type":"application/json", "x-api-key":key, "User-Agent":"cryo-pilot/0.1"})
        with urlopen(req, timeout=30) as r: data = json.load(r)
        return ([{"title": x.get("title"), "url": x.get("url"), "source": "Exa"} for x in data.get("results", []) if x.get("title") and x.get("url")], None)
    except Exception as e: return [], type(e).__name__

def fetch_pmc(pmcid, outdir):
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/" + pmcid + "/fullTextXML"
    req = Request(url, headers={"Accept":"application/xml", "User-Agent":"cryo-pilot/0.1"})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as r: content = r.read()
            break
        except Exception:
            if attempt == 2: raise
            time.sleep(1 + attempt)
    outdir.mkdir(parents=True, exist_ok=True); path = outdir / (pmcid + ".xml"); path.write_bytes(content); return str(path.relative_to(ROOT))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("query"); ap.add_argument("--limit", type=int, default=20); ap.add_argument("--exa", action="store_true"); ap.add_argument("--fetch-pmc", action="store_true"); ap.add_argument("--out", default="data/discovery/sources.json")
    a = ap.parse_args(); rows = europe_pmc(a.query, a.limit); exa_rows, exa_error = exa(a.query, a.limit) if a.exa else ([], None)
    if a.fetch_pmc:
        for row in rows:
            if row.get("pmcid"):
                try: row["raw_source_path"] = fetch_pmc(row["pmcid"], ROOT / "data/raw")
                except Exception as e: row["fetch_error"] = type(e).__name__
    result = {"query": a.query, "retrieved_at": __import__("datetime").date.today().isoformat(), "europe_pmc_hit_count": len(rows), "europe_pmc_truncated": len(rows) >= min(a.limit, 100), "europe_pmc": rows, "exa_hit_count": len(exa_rows), "exa_truncated": len(exa_rows) >= min(a.limit, 5), "exa": exa_rows, "license_caveat": "Downloaded XML is retained only for publicly accessible sources; license and redistribution limits must be checked per source."}
    if exa_error: result["exa_status"] = exa_error
    path = Path(a.out); path = path if path.is_absolute() else ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"europe_pmc": len(rows), "exa": len(exa_rows), "output": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)}))
if __name__ == "__main__": main()
