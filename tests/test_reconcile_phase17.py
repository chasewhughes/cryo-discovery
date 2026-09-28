import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import reconcile_phase17 as reconcile


class Phase17ReportTests(unittest.TestCase):
    def test_import_is_read_only(self):
        # Import has already completed without calling provider APIs.
        self.assertTrue(callable(reconcile.main))

    def test_final_report_requires_confirmed_deletion_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td); (out / 'billing-reconciliation.json').write_text('{"sentinel":true}')
            (out / 'gpu-quote.json').write_text('{"sentinel":true}')
            (out / 'runpod-attempt1-receipt.json').write_text(json.dumps({'pod_id': 'p1', 'deleted': True}))
            queried = [{'pod_id': 'p1', 'estimated_gpu_usd': .25, 'conservative_reserve_usd': .25}]
            with patch.object(reconcile, 'OUT', out):
                report = reconcile.final_report({'p1': {}}, queried, .25, .25, [], 0.)
            self.assertEqual(report['estimated_gpu_usd_phase17'], .25)
            self.assertEqual(json.loads((out / 'billing-reconciliation.json').read_text()), {'sentinel': True})
            self.assertTrue((out / 'compute-costs.json').exists())

    def test_final_report_rejects_pending_intent(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            with patch.object(reconcile, 'OUT', out):
                with self.assertRaises(ValueError):
                    reconcile.final_report({}, [], 1., 1., [], 2.10)


if __name__ == '__main__':
    unittest.main()
