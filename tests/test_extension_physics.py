import tempfile
import unittest
from pathlib import Path
from scripts.verify_hydration_extensions import tree_without_rng

class ExtensionPhysicsTests(unittest.TestCase):
    def test_new_rng_is_allowed_but_physical_pressure_change_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            parent=Path(td)/'parent.xml';branch=Path(td)/'branch.xml'
            parent.write_text('<System><Force type="MonteCarloBarostat" pressure="1" randomSeed="10"/></System>')
            branch.write_text('<System><Force randomSeed="20" pressure="1" type="MonteCarloBarostat"/></System>')
            self.assertEqual(tree_without_rng(parent),tree_without_rng(branch))
            branch.write_text('<System><Force randomSeed="20" pressure="2" type="MonteCarloBarostat"/></System>')
            self.assertNotEqual(tree_without_rng(parent),tree_without_rng(branch))

if __name__=='__main__':unittest.main()
