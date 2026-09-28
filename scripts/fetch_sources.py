#!/usr/bin/env python3
"""Fetch DOI metadata and available Europe PMC XML without destructive writes."""
import argparse, datetime, json, os, tempfile, time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
def get(url,accept):
    req=Request(url,headers={"Accept":accept,"User-Agent":"cryo-pilot/0.1"})
    for n in range(3):
        try:
            with urlopen(req,timeout=30) as r:return r.read()
        except Exception:
            if n==2:raise
            time.sleep(1+n)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",default="data/extractions"); ap.add_argument("--raw",default="data/raw"); a=ap.parse_args(); idir=Path(a.input); idir=idir if idir.is_absolute() else ROOT/idir; raw=Path(a.raw); raw=raw if raw.is_absolute() else ROOT/raw; rows=[]
    for p in sorted(idir.glob("*.json")):
        v=json.loads(p.read_text()); rows+=v if isinstance(v,list) else [v]
    raw.mkdir(parents=True,exist_ok=True); records=[]
    for s in rows:
        doi=s.get("doi"); rec={"doi":doi,"metadata_status":"failure","fulltext_status":"not_requested"}
        try:
            u="https://www.ebi.ac.uk/europepmc/webservices/rest/search?query="+quote("DOI:"+doi)+"&format=json&resultType=core&pageSize=1"; data=json.loads(get(u,"application/json")); result=(data.get("resultList",{}).get("result") or [None])[0]
            if not result: rec["error"]="metadata_not_found"
            else:
                rec.update({"metadata_status":"ok","metadata":result,"pmcid":result.get("pmcid"),"title":result.get("title"),"year":result.get("pubYear"),"source_url":u})
                source_path=ROOT/s["raw_source_path"] if s.get("raw_source_path") else None
                if s.get("source_access")=="abstract_only": rec["fulltext_status"]="abstract_only_scope"
                elif source_path and source_path.exists(): rec["fulltext_status"]="existing_extraction_path"
                elif source_path and source_path.suffix==".html": rec["fulltext_status"]="html_requires_separate_retrieval"
                elif result.get("pmcid"):
                    dest=source_path if source_path and source_path.suffix==".xml" else raw/(result["pmcid"]+".xml")
                    if dest.exists(): rec["fulltext_status"]="existing_raw_file"
                    else:
                        content=get("https://www.ebi.ac.uk/europepmc/webservices/rest/"+result["pmcid"]+"/fullTextXML","application/xml"); ET.fromstring(content); fd,tmp=tempfile.mkstemp(prefix=".cryo-",dir=raw); os.close(fd); Path(tmp).write_bytes(content); os.replace(tmp,dest); rec["fulltext_status"]="downloaded"
                    rec["raw_source_path"]=str(dest.relative_to(ROOT))
                else: rec["fulltext_status"]="not_available"
        except Exception as e: rec["error"]=type(e).__name__; rec["fulltext_status"]="failure"
        records.append(rec)
    out=raw/"fetched-metadata.json"; out.write_text(json.dumps({"retrieved_at":datetime.date.today().isoformat(),"records":records},indent=2)+"\n"); print(json.dumps({"records":len(records),"metadata_ok":sum(x["metadata_status"]=="ok" for x in records),"output":str(out)}))
if __name__=="__main__": main()
