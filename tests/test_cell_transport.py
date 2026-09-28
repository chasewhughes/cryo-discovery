import unittest

import numpy as np

from scripts.cell_transport import Parameters, linear_reference, reference_error, simulate


class TransportTests(unittest.TestCase):
    def test_isotonic_and_loaded_equilibria(self):
        for m1, m2 in [(1, 0), (2, 3)]:
            initial = (1/m1, m2/m1)
            r = simulate([dict(duration_min=10, m1=m1, m2=m2)], initial=initial)
            np.testing.assert_allclose(r["boundaries"][-1]["final"], initial, atol=1e-12)
            self.assertLess(reference_error([dict(duration_min=10, m1=m1, m2=m2)], r), 1e-9)

    def test_pure_water_equilibrium_conserves_nonpermeant(self):
        r = simulate([dict(duration_min=100, m1=2, m2=0)])
        self.assertAlmostEqual(r["trajectory"][-1]["w"], .5, places=8)
        self.assertEqual(r["trajectory"][-1]["s"], 0)

    def test_appendix_reference_across_bath_switches(self):
        steps = [dict(duration_min=2, m1=1, m2=3), dict(duration_min=3, m1=.5, m2=1)]
        r = simulate(steps)
        self.assertLess(reference_error(steps, r), 1e-7)
        self.assertEqual(r["boundaries"][0]["final"], r["boundaries"][1]["initial"])
        self.assertTrue(all(a["time_min"] < b["time_min"] for a, b in zip(r["trajectory"], r["trajectory"][1:])))

    def test_constant_bath_partition_invariance(self):
        one = simulate([dict(duration_min=10, m1=1, m2=5)])
        two = simulate([dict(duration_min=5, m1=1, m2=5)]*2)
        for key, value in one["metrics"].items():
            self.assertAlmostEqual(value, two["metrics"][key], places=7)

    def test_reject_nonphysical_inputs(self):
        for bad in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                Parameters(b=bad)
        with self.assertRaises(ValueError):
            simulate([dict(duration_min=1, m1=1, m2=-1)])
        with self.assertRaises(ValueError):
            simulate([dict(duration_min=1, m1=1, m2=1)], initial=(0, 0))


if __name__ == "__main__":
    unittest.main()
