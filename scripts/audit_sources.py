#!/usr/bin/env python3
"""Audit extraction provenance and excerpt support; emits flags, never verdicts."""
import argparse, hashlib, html, json, re
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
def norm(v): return re.sub(r"\s+"," ",html.unescape(v or "")).strip()
class _Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self,data): self.parts.append(data)
def strip_markup(v):
    p=_Text(); p.feed(v or ""); return " ".join(p.parts)
def key(v): return re.sub(r"[^a-z0-9]","",norm(strip_markup(v)).lower())
def load_records(path):
    if not path.exists(): return []
    v=json.loads(path.read_text())
    if isinstance(v,list): return v
    if isinstance(v,dict) and isinstance(v.get("resultList"),dict): return v["resultList"].get("result",[])
    if isinstance(v,dict) and isinstance(v.get("records"),list): return v["records"]
    if isinstance(v,dict) and isinstance(v.get("results"),list): return v["results"]
    return [x for x in v.values() if isinstance(x,dict)]
def raw_text(path):
    if path.suffix.lower() == ".txt":
        try: return norm(path.read_text(errors="replace"))
        except OSError: return ""
    try: return norm(" ".join(ET.parse(path).getroot().itertext()))
    except Exception:
        if path.suffix.lower() in (".html",".htm"):
            try: p=_Text(); p.feed(path.read_text(errors="replace")); return norm(" ".join(p.parts))
            except Exception: pass
        return ""
def index_metadata(paths):
    metadata={}
    for path in paths:
        for record in load_records(path):
            if not isinstance(record,dict): continue
            if record.get("metadata_status") == "failure": continue
            m=record.get("metadata",record)
            if not isinstance(m,dict): continue
            doi=(m.get("doi") or m.get("DOI") or "").lower().strip()
            if doi and (m.get("title") or m.get("abstractText")):
                metadata[doi]={**metadata.get(doi,{}),**m}
    return metadata
def evidence_text(study, metadata, root=ROOT):
    paths = ([study['raw_source_path']] if study.get('raw_source_path') else []) + study.get('additional_source_paths', [])
    parts = [raw_text(root / path) for path in paths if (root / path).exists()]
    if study.get('source_access') in ('abstract_only', 'abstract_plus_supplement'):
        parts.append(norm(strip_markup(' '.join(str(metadata.get(k, '')) for k in ('abstractText', 'abstract', 'title')))))
    return norm(' '.join(parts))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",default="data/extractions"); ap.add_argument("--raw",default="data/raw"); ap.add_argument("--metadata",default="data/raw/pilot-metadata.json"); ap.add_argument("--report",default="reports/source-audit.json"); ap.add_argument("--manifest",default="data/source-manifest.json"); a=ap.parse_args()
    idir=Path(a.input); idir=idir if idir.is_absolute() else ROOT/idir; rawdir=Path(a.raw); rawdir=rawdir if rawdir.is_absolute() else ROOT/rawdir; md=Path(a.metadata); md=md if md.is_absolute() else ROOT/md
    studies=[]
    for p in sorted(idir.glob("*.json")):
        try:
            v=json.loads(p.read_text()); studies += v if isinstance(v,list) else [v]
        except Exception: continue
    metadata={}
    metadata_files=[md]
    if md.name=="pilot-metadata.json": metadata_files += [md.parent/"fetched-metadata.json",md.parent/"methods-metadata.json",md.parent/"revitalice-metadata.json",md.parent/"phase2/metadata.json",md.parent/"phase3/metadata.json"]
    metadata=index_metadata(metadata_files)
    files=[]; texts={}
    for p in sorted(rawdir.rglob("*")):
        if not p.is_file() or p.name.startswith("._"): continue
        if p.suffix.lower() not in (".xml", ".html", ".htm", ".txt", ".json", ".r"): continue
        b=p.read_bytes(); rel=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p); files.append({"path":rel,"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()}); texts[p.name]=raw_text(p)
    entries=[]; flags=[]
    for i,s in enumerate(studies):
        if not isinstance(s,dict): continue
        doi=(s.get("doi") or "").lower().strip(); m=metadata.get(doi,{}); title=s.get("title") or ""; year=s.get("year")
        ef=[]; raw=s.get("raw_source_path"); rawpath=ROOT/raw if raw else None
        if rawpath and not rawpath.exists(): ef.append("raw_path_missing")
        if not raw: ef.append("raw_path_missing")
        if any(not (ROOT / p).exists() for p in s.get('additional_source_paths', [])): ef.append('additional_source_missing')
        if m:
            if year is not None and str(year)!=str(m.get("year",m.get("pubYear",year))): ef.append("metadata_year_mismatch")
            mt=m.get("title");
            if mt and key(title)!=key(mt): ef.append("metadata_title_mismatch")
        elif doi: ef.append("metadata_unavailable")
        if ef: flags.extend({"study_id":s.get("study_id"),"flag":x} for x in ef)
        experiments=s.get("experiments",[]) if isinstance(s.get("experiments",[]),list) else []
        for e in experiments:
            if not isinstance(e,dict):
                flags.append({"study_id":s.get("study_id"),"flag":"experiment_not_object"}); continue
            excerpt=e.get("evidence_excerpt") or ""; ef2=[]
            if "..." in excerpt or "…" in excerpt: ef2.append("excerpt_ellipsis_unsupported")
            else:
                hay=evidence_text(s,m)
                if excerpt and norm(excerpt) not in hay: ef2.append("excerpt_not_found")
            entries.append({"study_id":s.get("study_id"),"experiment_id":e.get("experiment_id"),"doi":doi,"raw_source_path":raw,"flags":ef+ef2})
            flags.extend({"study_id":s.get("study_id"),"experiment_id":e.get("experiment_id"),"flag":x} for x in ef2)
    report={"study_count":len(studies),"experiment_count":len(entries),"flags":flags,"entries":entries,"note":"Flags indicate provenance or text-support conditions; they are not scientific validity labels."}
    rp=Path(a.report); rp=rp if rp.is_absolute() else ROOT/rp; rp.parent.mkdir(parents=True,exist_ok=True); rp.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    mp=Path(a.manifest); mp=mp if mp.is_absolute() else ROOT/mp; mp.parent.mkdir(parents=True,exist_ok=True); mp.write_text(json.dumps({"files":files,"license":"Source-specific license status must be checked; raw files are publicly retrieved material and may have redistribution limits."},indent=2)+"\n")
    print(json.dumps({"studies":len(studies),"experiments":len(entries),"flags":len(flags)})); return 0
if __name__=="__main__": raise SystemExit(main())
