#!/usr/bin/env python3
"""Collect public PubChem identifiers/properties for reference compounds."""
import argparse, datetime, json, time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

COMPOUNDS=["DMSO","glycerol","ethylene glycol","trehalose","L-proline","Y-27632","emricasan","trans-ISRIB","Chroman 1"]
PROPS="IUPACName,ConnectivitySMILES,IsomericSMILES,MolecularFormula,MolecularWeight"
def fetch(name):
    url=f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(name)}/property/{PROPS}/JSON"
    req=Request(url,headers={"Accept":"application/json","User-Agent":"cryo-pilot/0.1"})
    for attempt in range(3):
        try:
            with urlopen(req,timeout=20) as r: data=json.load(r)
            props=(data.get("PropertyTable",{}).get("Properties") or [])
            if not props: return {"query":name,"status":"failure","error":"no properties returned"}
            p=props[0]; return {"query":name,"status":"ok","cid":p.get("CID"),"properties":{k:p.get(k) for k in PROPS.split(",")+["SMILES"] if p.get(k) is not None},"source_url":url}
        except Exception as e:
            if attempt==2: return {"query":name,"status":"failure","error":type(e).__name__}
            time.sleep(1+attempt)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output",default="data/reference-compounds.json"); a=ap.parse_args(); root=Path(__file__).resolve().parents[1]; out=Path(a.output); out=out if out.is_absolute() else root/out; out.parent.mkdir(parents=True,exist_ok=True)
    result={"retrieved_at":datetime.date.today().isoformat(),"endpoint":"PubChem PUG REST","property_query":PROPS,"compounds":[fetch(x) for x in COMPOUNDS],"note":"Reference identifiers/properties only; no research efficacy is inferred."}; out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n"); print(json.dumps({"ok":sum(x["status"]=="ok" for x in result["compounds"]),"failures":sum(x["status"]!="ok" for x in result["compounds"]),"output":str(out)})); return 0
if __name__=="__main__": raise SystemExit(main())
