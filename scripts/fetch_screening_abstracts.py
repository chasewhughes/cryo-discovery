#!/usr/bin/env python3
"""Fetch the fixed phase-2 screening queue in bounded, cached Europe PMC batches."""
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

from fetch_sources import get

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/phase3'


def batch(args):
    index, rows = args
    query = ' OR '.join('DOI:"' + r['doi'] + '"' for r in rows)
    url = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urlencode(
        {'query': query, 'format': 'json', 'resultType': 'core', 'pageSize': 100})
    path = RAW / f'abstract-batch-{index}.json'
    if not path.exists():
        data = get(url, 'application/json')
        value = json.loads(data)
        if value.get('hitCount', 0) > 100:
            raise ValueError('Unexpected truncated DOI batch')
        path.write_bytes(data)
    value = json.loads(path.read_text())
    if value.get('request', {}).get('queryString') != query:
        raise ValueError('Cached DOI batch does not match the requested queue')
    return value['resultList']['result'], {'source_url': url, 'raw_path': str(path.relative_to(ROOT)),
             'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'hit_count': value['hitCount']}


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    queue = [r for r in json.loads((ROOT/'data/phase2/backlog-screening.json').read_text())
             if r['decision'] in ('include_for_abstract_review', 'uncertain')]
    chunks = [queue[i:i+20] for i in range(0, len(queue), 20)]
    found = {}; provenance = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for records, source in pool.map(batch, enumerate(chunks)):
            provenance.append(source)
            for r in records:
                doi = (r.get('doi') or '').lower()
                if doi and (doi not in found or len(r.get('abstractText', '')) > len(found[doi].get('abstractText', ''))):
                    found[doi] = r
    packets = []
    for row in queue:
        meta = found.get(row['doi'].lower())
        packets.append({'queue_record': row, 'metadata': meta,
                        'status': 'abstract_available' if meta and meta.get('abstractText') else 'abstract_unavailable'})
    (RAW/'screening-packets.json').write_text(json.dumps(packets, indent=2) + '\n')
    for i, group in enumerate((packets[:40], packets[40:])):
        (RAW/f'screening-packets-{i}.json').write_text(json.dumps(group, indent=2) + '\n')
    (RAW/'metadata.json').write_text(json.dumps({'resultList': {'result': list(found.values())}}, indent=2) + '\n')
    summary = {'retrieved_at': datetime.date.today().isoformat(), 'queue_records': len(queue),
               'abstracts_available': sum(p['status'] == 'abstract_available' for p in packets),
               'missing_abstract_dois': [p['queue_record']['doi'] for p in packets if p['status'] != 'abstract_available'],
               'batches': provenance, 'query_scope': 'Fixed 67 priority plus 12 uncertain title-screened records; not a new exhaustive search'}
    (ROOT/'data/phase3').mkdir(exist_ok=True)
    (ROOT/'data/phase3/abstract-retrieval.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: summary[k] for k in ('queue_records','abstracts_available','missing_abstract_dois')}))


if __name__ == '__main__':
    main()
