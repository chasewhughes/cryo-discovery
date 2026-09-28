#!/usr/bin/env python3
"""Read deposited XLSX/TSV data; recompute descriptive outcomes without editing workbooks."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/phase2'
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
CLONES = {'G-Cl7': 'iPSC-4', 'H-Cl14': 'iPSC-5', 'COLL-C2-Cl3': 'iPSC-6'}
ARMS = ['CS10', 'IRI-I5', 'IRI-I10']


def read_sheet(path, sheet_path='xl/worksheets/sheet1.xml'):
    """Read Sheet1 cell values and formula markup, including cached shared formulas.

    This is read-only ZIP/XML extraction, not a workbook authoring or formula engine.
    Recovery calculations below are independently recomputed from measured inputs.
    """
    with ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(s.itertext()) for s in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        cells = {}
        for c in ET.fromstring(z.read(sheet_path)).findall('.//m:c', NS):
            v, f = c.find('m:v', NS), c.find('m:f', NS)
            value = v.text if v is not None else None
            if c.get('t') == 's':
                value = strings[int(value)]
            elif c.get('t') == 'inlineStr':
                value = ''.join(c.find('m:is', NS).itertext())
            elif c.get('t') == 'e':
                raise ValueError(f'Source workbook error at {c.attrib["r"]}: {value}')
            elif value is not None and c.get('t') not in ('str', 'b'):
                value = float(value)
                if not math.isfinite(value):
                    raise ValueError('Nonfinite source number')
            cells[c.attrib['r']] = {'value': value, 'formula': ET.tostring(f, encoding='unicode') if f is not None else None}
        return cells


def recovery(viable_per_ml, volume_ml, initial_viable):
    if initial_viable <= 0 or min(viable_per_ml, volume_ml) < 0:
        raise ValueError('Invalid recovery denominator or input')
    return 100 * viable_per_ml * volume_ml / initial_viable


def main():
    provenance = json.loads((ROOT / 'data/phase2/archive-index.json').read_text())
    for file in provenance['selected_files']:
        assert hashlib.sha256((ROOT / file['local_path']).read_bytes()).hexdigest() == file['sha256']
    rec = read_sheet(RAW / 'figure2a-recovery.xlsx')
    via = read_sheet(RAW / 'figure2a-viability.xlsx')
    conf = read_sheet(RAW / 'figure2b.xlsx')
    val = lambda cells, address: cells[address]['value']
    records = []
    for r in range(4, 31):
        clone, arm = val(rec, f'D{r}'), val(rec, f'E{r}')
        assert clone in CLONES and arm in ARMS
        assert val(via, f'B{r}') == val(rec, f'B{r}')
        assert val(via, f'D{r}') == clone and val(via, f'E{r}') == arm
        assert val(via, f'C{r}') == CLONES[clone]
        initial, live, volume = [val(rec, f'{c}{r}') for c in ('G', 'H', 'K')]
        result = recovery(live, volume, initial)
        assert math.isclose(result, val(rec, f'M{r}'), abs_tol=1e-10)
        assert math.isclose(live * volume, val(rec, f'L{r}'), abs_tol=1e-8)
        assert val(rec, f'J{r}') == val(via, f'G{r}')
        records.append({'sample_id': val(rec, f'B{r}'), 'clone': clone, 'cell_line': CLONES[clone],
                        'arm': arm, 'aliquot': val(rec, f'F{r}'), 'initial_viable_cells': initial,
                        'post_thaw_viable_cells_per_ml': live, 'volume_ml': volume,
                        'recovery_percent': result, 'viability_percent': val(via, f'G{r}'),
                        'source_row': r, 'source_sheet': 'Sheet1'})
    assert len({r['sample_id'] for r in records}) == 27
    summaries = []
    for index, line in enumerate(CLONES.values()):
        for j, arm in enumerate(ARMS):
            group = [r for r in records if r['cell_line'] == line and r['arm'] == arm]
            assert len(group) == 3
            row = {'cell_line': line, 'arm': arm, 'technical_vials': 3,
                   'confluence_24h_percent': val(conf, f'{chr(67+j)}{5+index}')}
            for metric in ('recovery', 'viability'):
                values = [r[f'{metric}_percent'] for r in group]
                row[f'{metric}_mean_percent'] = statistics.mean(values)
                row[f'{metric}_technical_sd_pp'] = statistics.stdev(values)
            summaries.append(row)
    overall = []
    for index, arm in enumerate(ARMS):
        lines = [r for r in summaries if r['arm'] == arm]
        row = {'arm': arm, 'donor_lines': 3}
        for metric, cells, column, source_row in [('recovery', rec, chr(80+index), 17), ('viability', via, chr(74+index), 18)]:
            values = [r[f'{metric}_mean_percent'] for r in lines]
            row[f'{metric}_mean_percent'] = statistics.mean(values)
            row[f'{metric}_between_line_sd_pp'] = statistics.stdev(values)
            assert math.isclose(row[f'{metric}_mean_percent'], val(cells, f'{column}{source_row}'), abs_tol=1e-10)
        overall.append(row)
    effects = []
    for line in CLONES.values():
        groups = {r['arm']: r for r in summaries if r['cell_line'] == line}
        effects.append({'cell_line': line, 'comparison': 'IRI-I5 minus CS10',
                        **{f'{metric}_difference_pp': groups['IRI-I5'][f'{metric}_mean_percent'] - groups['CS10'][f'{metric}_mean_percent'] for metric in ('recovery','viability')},
                        'confluence_24h_difference_pp': groups['IRI-I5']['confluence_24h_percent'] - groups['CS10']['confluence_24h_percent']})
    sets = {}
    gene_summary = []
    for name in ('cs10', 'iri-a', 'iri-b'):
        with (RAW / f'deg-{name}.csv').open() as f:
            genes = list(csv.DictReader(f, delimiter='\t'))
        assert set(genes[0]) == {'Ensembl','Symbol','log2FoldChange','padj'}
        assert len({g['Ensembl'] for g in genes}) == len(genes)
        retained = {g['Ensembl']: g for g in genes if float(g['padj']) <= .05 and abs(float(g['log2FoldChange'])) > math.log2(3)}
        sets[name] = retained
        gene_summary.append({'deposited_label': name, 'deposited_rows': len(genes),
                             'padj_le_005_abs_fc_gt_3_genes': len(retained)})
    common = set.intersection(*(set(s) for s in sets.values()))
    concordant = [g for g in sorted(common) if len({float(s[g]['log2FoldChange']) > 0 for s in sets.values()}) == 1]
    donor_common = {}
    figure3_genes = set()
    for direction in ('up', 'down'):
        groups = {}
        for name in ('cs10', 'iri-a', 'iri-b'):
            values = (RAW / f'common-{direction}-{name}.tsv').read_text().splitlines()
            assert len(set(values)) == len(values) and all(values)
            groups[name] = set(values)
        union = set.union(*groups.values())
        shared = set.intersection(*groups.values())
        figure3_genes.update(union)
        donor_common[direction] = {'per_list_counts': {k: len(v) for k,v in groups.items()},
                                   'union_count': len(union), 'shared_count': len(shared),
                                   'shared_symbols': sorted(shared)}
    assert len(figure3_genes) == 492
    output = {
        'source_dataset': 'https://doi.org/10.5281/zenodo.14038512',
        'analysis_type': 'Independent descriptive recomputation of deposited figure inputs and processed DEG-list intersection',
        'measurement_records': records, 'line_summaries': summaries, 'overall': overall,
        'within_line_contrasts': effects, 'processed_expression_lists': gene_summary,
        'common_thresholded_genes': len(common), 'common_same_direction_genes': len(concordant),
        'common_gene_ids': sorted(common),
        'figure3_per_donor_common_lists': donor_common,
        'figure3_union_all_treatments_gene_count': len(figure3_genes),
        'figure3_shared_across_all_treatments_gene_count': sum(x['shared_count'] for x in donor_common.values()),
        'expression_comparison_note': 'The 712 intersection uses combined contrast lists; Figure 3 uses lists already intersected across cell lines. Its 492 is a union across treatments, not the intersection. Deposited lists reproduce Figure 3B/C: 399 downregulated plus 93 upregulated genes in the union; 128 down plus 38 up shared by all arms.',
        'checks': ['All selected SHA-256 hashes match extraction manifest', '27 unique aliquots; 3 per donor line and arm',
                   'All 27 recovery and yield formulas independently recomputed', 'All 27 viability values agree between workbooks',
                   'All 6 overall means match cached source formulas', 'Original Figure 2 and Figure 3 PNGs visually inspected by root',
                   'Six per-donor-common gene-list counts and Venn regions reconcile with deposited Figure 3'],
        'limitations': ['Descriptive contrasts; no new significance tests or biological replication claims.',
                       'Recovery sheet column C uses legacy iPSC-1/2/3 labels. Clone IDs and viability sheet map these to final iPSC-4/5/6.',
                       'Viability is the recorded instrument percentage; rounded live/total counts need not exactly reconstruct it.',
                       'IRI-I5 versus CS10 changes both DMSO concentration and equilibration, so it does not isolate IRI causality.',
                       'Expression files are already processed and filtered; no count matrix or sample table identified in the archive inventory.',
                       'IRI_A/IRI_B label-to-formulation mapping is not inferred from filename order.',
                       'Intersection analysis does not reproduce normalization, DESeq2 fitting, or multiple-testing adjustment.']}
    (ROOT / 'data/phase2/iri-2024-analysis.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({k: output[k] for k in ('overall','within_line_contrasts','processed_expression_lists','common_thresholded_genes','common_same_direction_genes')}, indent=2))


if __name__ == '__main__':
    main()
