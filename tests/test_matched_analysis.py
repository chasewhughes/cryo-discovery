import unittest
import numpy as np
from scripts.analyze_matched_hydration import compare_groups

class MatchedAnalysisTests(unittest.TestCase):
    def rows(self,separate):
        rows=[]
        for c,index in [('leu',0),('ile',99 if separate else 0)]:
            for seed in range(3):
                pdf=np.zeros(100);pdf[index]=200
                count=(10 if c=='leu' or not separate else 12)+.1*seed
                rows.append({'name':f'{c}-{seed}','compound':c,'seed':seed,'summary':{'mean_counts':[count]*7,
                    'mean_count_0_30nm':count,'mean_pdf':pdf.tolist(),'mean_density_g_ml':1.0}})
        return rows
    def test_identical_groups_have_no_distribution_separation(self):
        r=compare_groups(self.rows(False))
        self.assertEqual(r['between_compound_mean_pdf_tv'],0)
        self.assertFalse(r['all_cross_tvs_exceed_all_within_tvs'])
        self.assertFalse(r['all_cross_count_differences_same_sign'])
    def test_known_difference_uses_trajectory_units_and_expected_pair_counts(self):
        r=compare_groups(self.rows(True))
        self.assertEqual(r['between_compound_mean_pdf_tv'],1)
        self.assertEqual(len(r['cross_compound_pairs']),9)
        self.assertEqual(len(r['groups']['leu']['within_pair_tv']),3)
        self.assertAlmostEqual(r['leu_minus_ile_mean_counts'][2],-2)
        self.assertAlmostEqual(r['groups']['leu']['sample_sd_counts'][2],.1)
        self.assertTrue(r['all_cross_count_differences_same_sign'])
        self.assertTrue(r['all_cross_tvs_exceed_all_within_tvs'])

if __name__=='__main__':unittest.main()
