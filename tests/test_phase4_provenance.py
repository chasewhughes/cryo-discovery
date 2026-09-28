import tempfile
import unittest
from pathlib import Path

from scripts.audit_sources import evidence_text
from scripts.build_phase4_status import remaining_queue


class Phase4ProvenanceTests(unittest.TestCase):
    def test_supplement_does_not_complete_main_fulltext_queue(self):
        queue = [{'doi': '10.x/a'}, {'doi': '10.x/b'}, {'doi': '10.x/c'}]
        studies = [{'doi': '10.x/a', 'source_access': 'full_text'},
                   {'doi': '10.x/b', 'source_access': 'abstract_plus_supplement'}]
        remaining = remaining_queue(queue, studies)
        self.assertEqual([r['doi'] for r in remaining], ['10.x/b', '10.x/c'])
        self.assertEqual(remaining[0]['curated_source_access'], 'abstract_plus_supplement')
        self.assertIsNone(remaining[1]['curated_source_access'])

    def test_abstract_and_declared_supplement_support_are_combined(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'metadata.json').write_text('{}')
            (root / 'supplement.txt').write_text('Ethylene glycol is 12% v/v.')
            (root / 'unrelated.txt').write_text('Unrelated claim.')
            study = {'source_access': 'abstract_plus_supplement',
                     'raw_source_path': 'metadata.json',
                     'additional_source_paths': ['supplement.txt']}
            text = evidence_text(study, {'abstractText': 'Cells retained <b>viability</b>.'}, root)
            self.assertIn('12% v/v', text)
            self.assertIn('Cells retained viability', text)
            self.assertNotIn('Unrelated claim', text)


if __name__ == '__main__':
    unittest.main()
