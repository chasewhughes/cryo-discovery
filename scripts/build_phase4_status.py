#!/usr/bin/env python3
"""Update acquisition status without treating abstract curation as full-text completion."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def remaining_queue(queue, studies):
    by_doi = {s['doi']: s for s in studies}
    result = []
    for row in queue:
        study = by_doi.get(row['doi'])
        if study and study['source_access'] == 'full_text':
            continue
        result.append({**row, 'curated_source_access': study['source_access'] if study else None,
                       'next_action': 'Obtain main article; supplement/abstract already reviewed' if study else 'Retrieve and review primary full text'})
    return result


def main():
    prior = json.loads((ROOT / 'data/phase3/fulltext-queue.json').read_text())['records']
    studies = []
    for path in sorted((ROOT / 'data/extractions').glob('phase4-*.json')):
        studies.extend(json.loads(path.read_text()))
    selected = [r for r in prior if r['priority'] == 'high']
    assert {r['doi'] for r in selected} == {s['doi'] for s in studies}
    indexed = {s['doi']: s for s in studies}
    status = []
    for record in selected:
        study = indexed[record['doi']]
        status.append({'doi': record['doi'], 'title': study['title'],
                       'source_access': study['source_access'], 'review_status': study['review_status'],
                       'main_fulltext_review_complete': study['source_access'] == 'full_text',
                       'experiment_summaries': len(study['experiments']),
                       'source_paths': [study['raw_source_path']] + study.get('additional_source_paths', [])})
    remaining = remaining_queue(prior, studies)
    folder = ROOT / 'data/phase4'
    folder.mkdir(exist_ok=True)
    def write(name, data):
        (folder / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    write('priority-review.json', {'reviewed_at': '2026-09-05', 'selected_records': len(selected),
                                  'access_counts': dict(Counter(s['source_access'] for s in studies)),
                                  'records': status})
    write('fulltext-queue.json', {'record_count': len(remaining),
                                'counts_by_priority': dict(Counter(r['priority'] for r in remaining)),
                                'records': remaining})
    files = []
    raw = ROOT / 'data/raw/phase4'
    if raw.exists():
        for path in sorted(raw.iterdir()):
            if path.is_file() and not path.name.startswith('._'):
                content = path.read_bytes()
                files.append({'path': str(path.relative_to(ROOT)), 'bytes': len(content),
                              'sha256': hashlib.sha256(content).hexdigest()})
    if files:
        write('source-files.json', {'files': files, 'note': 'Includes successful sources and failed-route captures; only extraction-declared paths support evidence. Raw files are local and excluded from Git.'})
    print(json.dumps({'new_studies': len(studies), 'new_experiments': sum(len(s['experiments']) for s in studies),
                      'access': dict(Counter(s['source_access'] for s in studies)), 'remaining_fulltexts': len(remaining)}))


if __name__ == '__main__':
    main()
