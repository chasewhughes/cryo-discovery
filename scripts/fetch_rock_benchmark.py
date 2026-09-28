"""Bounded primary/reference retrieval; invoke through with_external_storage.py."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/phase15/rock'
URLS = {
    'targets.json': 'https://www.ebi.ac.uk/chembl/api/data/target.json?pref_name__icontains=Rho-associated&limit=100',
    'document.json': 'https://www.ebi.ac.uk/chembl/api/data/document.json?doi=10.1021%2Facs.jmedchem.8b01098',
    'activities.json': 'https://www.ebi.ac.uk/chembl/api/data/activity.json?document_chembl_id=CHEMBL4325872&target_chembl_id=CHEMBL2973&limit=1000',
    'assay.json': 'https://www.ebi.ac.uk/chembl/api/data/assay/CHEMBL4328667.json',
    '6ED6-entry.json': 'https://data.rcsb.org/rest/v1/core/entry/6ED6',
    '6ED6-polymer.json': 'https://data.rcsb.org/rest/v1/core/polymer_entity/6ED6/1',
    'J0P.json': 'https://data.rcsb.org/rest/v1/core/chemcomp/J0P',
    '6ED6.cif': 'https://files.rcsb.org/download/6ED6.cif',
}


def fetch(item):
    name, url = item
    p = RAW/name
    if not p.exists():
        request = urllib.request.Request(url, headers={'User-Agent': 'cryo-research/phase15'})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(10_000_001)
        if len(data) > 10_000_000:
            raise ValueError('Source exceeds bounded download size')
        if name.endswith('.json'):
            json.loads(data)
        elif not data.lstrip().startswith(b'data_'):
            raise ValueError('Not a mmCIF file')
        p.write_bytes(data)
    data = p.read_bytes()
    if name.endswith('.json'):
        value = json.loads(data)
        if value.get('page_meta', {}).get('next'):
            raise ValueError(f'{name}: pagination incomplete; extend acquisition explicitly')
    return {'source_path': str(p.relative_to(ROOT)), 'url': url,
            'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


if __name__ == '__main__':
    RAW.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as executor:
        sources = list(executor.map(fetch, URLS.items()))
    output = ROOT/'data/phase15/rock-source-manifest.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'verified_at': datetime.now(timezone.utc).isoformat(),
                                  'sources': sources,
                                  'licenses': {'ChEMBL': 'CC BY-SA 3.0; attribution and share-alike apply to derived data',
                                               'RCSB PDB': 'CC0'}}, indent=2)+'\n')
    print(f'Acquired/verified {len(sources)} sources')
