import unittest
import numpy as np
from scripts.calibrate_hydration_sampling import coarsen, diagnose, tv

class SamplingCalibrationTests(unittest.TestCase):
    def test_coarsening_preserves_probability_and_contracts_tv(self):
        rng=np.random.default_rng(3)
        p=rng.dirichlet(np.ones(100),size=2)/.005
        fine=tv(*p)
        for bins in [20,50,100]:
            q=coarsen(p,bins)
            np.testing.assert_allclose(q.sum(axis=1)*.5/bins,1)
            self.assertLessEqual(tv(*q,bins),fine+1e-12)

    def test_constant_trajectory_has_zero_all_contrasts(self):
        p=np.full((300,100),2.)
        grid={'bins':[20,100],'endpoint_window_ps':[500,1500],
              'block_ps':[100,500],'permutations':5,'random_seed':1}
        rows=diagnose(p,grid)
        self.assertEqual(len(rows),8)
        self.assertTrue(all(r['observed_tv']==0 and r['mixed_tv_quantiles_05_50_95']==[0,0,0] for r in rows))

    def test_invalid_or_unbalanced_sampling_rejected(self):
        with self.assertRaises(ValueError): diagnose(np.ones((300,100)))
        with self.assertRaises(ValueError): diagnose(np.full((299,100),2.))
        with self.assertRaises(ValueError): diagnose(np.full((300,100),2.),
            {'bins':[100],'endpoint_window_ps':[500],'block_ps':[300],'random_seed':1,'permutations':5})

if __name__=='__main__': unittest.main()
