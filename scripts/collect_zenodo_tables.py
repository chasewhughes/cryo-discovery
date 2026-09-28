#!/usr/bin/env python3
"""Retrieve study tables with RAR5 QuickOpen and checked, bounded HTTP ranges.

Never extract archive paths onto the filesystem or execute deposited code.
Run through with_external_storage.py on the configured research workstation.
"""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib

from index_remote_rar import Reader, URL, parse_header, vint

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/phase2'
QO_OFFSET = 3510940099  # RAR5 main-header locator for this version of the archive.
ARCHIVE_SIZE = 3511664912
SIGNATURE = b'Rar!\x1a\x07\x01\x00'
MAX_FILE = 10 * 1024 * 1024


def checked_block(body):
    return struct.pack('<I', zlib.crc32(body) & 0xffffffff) + body


def quick_open(tail):
    header = parse_header(tail, QO_OFFSET)
    assert header['kind'] == 3 and header['name'] == 'QO'
    pos = header['header_bytes']
    end = pos + header['packed_bytes']
    rows = []
    while pos < end:
        size, cursor = vint(tail, pos + 4)
        stop = cursor + size
        if stop > end or zlib.crc32(tail[pos+4:stop]) & 0xffffffff != struct.unpack_from('<I', tail, pos)[0]:
            raise ValueError('QuickOpen cache CRC mismatch')
        flags, cursor = vint(tail, cursor)
        distance, cursor = vint(tail, cursor)
        count, cursor = vint(tail, cursor)
        if flags != 0 or cursor + count != stop:
            raise ValueError('Unsupported QuickOpen cache entry')
        rows.append(parse_header(tail[cursor:stop], QO_OFFSET - distance))
        pos = stop
    return rows


def fill_gap(gap):
    start, end = gap
    buf = Reader(URL).read(start, end - start)
    rows = []
    pos = start
    while pos < end:
        block = parse_header(buf[pos-start:], pos)
        rows.append(block)
        if block['next_offset'] <= pos or block['next_offset'] > end:
            raise ValueError('Invalid archive gap boundaries')
        pos = block['next_offset']
    return rows


def extract(row, output):
    if row['solid'] or row['directory'] or row['unpacked_bytes'] > MAX_FILE or row['packed_bytes'] > MAX_FILE:
        raise ValueError('Unsupported or oversized selected file')
    block = Reader(URL).read(row['block_offset'], row['header_bytes'] + row['packed_bytes'])
    actual = parse_header(block, row['block_offset'])
    if actual != row:
        raise ValueError('QuickOpen entry differs from original file header')
    # Minimal single-file archive: remove original archive locator to missing data.
    fragment = SIGNATURE + checked_block(bytes([3, 1, 0, 0])) + block + checked_block(bytes([3, 5, 0, 0]))
    with tempfile.NamedTemporaryFile(suffix='.rar') as f:
        f.write(fragment)
        f.flush()
        result = subprocess.run(['/usr/bin/bsdtar', '-xOf', f.name], capture_output=True, check=True)
    content = result.stdout
    if len(content) != row['unpacked_bytes']:
        raise ValueError('Extracted size differs from archive')
    if 'data_crc32' in row and zlib.crc32(content) & 0xffffffff != row['data_crc32']:
        raise ValueError('Extracted file CRC mismatch')
    output.write_bytes(content)
    return {'archive_path': row['name'], 'local_path': str(output.relative_to(ROOT)),
            'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
            'header_and_content_crc_verified': True}


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    tail_path = RAW / 'zenodo-rar-tail.bin'
    if not tail_path.exists():
        tail_path.write_bytes(Reader(URL).read(QO_OFFSET, ARCHIVE_SIZE - QO_OFFSET))
    rows = sorted(quick_open(tail_path.read_bytes()), key=lambda r: r['block_offset'])
    gaps = []
    previous = 29
    for row in rows:
        if row['block_offset'] > previous:
            gaps.append((previous, row['block_offset']))
        elif row['block_offset'] < previous:
            raise ValueError('Overlapping QuickOpen entries')
        previous = row['next_offset']
    if previous < QO_OFFSET:
        gaps.append((previous, QO_OFFSET))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for extra in pool.map(fill_gap, gaps):
            rows.extend(extra)
    rows.sort(key=lambda r: r['block_offset'])
    previous = 29
    for row in rows:
        assert row['block_offset'] == previous
        previous = row['next_offset']
    assert previous == QO_OFFSET
    inventory = RAW / 'zenodo-complete-inventory.json'
    inventory.write_text(json.dumps(rows, indent=2) + '\n')
    selections = {
        'Figure 2A - Recovery.xlsx': 'figure2a-recovery.xlsx',
        'Figure 2A - Viability.xlsx': 'figure2a-viability.xlsx',
        'Figure 2A - Table view.xlsx': 'figure2a-table.xlsx',
        'Figure 2B.xlsx': 'figure2b.xlsx',
        'Figure 2.png': 'figure2.png',
        'Figure 3.png': 'figure3.png',
        'sig_CS10_over_Control.csv': 'deg-cs10.csv',
        'sig_IRI_A_over_Control.csv': 'deg-iri-a.csv',
        'sig_IRI_B_over_Control.csv': 'deg-iri-b.csv',
        'common_up_sigGenes_3fold_CS10.csv': 'common-up-cs10.tsv',
        'common_up_sigGenes_3fold_IRI_A.csv': 'common-up-iri-a.tsv',
        'common_up_sigGenes_3fold_IRI_B.csv': 'common-up-iri-b.tsv',
        'common_down_sigGenes_3fold_CS10.csv': 'common-down-cs10.tsv',
        'common_down_sigGenes_3fold_IRI_A.csv': 'common-down-iri-a.tsv',
        'common_down_sigGenes_3fold_IRI_B.csv': 'common-down-iri-b.tsv',
    }
    selected = []
    for name, output in selections.items():
        matches = [r for r in rows if Path(r.get('name', '')).name == name]
        assert len(matches) == 1, (name, len(matches))
        selected.append(extract(matches[0], RAW / output))
        print('Verified ' + output, flush=True)
    summary = {
        'dataset_doi': '10.5281/zenodo.14038512', 'source_url': URL,
        'archive_size_bytes': ARCHIVE_SIZE, 'status': 'complete_header_inventory_selective_data_download',
        'archive_full_md5_verified': False,
        'verification': 'QuickOpen cache CRCs; continuous indexed block offsets; actual headers and decompressed CRCs for selected files',
        'file_count': sum(r['kind'] == 2 and not r.get('directory') for r in rows),
        'gap_ranges_retrieved': len(gaps), 'gap_bytes_retrieved': sum(b-a for a,b in gaps),
        'inventory_path': str(inventory.relative_to(ROOT)),
        'inventory_sha256': hashlib.sha256(inventory.read_bytes()).hexdigest(),
        'selected_files': selected,
        'table_like_paths': [r['name'] for r in rows if Path(r.get('name','')).suffix.lower() in ('.csv','.tsv','.txt','.xlsx','.r')],
    }
    (ROOT / 'data/phase2/archive-index.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'files_indexed': summary['file_count'], 'selected_downloads': len(selected)}))


if __name__ == '__main__':
    main()
