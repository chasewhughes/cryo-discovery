#!/usr/bin/env python3
"""Strictly validate extraction batches and publish pilot reports on success."""
import argparse, json, math
from collections import Counter
from pathlib import Path

STUDY=["study_id","doi","title","year","pmcid","source_url","source_access","raw_source_path","retrieved_at","evidence_scope","species","cell_types","study_design","interventions","mechanism_axes","experiments","main_finding","limitations","mechanism_claim","review_status","reviewer"]
EXP=["experiment_id","model","intervention","comparator","formulation","treatment_stage","cooling","warming","storage","outcome_name","outcome_type","timepoint","result","effect_numeric","effect_unit","sample_size","source_locator","evidence_excerpt"]
SCOPES={"ipsc_direct","pluripotent_related","mammalian_transfer","physical_assay","methods_transfer"}; ACCESS={"full_text","abstract_only","abstract_plus_supplement"}; AXES={"physical_ice","biological_stress","osmotic_membrane","protocol_optimization"}; OUTCOMES={"viability","recovery","function","ice_activity","toxicity","permeability","mechanistic","model_performance"}
def text(v): return isinstance(v,str) and bool(v.strip())
def finite(v): return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def absent(v): return v is None or v=="" or v==[]

def validate(rows):
    err=[]; dois=set(); sids=set(); eids=set()
    if not isinstance(rows,list) or not rows: return ["input must be a non-empty JSON array"]
    for i,s in enumerate(rows):
        p=f"study[{i}]"
        if not isinstance(s,dict): err.append(f"{p} must be an object"); continue
        for k in STUDY:
            if k not in s: err.append(f"{p} missing {k}")
        sid,doi=s.get("study_id"),s.get("doi")
        if not text(sid): err.append(f"{p} study_id must be non-empty")
        elif sid in sids: err.append(f"{p} duplicate study_id {sid}")
        else: sids.add(sid)
        if not text(doi): err.append(f"{p} doi must be non-empty")
        elif doi.lower() in dois: err.append(f"{p} duplicate doi {doi}")
        else: dois.add(doi.lower())
        if s.get("source_access") not in ACCESS: err.append(f"{p} invalid source_access")
        if s.get("evidence_scope") not in SCOPES: err.append(f"{p} invalid evidence_scope")
        if not isinstance(s.get("mechanism_axes"),list) or not set(s.get("mechanism_axes",[])) <= AXES: err.append(f"{p} invalid mechanism_axes")
        for k in ("title","source_url","retrieved_at","study_design","main_finding","mechanism_claim","reviewer"):
            if not text(s.get(k)): err.append(f"{p} {k} must be non-empty")
        for k in ("species","cell_types","interventions","limitations"):
            if not isinstance(s.get(k),list): err.append(f"{p} {k} must be an array")
        xs=s.get("experiments")
        if not isinstance(xs,list) or not xs: err.append(f"{p} experiments must be a non-empty array"); xs=[]
        for j,e in enumerate(xs):
            q=f"{p}.experiment[{j}]"
            if not isinstance(e,dict): err.append(f"{q} must be an object"); continue
            for k in EXP:
                if k not in e: err.append(f"{q} missing {k}")
            eid=e.get("experiment_id")
            if not text(eid): err.append(f"{q} experiment_id must be non-empty")
            elif eid in eids: err.append(f"{q} duplicate experiment_id {eid}")
            else: eids.add(eid)
            for k in ("model","intervention","outcome_name","result","source_locator","evidence_excerpt"):
                if not text(e.get(k)): err.append(f"{q} {k} must be non-empty")
            if e.get("outcome_type") not in OUTCOMES: err.append(f"{q} invalid outcome_type")
            if not isinstance(e.get("formulation"),list): err.append(f"{q} formulation must be an array")
            else:
                for z,f in enumerate(e["formulation"]):
                    fq=f"{q}.formulation[{z}]"
                    if not isinstance(f,dict) or not text(f.get("compound")): err.append(f"{fq} compound required"); continue
                    if "concentration" not in f or "unit" not in f: err.append(f"{fq} concentration and unit keys required")
                    if f.get("concentration") is not None and not finite(f.get("concentration")): err.append(f"{fq} concentration must be finite numeric or null")
                    if f.get("concentration") is None and f.get("unit") is not None: err.append(f"{fq} null concentration cannot have unit")
                    if f.get("concentration") is not None and not text(f.get("unit")): err.append(f"{fq} numeric concentration needs unit")
            if e.get("treatment_stage") is not None and not isinstance(e.get("treatment_stage"),list): err.append(f"{q} treatment_stage must be an array")
            if e.get("effect_numeric") is not None and not finite(e.get("effect_numeric")): err.append(f"{q} effect_numeric must be finite numeric or null")
            if e.get("effect_numeric") is None and e.get("effect_unit") is not None: err.append(f"{q} null effect cannot have unit")
            if e.get("effect_numeric") is not None and not text(e.get("effect_unit")): err.append(f"{q} numeric effect needs unit")
    return err

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",default="data/extractions"); ap.add_argument("--output",default="data/pilot-studies.json"); ap.add_argument("--reports",default="reports"); a=ap.parse_args(); root=Path(__file__).resolve().parents[1]
    idir=Path(a.input); idir=idir if idir.is_absolute() else root/idir; op=Path(a.output); op=op if op.is_absolute() else root/op; rd=Path(a.reports); rd=rd if rd.is_absolute() else root/rd
    rows=[]; files=[]; errors=[]
    for p in sorted(idir.glob("*.json")):
        try: v=json.loads(p.read_text()); rows.extend(v if isinstance(v,list) else [v]); files.append(str(p.relative_to(root)) if p.is_relative_to(root) else str(p))
        except Exception as e: errors.append(f"{p}: invalid JSON ({type(e).__name__})")
    errors += validate(rows); exps=[e for s in rows if isinstance(s,dict) for e in (s.get("experiments") or []) if isinstance(e,dict)]
    coverage={"study_count":len(rows),"experiment_count":len(exps),"batch_files":files,"validation_errors":errors,"coverage":{"evidence_scope":dict(Counter(s.get("evidence_scope") for s in rows if isinstance(s,dict))),"source_access":dict(Counter(s.get("source_access") for s in rows if isinstance(s,dict))),"review_status":dict(Counter(s.get("review_status") for s in rows if isinstance(s,dict))),"mechanism_axes":dict(Counter(x for s in rows if isinstance(s,dict) for x in (s.get("mechanism_axes") or []))),"outcome_type":dict(Counter(e.get("outcome_type") for e in exps))},"missing_required_fields":{k:sum(1 for s in rows if isinstance(s,dict) and absent(s.get(k))) for k in STUDY},"experiment_missing_fields":{k:sum(1 for e in exps if absent(e.get(k))) for k in EXP}}
    rd.mkdir(parents=True,exist_ok=True); (rd/"coverage.json").write_text(json.dumps(coverage,indent=2,ensure_ascii=False)+"\n")
    if errors: print(json.dumps({"studies":len(rows),"experiments":len(exps),"errors":len(errors)})); return 1
    op.parent.mkdir(parents=True,exist_ok=True); op.write_text(json.dumps(rows,indent=2,ensure_ascii=False)+"\n")
    lines=["# Evidence table","",f"Studies: {len(rows)}","","| Study / DOI | Context | Model | Intervention | Comparator | Outcome | Timepoint | Result |","|---|---|---|---|---|---|---|---|"]
    for s in rows:
        for e in s["experiments"]: lines.append(f"| [{s['title']}]({s['source_url']})<br>{s['doi']} | {s['evidence_scope']} | {e['model']} | {e['intervention']} | {e['comparator'] or ''} | {e['outcome_name']} ({e['outcome_type']}) | {e['timepoint'] or ''} | {e['result']} |")
    (rd/"evidence-table.md").write_text("\n".join(lines)+"\n"); print(json.dumps({"studies":len(rows),"experiments":len(exps),"errors":0})); return 0
if __name__ == "__main__": raise SystemExit(main())
