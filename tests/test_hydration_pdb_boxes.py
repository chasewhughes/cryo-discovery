import unittest
import numpy as np
from scripts.fix_hydration_pdb_boxes import corrected_pdb


class PdbBoxTests(unittest.TestCase):
    def test_corrects_units_and_preserves_coordinate_records(self):
        text='CRYST1   40.000   40.000   40.000  90.00  90.00  90.00 P 1           1\nATOM      1  O   HOH A   1       1.000   2.000   3.000\n'
        result=corrected_pdb(text,np.diag([3.7,3.8,3.9]))
        self.assertEqual([float(result[i:j]) for i,j in [(6,15),(15,24),(24,33)]],[37,38,39])
        self.assertEqual(result.splitlines()[1:],text.splitlines()[1:])
        self.assertEqual(result.splitlines()[0][54:],text.splitlines()[0][54:])


if __name__=='__main__':unittest.main()
