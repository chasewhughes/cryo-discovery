import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import reconcile_boltz_compute as reconcile


class PendingIntentTests(unittest.TestCase):
    def test_receipt_excludes_pending_and_unresolved_reserves_default(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); raw=root/'data/raw/phase16/attempt1'; raw.mkdir(parents=True)
            out=root/'data/phase16'; out.mkdir(parents=True)
            (raw/'intent.json').write_text(json.dumps({'attempt':1,'name':'cryo-1'}))
            with patch.object(reconcile,'ROOT',root), patch.object(reconcile,'OUT',out):
                self.assertEqual(reconcile.pending_intents()[0]['reserved_usd'], .9)
                (out/'runpod-attempt1-receipt.json').write_text('{}')
                self.assertEqual(reconcile.pending_intents(), [])

    def test_definitive_resolution_and_curated_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); raw=root/'data/raw/phase16/attempt2'; raw.mkdir(parents=True)
            out=root/'data/phase16'; out.mkdir(parents=True)
            (raw/'intent.json').write_text(json.dumps({'attempt':2,'reserved_usd':float('nan')}))
            (raw/'intent-reconciliation.json').write_text(json.dumps({}))
            curated=out/'attempt3-unresolved-intent.json'; curated.write_text(json.dumps({'attempt':3}))
            with patch.object(reconcile,'ROOT',root), patch.object(reconcile,'OUT',out):
                with self.assertRaises(ValueError): reconcile.pending_intents()
                (raw/'intent-reconciliation.json').write_text(json.dumps({'definitive_rejection':True}))
                self.assertEqual(reconcile.pending_intents()[0]['attempt'],3)
                self.assertEqual(reconcile.pending_intents()[0]['reserved_usd'],.9)


if __name__ == '__main__': unittest.main()
