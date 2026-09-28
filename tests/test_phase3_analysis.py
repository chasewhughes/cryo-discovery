import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze_cm_data import describe


class Phase3IntegrityTests(unittest.TestCase):
    def test_dispersion_does_not_conflate_sd_with_sem(self):
        result = describe([85.75, 75.5, 82.75, 76.75])
        self.assertEqual(result['mean'], 80.1875)
        self.assertAlmostEqual(result['sample_sd'], 4.875)
        self.assertAlmostEqual(result['sample_sem'], 2.4375)
        self.assertAlmostEqual(result['population_sd'], 4.875 * math.sqrt(3 / 4))

    def test_undefined_or_nonfinite_dispersion_rejected(self):
        for values in ([], [1], [1, float('nan')], [1, float('inf')]):
            with self.assertRaises(ValueError):
                describe(values)

    def test_screening_covers_exact_selected_backlog(self):
        backlog = json.loads((ROOT / 'data/phase2/backlog-screening.json').read_text())
        selected = {r['doi'] for r in backlog
                    if r['decision'] in ('include_for_abstract_review', 'uncertain')}
        report = json.loads((ROOT / 'data/phase3/abstract-screening.json').read_text())
        rows = report['records']
        self.assertEqual({r['doi'] for r in rows}, selected)
        self.assertEqual(len(rows), len(selected))
        self.assertEqual(sum(report['counts'].values()), len(rows))
        for row in rows:
            self.assertLessEqual(row['first_publication_date'], report['screened_at'])
            if row['primary_study_status'] == 'review_or_nonprimary':
                self.assertNotEqual(row['decision'], 'include_fulltext_review')

    def test_fulltext_queue_excludes_curated_and_linked_versions(self):
        rows = json.loads((ROOT / 'data/phase3/abstract-screening.json').read_text())['records']
        queue = json.loads((ROOT / 'data/phase3/fulltext-queue.json').read_text())['records']
        expected = {r['doi'] for r in rows if r['decision'] in
                    ('include_fulltext_review', 'uncertain') and not r['curated_study_id']}
        self.assertEqual({r['doi'] for r in queue}, expected)
        self.assertEqual(len(queue), len(expected))
        corpus = {r['doi'] for r in json.loads((ROOT / 'data/pilot-studies.json').read_text())}
        for row in rows:
            if row['decision'] == 'linked_version':
                self.assertIn(row['bibliographic_version_group'], corpus)
                self.assertNotIn(row['doi'], corpus)


if __name__ == '__main__':
    unittest.main()
