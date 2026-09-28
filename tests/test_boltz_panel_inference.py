import json, tempfile, unittest
from pathlib import Path
from scripts.boltz_panel_inference import json_affinity, inventory, validate_seed_outputs
class PanelTests(unittest.TestCase):
 def test_recursive_affinity_inventory(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); (p/'x.json').write_text(json.dumps({'confidence':{'affinity_pred_value':2.0,'affinity_probability_binary':.4}})); (p/'x.cif').write_text('data_x')
   self.assertEqual(json_affinity(p/'x.json')['affinity_pred_value'],2.0); self.assertEqual(len(inventory(p)),2)
 def test_seed_validation_requires_every_compound(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); inputs=[]
   for i in range(43):
    p=root/f'CHEMBL{i:04d}.yaml'; p.write_text('x'); inputs.append(p)
    o=root/f'pred/CHEMBL{i:04d}'; o.mkdir(parents=True); (o/f'affinity_CHEMBL{i:04d}.json').write_text(json.dumps({'affinity_pred_value':2.0,'affinity_probability_binary':.5})); (o/f'CHEMBL{i:04d}_model_0.cif').write_text('data_x')
   self.assertTrue(validate_seed_outputs(inputs,root)['all_expected_outputs_valid'])
   (root/'pred/CHEMBL0007/affinity_CHEMBL0007.json').write_text(json.dumps({'affinity_pred_value':2.0,'affinity_probability_binary':1.5}))
   self.assertFalse(validate_seed_outputs(inputs,root)['all_expected_outputs_valid'])
 def test_inventory_hashes_and_relative_paths(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); (p/'a.json').write_text('{}'); row=inventory(p)[0]; self.assertEqual(row['path'],'a.json'); self.assertEqual(len(row['sha256']),64)
if __name__=='__main__':unittest.main()
