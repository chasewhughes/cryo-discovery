"""Generate unverified accession candidates; never overwrite curated dataset leads.

Run with with_external_storage.py to use the configured local research paths.
"""
import json,re
from pathlib import Path
from audit_sources import raw_text
root=Path(__file__).resolve().parents[1]
if not (root/'data/raw').is_dir():
    raise SystemExit('Original source storage is unavailable; candidate scan not written')
meta={'resultList':{'result':json.loads((root/'data/pilot-studies.json').read_text())}}
rows=[]
for x in meta['resultList']['result']:
    doi=x.get('doi'); path=root/x['raw_source_path'] if x.get('raw_source_path') and x.get('source_access')=='full_text' else None
    if doi == '10.1016/j.scr.2024.103583':
        rows.extend([
            {'studyDOI':doi,'accession/url':'https://doi.org/10.5281/zenodo.14038512','evidence_excerpt':None,'sourcepath/locator':'data/phase2/archive-index.json','relationship':'own_data','verified_availability_status':'selected_original_files_downloaded_and_verified','dataset_type':'study archive'},
            {'studyDOI':doi,'accession/url':'https://gitlab.com/uniluxembourg/lcsb/developmental-and-cellular-biology/mommaerts_2022','evidence_excerpt':'Study-linked GitLab repository contains README and process_RNAseq.R.','sourcepath/locator':'root-supplied study data lead','relationship':'own_data','verified_availability_status':'public_repository','dataset_type':'RNA-seq processing code'}
        ])
        continue
    if not path:
        rows.append({'studyDOI':doi,'accession/url':None,'evidence_excerpt':None,'sourcepath/locator':None,'relationship':'uncertain','verified_availability_status':'not_reviewed_abstract_only','dataset_type':None})
        continue
    if not path.exists():
        raise SystemExit(f'Missing original source for {doi}; candidate scan not written')
    s=raw_text(path)
    found=[]
    for pat in (r'PRJNA\d+',r'PRJEB\d+',r'GSE\d+',r'E-MTAB-\d+',r'SRP\d+'):
        found += re.findall(pat,s,re.I)
    links=re.findall(r'https?://[^" <]+(?:geo|sra|tripod|zenodo|figshare|dryad)[^" <]*',s,re.I)
    for acc in sorted(set(found+links)):
        pos=s.lower().find(acc.lower()); snippet=s[max(0,pos-180):pos+len(acc)+180].replace('\n',' ')
        own=bool(re.search(r'(deposited|available|accession|repository|data availability)',snippet,re.I))
        rows.append({'studyDOI':doi,'accession/url':acc,'evidence_excerpt':snippet,'sourcepath/locator':str(path.relative_to(root))+':full-text context','relationship':'uncertain','candidate_status':'requires_manual_ownership_check','availability_language_nearby':own,'verified_availability_status':'not_verified_metadata','dataset_type':'sequencing or expression data' if acc.upper().startswith(('PRJNA','PRJEB','GSE','E-MTAB','SRP')) else 'repository link'})
    if not found and not links:
        rows.append({'studyDOI':doi,'accession/url':None,'evidence_excerpt':None,'sourcepath/locator':str(path.relative_to(root))+':limited regex scan','relationship':'uncertain','verified_availability_status':'no_pattern_match_not_evidence_of_no_data','dataset_type':None})
out={'retrieved_at':'2026-09-05','scope':'pilot full texts; abstract-only records marked unknown','records':rows}
(root/'data/phase2/dataset-candidates.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'records':len(rows),'output':'data/phase2/dataset-candidates.json'}))
