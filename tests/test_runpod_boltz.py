from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import runpod_boltz as launcher
from scripts import runpod_boltz_worker as worker


class PilotSafetyTests(unittest.TestCase):
    def test_unresolved_post_retains_full_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            d = p/'attempt3'
            d.mkdir()
            (d/'intent.json').write_text(json.dumps({'attempt': 3}))
            (d/'intent-reconciliation.json').write_text(json.dumps({'no_matching_pods_now': True}))
            with patch.object(launcher, 'LOCAL', p), patch.object(launcher, 'OUT', p/'out'):
                self.assertAlmostEqual(launcher.pending_reserve(), .9)
                (d/'intent-reconciliation.json').write_text(json.dumps({'definitive_rejection': True}))
                self.assertEqual(launcher.pending_reserve(), 0.)

    def test_observed_a6000_memory_with_ecc_is_accepted(self):
        info = {'available': True, 'count': 1, 'devices': [{'name': 'NVIDIA RTX A6000', 'bytes': 47708110848}]}
        worker.validate_gpu_info(info)
        with self.assertRaises(ValueError):
            worker.validate_gpu_info({**info, 'devices': [{'name': 'NVIDIA RTX A6000', 'bytes': 24*1024**3}]})
        with self.assertRaises(ValueError):
            worker.validate_gpu_info({**info, 'count': 2})

    def test_budget_rejects_overrun_stale_or_wrong_quote(self):
        stamp = datetime.now(timezone.utc).isoformat()
        rec = dict(verified_at=stamp, all_prior_research_pods_absent=True, prior_gpu_reserve_usd=4.1)
        quote = dict(checked_at=stamp, quotes=[dict(id=launcher.GPU, securePrice=.53)])
        self.assertEqual(launcher.validate_budget(rec, quote), 4.1)
        for change in [dict(prior_gpu_reserve_usd=9.5), dict(prior_gpu_reserve_usd=float('nan')),
                       dict(all_prior_research_pods_absent=False), dict(verified_at='2020-01-01T00:00:00+00:00')]:
            with self.assertRaises(ValueError):
                launcher.validate_budget({**rec, **change}, quote)
        with self.assertRaises(ValueError):
            launcher.validate_budget(rec, {**quote, 'quotes': [dict(id=launcher.GPU, securePrice=.61)]})

    def test_wrong_pod_name_never_deleted(self):
        with patch.object(launcher, 'api', return_value={'name': 'unrelated'}) as api:
            with self.assertRaises(ValueError):
                launcher.remove({'pod_id': 'test', 'name': 'cryo-test'})
            api.assert_called_once_with('GET', 'pods/test')

    def test_receipt_deletion_is_monotonic(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            state = dict(attempt=1, pod_id='test', name='cryo-test')
            receipt = {**state, 'deleted': True, 'estimated_gpu_cost_usd': .1, 'ended_epoch': 1}
            (p/'runpod-attempt1-receipt.json').write_text(json.dumps(receipt))
            with patch.object(launcher, 'OUT', p), patch.object(launcher, 'remove') as remove:
                result = launcher.finish_locked(state, {'result_archive_sha256': 'a'*64})
                self.assertTrue(result['deleted'])
                self.assertEqual(result['estimated_gpu_cost_usd'], .1)
                remove.assert_not_called()

    def test_archive_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'input.tar.gz'
            with tarfile.open(p, 'w:gz') as t:
                info = tarfile.TarInfo('../escape')
                info.size = 1
                t.addfile(info, io.BytesIO(b'x'))
            with self.assertRaises(ValueError):
                worker.unpack(p, {'../escape': 'a'*64})


if __name__ == '__main__':
    unittest.main()
