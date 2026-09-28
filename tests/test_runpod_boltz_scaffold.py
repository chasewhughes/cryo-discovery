import json
import io
import math
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import runpod_boltz_scaffold as launcher
from scripts import runpod_boltz_scaffold_worker as worker


class PanelLifecycleTests(unittest.TestCase):
    def test_frozen_budget_window_and_gpu_cap(self):
        self.assertEqual(launcher.LIFETIME, 10800)
        self.assertEqual(launcher.MARGIN, .30)
        self.assertAlmostEqual(launcher.MAX_RATE * launcher.LIFETIME / 3600 + launcher.MARGIN, 2.70)
        stamp = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
        rec = {'verified_at': stamp, 'all_prior_research_pods_absent': True, 'prior_gpu_reserve_usd': 7.2}
        quote = {'checked_at': stamp, 'quotes': [{'id': launcher.GPU, 'securePrice': .80}]}
        self.assertEqual(launcher.validate_budget(rec, quote), 7.2)
        with self.assertRaises(ValueError):
            launcher.validate_budget({**rec, 'prior_gpu_reserve_usd': 7.31}, quote)
        with self.assertRaises(ValueError):
            launcher.validate_budget(rec, {'checked_at': stamp, 'quotes': [{'id': launcher.GPU, 'securePrice': .81}]})

    def test_pending_intent_is_cumulative_and_resolution_releases_reserve(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); attempt = root/'data/raw/phase16/attempt3'; attempt.mkdir(parents=True)
            (attempt/'intent.json').write_text(json.dumps({'attempt': 3, 'name': 'cryo-old'}))
            with patch.object(launcher, 'ROOT', root), patch.object(launcher, 'OUT', root/'data/phase17'):
                self.assertAlmostEqual(launcher.pending_reserve(), 2.70)
                (root/'data/phase16').mkdir(parents=True)
                (root/'data/phase16/runpod-attempt3-receipt.json').write_text(json.dumps({'name': 'other', 'deleted': True}))
                self.assertAlmostEqual(launcher.pending_reserve(), 2.70)
                (root/'data/phase16/runpod-attempt3-receipt.json').write_text(json.dumps({'name': 'cryo-old', 'deleted': True}))
                self.assertEqual(launcher.pending_reserve(), 0.)
                (root/'data/phase16/runpod-attempt3-receipt.json').unlink()
                (attempt/'intent.json').write_text(json.dumps({'attempt': 3, 'name': 'cryo-old', 'reserved_usd': float('nan')}))
                self.assertAlmostEqual(launcher.pending_reserve(), 2.70)
                (attempt/'intent-reconciliation.json').write_text(json.dumps({'no_matching_pod_at_deadline': True}))
                self.assertEqual(launcher.pending_reserve(), 0.)

    def test_batch_state_blocks_second_unfinished_reservation(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            with patch.object(launcher, 'OUT', out), patch.object(launcher, 'LOCAL', out/'raw'):
                launcher.reserve_batch(1)
                with self.assertRaises(ValueError):
                    launcher.reserve_batch(2)
                launcher.release_batch({'attempt': 1}, {'state': 'failed'})
                self.assertEqual(json.loads((out/'panel-batch-state.json').read_text())['active_attempt'], 1)
                launcher.release_batch({'attempt': 1}, {'state': 'finished', 'deleted': True})
                launcher.reserve_batch(2)

    def test_worker_rejects_oversize_input_archive(self):
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td)/'input.tar.gz'
            with tarfile.open(archive, 'w:gz') as t:
                info = tarfile.TarInfo('large.bin'); info.size = 10_000_001
                # Sparse metadata is enough to exercise the bounded member check.
                t.addfile(info, io.BytesIO(b'x' * 10_000_001))
            with self.assertRaises(ValueError):
                worker.unpack(archive, {'large.bin': '0' * 64})

    def test_worker_requires_single_a6000_with_memory(self):
        info = {'available': True, 'count': 1, 'devices': [{'name': 'NVIDIA GeForce RTX 4090', 'bytes': 24 * 1024**3}]}
        worker.validate_gpu_info(info)
        for bad in ({**info, 'count': 2}, {**info, 'devices': [{'name': 'NVIDIA GeForce RTX 4090', 'bytes': 16 * 1024**3}]}):
            with self.assertRaises(ValueError):
                worker.validate_gpu_info(bad)


if __name__ == '__main__':
    unittest.main()
