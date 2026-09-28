import unittest

from scripts.prepare_rock_scaffold import split_rows, validate_heldout_scaffolds


class ScaffoldSplitTests(unittest.TestCase):
    def test_single_scaffold_is_ineligible(self):
        with self.assertRaises(ValueError):
            split_rows([{'molecule_id': str(i), 'scaffold': 'same'} for i in range(30)])

    def test_split_is_label_and_order_independent(self):
        rows = [{'molecule_id': str(i), 'scaffold': str(i), 'observed_pIC50': i} for i in range(30)]
        first = split_rows(rows)
        for row in rows:
            row['observed_pIC50'] = -row['observed_pIC50']
        second = split_rows(list(reversed(rows)))
        self.assertEqual(first, second)
        self.assertIn('cryo-phase19-split-1900:', first['method'])

    def test_prior_scaffold_overlap_rejects_heldout_only(self):
        rows = [{'molecule_id': str(i), 'scaffold': str(i)} for i in range(30)]
        partition = split_rows(rows)
        heldout = partition['test_ids'][0]
        with self.assertRaises(ValueError):
            validate_heldout_scaffolds(rows, partition, {heldout})
        validate_heldout_scaffolds(rows, partition, {'not-present'})


if __name__ == '__main__':
    unittest.main()
