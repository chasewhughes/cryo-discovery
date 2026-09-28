import unittest

from scripts.prepare_rock_validation import split_rows


class ValidationSplitTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
