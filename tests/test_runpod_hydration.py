"""Lifecycle guards tested without credentials or network calls."""
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from scripts import runpod_hydration as cloud


class PodDeletionTests(unittest.TestCase):
    def test_reserves_full_runtime_before_new_rental(self):
        cloud.check_budget([{'deleted':True,'estimated_gpu_cost_usd':.06}])
        with self.assertRaises(ValueError):
            cloud.check_budget([{'deleted':True,'estimated_gpu_cost_usd':1.8}])
        with self.assertRaises(ValueError):
            cloud.check_budget([{'deleted':False,'estimated_gpu_cost_usd':.06}])

    def test_refuses_different_pod_name(self):
        with patch.object(cloud,'api',return_value={'name':'unrelated-user-pod'}) as api:
            with self.assertRaises(ValueError):cloud.delete_pod({'id':'pilot','name':'cryo-pilot'})
            api.assert_called_once_with('GET','pods/pilot')

    def test_checks_deletion_with_followup(self):
        missing=HTTPError('https://rest.runpod.io/v1/pods/pilot',404,'Not Found',{},None)
        with patch.object(cloud,'api',side_effect=[{'name':'cryo-pilot'},None,missing]) as api:
            self.assertTrue(cloud.delete_pod({'id':'pilot','name':'cryo-pilot'}))
            self.assertEqual([c.args[0] for c in api.call_args_list],['GET','DELETE','GET'])

    def test_does_not_claim_pending_deletion_is_confirmed(self):
        with patch.object(cloud,'api',side_effect=[{'name':'cryo-pilot'},None,{'name':'cryo-pilot'}]):
            self.assertFalse(cloud.delete_pod({'id':'pilot','name':'cryo-pilot'}))


if __name__=='__main__':unittest.main()
