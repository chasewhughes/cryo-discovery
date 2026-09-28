import json, tempfile, unittest
from pathlib import Path
from scripts.boltz_external_inference import validate_seed_outputs, SEEDS
class ExternalRunnerTests(unittest.TestCase):
 def test_external_seeds_and_plan_driven_outputs(self):
  self.assertEqual(SEEDS,(1801,1802))
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); inputs=[]
   for i in range(3):
    p=root/f'EXT{i}.yaml'; p.write_text('version: 1'); inputs.append(p)
    out=root/'pred'/f'EXT{i}'; out.mkdir(parents=True); (out/f'affinity_EXT{i}.json').write_text(json.dumps({'affinity_pred_value':2.,'affinity_probability_binary':.5})); (out/f'EXT{i}_model_0.cif').write_text('data_x')
   v=validate_seed_outputs(inputs,root); self.assertTrue(v['all_expected_outputs_valid']); self.assertEqual(v['predicted_affinity_count'],3)
 def test_duplicate_affinity_fails(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); p=root/'X.yaml'; p.write_text('x'); out=root/'x'; (out/'a').mkdir(parents=True); (out/'b').mkdir(parents=True)
   for sub in ('a','b'): (out/sub/'affinity_X.json').write_text(json.dumps({'affinity_pred_value':2,'affinity_probability_binary':.5}))
   (out/'X_model_0.cif').write_text('data_x'); self.assertFalse(validate_seed_outputs([p],root)['all_expected_outputs_valid'])
if __name__=='__main__':unittest.main()
