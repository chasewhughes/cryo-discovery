#!/usr/bin/env python3
"""Descriptive checks of published group means; never infer replicate-level synergy."""
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.table = self.row = self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table': self.table = []
        elif tag == 'tr': self.row = []
        elif tag in ('td', 'th'): self.cell = []

    def handle_data(self, text):
        if self.cell is not None: self.cell.append(text)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            if self.row is not None: self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            if self.table is not None: self.table.append(self.row)
            self.row = None
        elif tag == 'table' and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def additive_interaction(p00, p10, p01, p11):
    return p11 - p10 - p01 + p00


def percentage_check(mean, numerator, denominator, tolerance_pp=0.05):
    if not 0 <= numerator <= denominator or denominator <= 0:
        raise ValueError('Invalid numerator/denominator')
    pooled = 100 * numerator / denominator
    return {'reported_mean_percent': mean, 'numerator': numerator, 'denominator': denominator,
            'aggregate_ratio_percent': pooled, 'reported_minus_aggregate_pp': mean - pooled,
            'needs_aggregation_clarification': abs(mean - pooled) > tolerance_pp}


def main():
    source = ROOT / 'data/raw/phase5/porcine-embryos.html'
    content = source.read_bytes()
    parser = Tables()
    parser.feed(content.decode())
    analyses, checks = [], []
    for number, label in [(4, 'berberine × melatonin'), (5, 'Fe3O4 × AFP I'),
                          (6, 'antioxidant pair × nanoparticle/AFP pair')]:
        table = parser.tables[number - 1]
        assert table[0][1] == 'Survival Rate (%)' and len(table) == 6
        means = [float(re.match(r'[\d.]+', row[1]).group()) for row in table[1:5]]
        p00, p10, p01, p11 = means
        analyses.append({'table': number, 'comparison': label,
                         'reported_survival_means_percent': dict(zip(['p00', 'p10', 'p01', 'p11'], means)),
                         'combination_minus_best_component_pp': p11 - max(p10, p01),
                         'additive_interaction_pp': additive_interaction(*means),
                         'inferential_test': None})
        for row_number, row in enumerate(table[1:], 1):
            assert len(row) == len(table[0])
            for col, value in enumerate(row[1:], 1):
                counts = re.search(r'\((\d+)/(\d+)\)', value)
                if not counts: continue
                mean = float(re.match(r'[\d.]+', value).group())
                checks.append({'table': number, 'data_row': row_number, 'column': table[0][col],
                               **percentage_check(mean, *map(int, counts.groups()))})
    out = {'doi': '10.3390/antiox14121412', 'source_path': str(source.relative_to(ROOT)),
           'source_sha256': hashlib.sha256(content).hexdigest(),
           'analysis_type': 'Descriptive published-mean arithmetic, not raw replicate reanalysis',
           'interaction_scale': 'percentage-point additive survival scale; p11-p10-p01+p00',
           'comparisons': analyses, 'percentage_checks': checks,
           'aggregation_clarification_count': sum(c['needs_aggregation_clarification'] for c in checks),
           'unresolved_table_note': 'Table 6 fresh-control cytoskeleton cell contains 29.32 ± 3.42 (n=30), while ROS is blank. Do not shift or repair columns.',
           'limitations': ['Reported means may average replicate percentages, while parenthetical counts may be pooled or representative; discrepancies are clarification flags, not proof of errors.',
                           'At least three repeats are described, but replicate-level outcomes and covariance are unavailable; no interaction confidence interval or p-value is calculated.',
                           'The source reports one-way ANOVA/Tukey comparisons; higher combination means and nonsignificance versus fresh do not establish synergy or equivalence.',
                           'Interaction depends on the chosen response scale and may be affected by ceiling effects; these arithmetic checks do not rule out other mechanisms or models.']}
    target = ROOT / 'data/phase5/combination-analysis.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'comparisons': analyses, 'aggregation_clarifications': out['aggregation_clarification_count']}, indent=2))


if __name__ == '__main__': main()
