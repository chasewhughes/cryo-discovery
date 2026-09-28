import unittest
import numpy as np
from scripts.analyze_hydration_extensions import sampling_grid

class ExtensionAnalysisTests(unittest.TestCase):
    def test_known_half_change_survives_fine_and_coarse_analysis(self):
        # Disjoint endpoint distributions have TV=1 regardless of sample length.
        pdf=np.zeros((1000,100));pdf[:500,0]=200;pdf[500:,99]=200
        config={'bins':[20,50,100],'endpoint_window_ps':[500,1000,2000,5000],
                'block_ps':[100,250,500],'random_seed':7,'block_mixing_permutations':10}
        rows=sampling_grid(pdf,config)
        self.assertEqual(len(rows),36)
        self.assertTrue(all(abs(r['observed_tv']-1)<1e-12 for r in rows))
        self.assertTrue(all(0<=q<=1+1e-12 for r in rows for q in r['mixed_tv_quantiles_05_50_95']))

    def test_overlapping_endpoint_groups_rejected(self):
        with self.assertRaises(ValueError):
            sampling_grid(np.full((1000,100),2.),{'bins':[100],
                'endpoint_window_ps':[6000],'block_ps':[100],
                'random_seed':7,'block_mixing_permutations':10})

if __name__=='__main__': unittest.main()
