"""Independent geometry and ensemble checks for the new representation."""
import itertools
import unittest
try:
    import numpy as np
    import openmm as mm
    from openmm import unit
    from scripts.hydration_descriptor import measure, CUTOFFS
    from scripts.run_hydration_stability import add_barostat
except ImportError:
    mm = None


@unittest.skipIf(mm is None, 'Requires isolated MD environment')
class DescriptorTests(unittest.TestCase):
    def test_unique_water_and_closed_last_edge(self):
        # Water at x=.2 is seen by both solute atoms but must count only once.
        xyz = [[0,0,0],[.1,0,0],[.2,0,0],[.6,0,0],[2,0,0]]
        counts,pdf = measure(xyz,np.eye(3)*4,[0,1],[2,3,4])
        np.testing.assert_array_equal(counts,[1,1,1,1,1,1,2])
        self.assertAlmostEqual(pdf[-1],100)
        self.assertAlmostEqual(pdf.sum()*.005,1)

    def test_matches_independent_periodic_image_enumeration(self):
        rng=np.random.default_rng(817)
        xyz=rng.uniform(0,4,(70,3)); xyz[3]=[3.99,.01,.01]; xyz[0]=[.01,.01,.01]
        counts,pdf=measure(xyz,np.eye(3)*4,[0,1,2],list(range(3,70)))
        # Enumerate 27 periodic images rather than using vectorized minimum image.
        distances=[]
        for water in xyz[3:]:
            distances.append(min(float(np.linalg.norm(water-sol+4*np.array(shift)))
                for sol in xyz[:3] for shift in itertools.product([-1,0,1],repeat=3)))
        expected=[sum(d<=c for d in distances) for c in CUTOFFS]
        np.testing.assert_array_equal(counts,expected)
        hist=np.zeros(100)
        for d in distances:
            if d<=.5: hist[min(int(d/.005),99)]+=1
        np.testing.assert_allclose(pdf,hist/(sum(hist)*.005),atol=1e-10)

    def test_translation_wrapping_and_selection_permutation(self):
        # Avoid a bin edge: floating subtraction can put an exact edge on either side.
        xyz=np.array([[.05,0,0],[.1,0,0],[3.953,0,0],[.3,.1,0]])
        a=measure(xyz,np.eye(3)*4,[0,1],[2,3])
        b=measure(xyz+[8,4,-4],np.eye(3)*4,[1,0],[3,2])
        np.testing.assert_array_equal(a[0],b[0])
        np.testing.assert_allclose(a[1],b[1])

    def test_invalid_geometry_and_selections_rejected(self):
        xyz=np.zeros((3,3)); box=np.eye(3)*4
        for sol,wat in [([0,0],[1]),([0],[0]),([],[1]),([0],[3])]:
            with self.assertRaises(ValueError):measure(xyz,box,sol,wat)
        box[0,1]=.2
        with self.assertRaises(ValueError):measure(xyz,box,[0],[1])

    def test_barostat_only_in_npt_and_correct_conditions(self):
        for ensemble in ['NVT','NPT']:
            system=mm.System(); system.addParticle(1)
            add_barostat(system,ensemble,123)
            self.assertEqual(system.getNumForces(),ensemble=='NPT')
            if ensemble=='NPT':
                barostat=system.getForce(0)
                self.assertEqual(barostat.getFrequency(),25)
                self.assertEqual(barostat.getRandomNumberSeed(),100123)
                self.assertEqual(barostat.getDefaultPressure().value_in_unit(unit.bar),1)
                self.assertEqual(barostat.getDefaultTemperature().value_in_unit(unit.kelvin),273)


if __name__=='__main__':unittest.main()
