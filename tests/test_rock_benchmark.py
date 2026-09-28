import unittest
from scripts.rock_benchmark import classify, neighbor_predictions


class RockTests(unittest.TestCase):
    def test_censored_and_mismatched_labels_are_separate(self):
        row = dict(target_chembl_id='CHEMBL2973', assay_chembl_id='CHEMBL4328667', standard_type='IC50', standard_units='nM', standard_value='10000', standard_relation='>')
        self.assertEqual(classify(row), 'right_censored')
        self.assertEqual(classify({**row, 'standard_relation': '='}), 'exact')
        self.assertEqual(classify({**row, 'standard_type': 'Ki'}), 'different_endpoint_or_units')
        self.assertEqual(classify({**row, 'assay_chembl_id': 'other'}), 'different_target_or_assay')
        self.assertEqual(classify({**row, 'standard_value': 'nan'}), 'invalid_value')
        self.assertEqual(classify({**row, 'data_validity_comment': 'flag'}), 'quality_flag')

    def test_scaffold_members_cannot_leak_into_training(self):
        rows = [dict(molecule_id='a', canonical_smiles='Cc1ccccc1', scaffold='benzene', pIC50=8.),
                dict(molecule_id='b', canonical_smiles='CCc1ccccc1', scaffold='benzene', pIC50=9.),
                dict(molecule_id='c', canonical_smiles='Cc1ccncc1', scaffold='pyridine', pIC50=5.)]
        predictions = neighbor_predictions(rows)
        for p in predictions:
            self.assertNotEqual(p['scaffold'], p['nearest_training_scaffold'])
        self.assertEqual(predictions[0]['predicted_pIC50'], 5.)
        self.assertEqual(predictions[1]['predicted_pIC50'], 5.)
        self.assertEqual(predictions[2]['control_pIC50'], 8.5)


if __name__ == '__main__':
    unittest.main()
