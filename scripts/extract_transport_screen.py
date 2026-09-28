#!/usr/bin/env python3
"""Extract the published permeability screen tables from PMC11731021 XML."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
import xml.etree.ElementTree as ET

NUM = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*[±+/-]\s*([0-9]+(?:\.[0-9]+)?)")

def text(e): return " ".join(" ".join(e.itertext()).split())
def sha256(p):
 h=hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()
def cells(tr):
    out=[]
    for x in tr.findall('./td'):
        out.extend([text(x)] * int(x.get('colspan', '1')))
    return out
def parse_value(s):
 m=NUM.match(s)
 return {"mean":float(m.group(1)),"uncertainty":float(m.group(2)),"uncertainty_type":"not_explicitly_specified","raw":s} if m else None

def parse_table1(root):
 tw=next(x for x in root.iter('table-wrap') if x.findtext('label')=='Table 1')
 rows=[]
 for tr in tw.iter('tr'):
  c=cells(tr)
  if len(c)!=5 or c[0] in ('Solute',''): continue
  row={"solute":c[0]}
  for temp, p, lp in [('4_C',c[1],c[2]),('25_C',c[3],c[4])]:
   status='measured'
   if p.strip().lower()=='fast' or lp.strip().lower()=='fast': status='fast'
   elif p.strip().lower()=='toxic' or lp.strip().lower()=='toxic': status='toxic'
   row[temp]={"status":status}
   if status=='measured':
    pv, lv = parse_value(p), parse_value(lp)
    if pv is None or lv is None:
     raise ValueError(f"Unparsed measured Table 1 cell for {row['solute']} at {temp}")
    row[temp].update({"P_CPA_x10^-3_s^-1":pv,"L_p_x10^-8_Pa^-1_s^-1":lv})
  rows.append(row)
 return rows

def parse_table2(root):
 tw=next(x for x in root.iter('table-wrap') if x.findtext('label')=='Table 2')
 rows=[]
 for tr in tw.iter('tr'):
  c=cells(tr)
  if len(c)==3 and c[0] not in ('Solute',''):
   try:
    rows.append({"solute":c[0],"E_Lp_kJ_mol":float(c[1]),"E_PCPA_kJ_mol":(float(c[2]) if c[2] else None)})
   except ValueError: pass
 return rows

def extract(xml_path):
 root=ET.parse(xml_path).getroot()
 article=root.find('front/article-meta')
 title=text(article.find('title-group/article-title'))
 doi=next((x.text for x in article.findall('.//article-id') if x.get('pub-id-type')=='doi'),None)
 rows=parse_table1(root); activation=parse_table2(root)
 toxic4=sum(x['4_C']['status']=='toxic' for x in rows); toxic25=sum(x['25_C']['status']=='toxic' for x in rows)
 return {
  "source":{"pmcid":"PMC11731021","doi":doi,"title":title,"xml_sha256":sha256(xml_path),"xml_path":str(xml_path)},
  "study_context":{"cell":"bovine pulmonary artery endothelial cells (BPAEC)","temperatures_C":[4,25],"screened_test_chemicals":27,"control":"sucrose non-permeant control","permeability_units":{"P_CPA":"reported table value ×10^-3 s^-1","L_p":"reported table value ×10^-8 Pa^-1 s^-1"},"permeability_replicates":"minimum 13 at 4 C and minimum 16 at 25 C across at least 3 plates","toxicity_exposure":"approximately 25 min at 4 C (range 13–34 min), approximately 20 min at 25 C (range 8–34 min); approximately 1 M at 4 C and approximately 2 M at 25 C","toxicity_threshold":"80% viability","bath_total_osmolality_mOsm_kg":{"4_C":"1000 ± 100","25_C":"2000 ± 100 except sucrose 1000 ± 100"},"table_uncertainty":"Table 1 reports mean ± value with statistical-letter annotations; the XML does not explicitly identify the uncertainty as SD or SEM, so it is retained as unspecified."},
  "table1_permeability":rows,"table2_activation_energy":activation,
  "toxicity_summary":{"numeric_per_compound_data_available":False,"status_counts":{"4_C":{"toxic":toxic4,"measured":sum(x['4_C']['status']=='measured' for x in rows),"fast":sum(x['4_C']['status']=='fast' for x in rows)},"25_C":{"toxic":toxic25,"measured":sum(x['25_C']['status']=='measured' for x in rows),"fast":sum(x['25_C']['status']=='fast' for x in rows)}} ,"published_text":"Figure 6 reports viability graphically; the article states four toxic chemicals at 4 C and six at 25 C, with an 80% threshold. Exact per-compound numeric viability values were not present in the XML tables and are not reconstructed."},
  "notes":["Sucrose is a non-permeating control; its small fitted apparent P_CPA value is a model/control estimate, not evidence of CPA membrane transport."],
  "limitations":["Fast status means permeation exceeded the measurement capability; it is not a numeric lower bound.","Toxic status means permeability was not measured, not zero permeability.","Permeability is an indirect calcein-fluorescence estimate in BPAEC, not a general compound constant.","Activation energies are reported only for compounds with measured values in Table 2; no model fitting is performed by this extractor."]}

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--xml',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args(); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(extract(a.xml),indent=2)+'\n')
if __name__=='__main__': main()
