import unittest

try:
    from scripts.prepare_matched_hydration import CONTROLS, build_solute
except ImportError:
    CONTROLS = None


@unittest.skipIf(CONTROLS is None, "Requires isolated MD environment")
class MatchedPreparationTests(unittest.TestCase):
    def test_controls_are_same_formula_and_expected_stereo(self):
        from rdkit import Chem
        from rdkit.Chem import Descriptors
        masses = []
        for code, expected in [('leu', 1), ('ile', 2)]:
            mol, top, _ = build_solute(code, 817)
            self.assertEqual(Chem.GetFormalCharge(mol), 0)
            centers = Chem.FindMolChiralCenters(mol, includeUnassigned=True, includeCIP=True)
            self.assertEqual(len(centers), expected)
            self.assertTrue(all(label == 'S' for _, label in centers))
            self.assertEqual(Chem.rdMolDescriptors.CalcMolFormula(mol), 'C6H13NO2')
            masses.append(Descriptors.MolWt(mol))
            self.assertEqual(top.getNumAtoms(), mol.GetNumAtoms())
        self.assertAlmostEqual(masses[0], masses[1], places=8)

    def test_conformers_are_seeded_and_nonidentical(self):
        import numpy as np
        from openmm import unit
        a, _, xa = build_solute('leu', 20261011)
        b, _, xb = build_solute('leu', 20261012)
        self.assertNotEqual(a.GetNumAtoms(), 0)
        self.assertFalse(np.array_equal(xa.value_in_unit(unit.nanometer), xb.value_in_unit(unit.nanometer)))


if __name__ == '__main__':
    unittest.main()
