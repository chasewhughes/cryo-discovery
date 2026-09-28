import json, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from scripts import runpod_stability as cloud

class StabilityGuards(unittest.TestCase):
    def reconciliation(self, **extra):
        value={'prior_gpu_reserve_usd':0.2,'verified_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'all_prior_research_pods_absent':True}; value.update(extra)
        f=tempfile.NamedTemporaryFile(mode='w',delete=False); json.dump(value,f); f.close(); return Path(f.name)

    def test_budget_aggregates_and_deduplicates(self):
        rec=self.reconciliation()
        cloud.check_budget([{'id':'same','deleted':True,'estimated_gpu_cost_usd':.1},{'id':'same','deleted':True,'estimated_gpu_cost_usd':.1}],rec)
        with self.assertRaises(ValueError): cloud.check_budget([{'id':'x','deleted':False,'estimated_gpu_cost_usd':.1}],rec)
        with self.assertRaises(ValueError): cloud.check_budget([{'id':'x','deleted':True,'estimated_gpu_cost_usd':9.8}],rec)

    def test_unconfirmed_deletion_is_false(self):
        with patch.object(cloud,'api',side_effect=[{'name':'cryo'},None,{'name':'cryo'}]):
            self.assertFalse(cloud.delete_pod({'id':'p','name':'cryo'}))

    def test_already_absent_deletion_is_confirmed(self):
        missing=HTTPError('https://rest.runpod.io/v1/pods/p',404,'Not Found',{},None)
        with patch.object(cloud,'api',side_effect=missing):
            self.assertTrue(cloud.delete_pod({'id':'p','name':'cryo'}))

    def test_iso_offset_reconciliation_is_accepted(self):
        stamp=time.strftime('%Y-%m-%dT%H:%M:%S+00:00',time.gmtime())
        cloud.check_budget([],self.reconciliation(verified_at=stamp))

    def test_stale_reconciliation_fails_closed(self):
        old=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(time.time()-90000))
        with self.assertRaises(ValueError): cloud.check_budget([],self.reconciliation(verified_at=old))

    def test_cleanup_checks_identity(self):
        with patch.object(cloud,'api',return_value={'name':'other'}) as mocked:
            with self.assertRaises(ValueError): cloud.delete_pod({'id':'p','name':'cryo'})
            mocked.assert_called_once_with('GET','pods/p')

    def test_conflicting_duplicate_receipts_fail_closed(self):
        rec=self.reconciliation()
        for receipts in [
            [{'id':'p','deleted':False,'estimated_gpu_cost_usd':.1},{'id':'p','deleted':True,'estimated_gpu_cost_usd':.1}],
            [{'id':'p','deleted':True,'estimated_gpu_cost_usd':8},{'id':'p','deleted':True,'estimated_gpu_cost_usd':.1}],
        ]:
            for ordered in [receipts,list(reversed(receipts))]:
                with self.assertRaises(ValueError):cloud.check_budget(ordered,rec)

    def test_invalid_costs_never_reduce_budget_reservation(self):
        for cost in [None,-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):
                cloud.check_budget([{'id':'p','deleted':True,'estimated_gpu_cost_usd':cost}],self.reconciliation())
        with self.assertRaises(ValueError):cloud.check_budget([{'id':'p','deleted':True}],self.reconciliation())

if __name__=='__main__': unittest.main()
