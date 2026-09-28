import json
import tempfile
import unittest
from pathlib import Path

from scripts import boltz_validation_inference as runner


class ValidationInferenceTests(unittest.TestCase):
    def test_frozen_seeds_are_distinct(self):
        self.assertEqual(runner.SEEDS, (2001, 2002))
        self.assertEqual(len(set(runner.SEEDS)), 2)

    def test_validation_requires_one_affinity_and_structure_per_input(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); inp = root / 'inputs'; inp.mkdir()
            a = inp / 'CHEMBL1.yaml'; a.write_text('x')
            out = root / 'seed'; out.mkdir()
            (out / 'affinity_CHEMBL1.json').write_text(json.dumps({'affinity_pred_value': 6.2, 'affinity_probability_binary': .4}))
            (out / 'CHEMBL1_model_0.cif').write_text('data_CHEMBL1')
            result = runner.validate_seed_outputs([a], out)
            self.assertTrue(result['all_expected_outputs_valid'])
            (out / 'CHEMBL1_model_1.cif').write_text('duplicate')
            result = runner.validate_seed_outputs([a], out)
            self.assertFalse(result['all_expected_outputs_valid'])

    def test_invalid_affinity_probability_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); inp = root / 'inputs'; inp.mkdir(); a = inp / 'CHEMBL1.yaml'; a.write_text('x')
            out = root / 'seed'; out.mkdir()
            (out / 'affinity_CHEMBL1.json').write_text(json.dumps({'affinity_pred_value': 6.2, 'affinity_probability_binary': 2}))
            (out / 'CHEMBL1_model_0.cif').write_text('data_CHEMBL1')
            self.assertFalse(runner.validate_seed_outputs([a], out)['all_expected_outputs_valid'])


if __name__ == '__main__':
    unittest.main()
