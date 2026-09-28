import json, tempfile, unittest
from pathlib import Path
from scripts.boltz_pilot_inference import collect_outputs, EXPECTED
class BoltzPilotTests(unittest.TestCase):
 def test_fixed_controls_and_output_scan(self):
  self.assertEqual(set(EXPECTED), {'CHEMBL4522042.yaml','CHEMBL4540054.yaml'})
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); (p/'x.json').write_text(json.dumps({'affinity_pred_value':2.1,'affinity_probability_binary':.2}))
   self.assertEqual(collect_outputs(p)[0]['data']['affinity_pred_value'],2.1)
 def test_missing_output_is_not_fabricated(self):
  with tempfile.TemporaryDirectory() as d: self.assertEqual(collect_outputs(Path(d)),[])
if __name__=='__main__': unittest.main()
