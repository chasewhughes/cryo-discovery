import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import analyze_matched_hydration as analyzer
from scripts import verify_matched_hydration as verifier


class ResultLocationTests(unittest.TestCase):
    ids = ['leu-NPT-20261011','leu-NPT-20261012','leu-NPT-20261013','ile-NPT-20261021','ile-NPT-20261022','ile-NPT-20261023']

    def test_valid_mixed_attempt_map(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); locations={}
            for i, jid in enumerate(self.ids):
                attempt='runpod-attempt2' if i < 3 else 'runpod-attempt3'
                p=root/'data/raw/phase13'/attempt/jid/'runs'/jid; p.mkdir(parents=True); (p/'result.json').write_text('{}')
                locations[jid]=f'{attempt}/{jid}/runs/{jid}'
            mp=root/'map.json'; mp.write_text(json.dumps(locations)); plan={'jobs':[{'id':j} for j in self.ids]}
            with patch.object(analyzer,'ROOT',root): self.assertEqual(set(analyzer.resolve_locations(plan,mp)),set(self.ids))
            with patch.object(verifier,'ROOT',root): self.assertEqual(set(verifier.resolve_locations(plan,mp)),set(self.ids))

    def test_rejects_missing_duplicate_or_wrong_attempt_path(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); plan={'jobs':[{'id':j} for j in self.ids]}; mp=root/'map.json'
            bad={j:f'runpod-attempt2/{j}/runs/{j}' for j in self.ids}; bad.pop(self.ids[-1]); mp.write_text(json.dumps(bad))
            with patch.object(analyzer,'ROOT',root), self.assertRaises(ValueError): analyzer.resolve_locations(plan,mp)
            bad={j:f'runpod-other/{j}/runs/{j}' for j in self.ids}; mp.write_text(json.dumps(bad))
            with patch.object(verifier,'ROOT',root), self.assertRaises(ValueError): verifier.resolve_locations(plan,mp)


if __name__ == '__main__': unittest.main()
