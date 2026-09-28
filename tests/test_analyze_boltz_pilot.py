import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import scripts.analyze_boltz_pilot as analyzer

class AnalyzeBoltzTests(unittest.TestCase):
 def test_localizes_workspace_runs_paths(self):
  raw=Path('/tmp/attempt1'); self.assertEqual(analyzer.localize(raw,'/workspace/cryo/runs/CHEMBL4522042/complex.cif'),(raw/'runs/CHEMBL4522042/complex.cif').resolve())
 def test_rejects_unmapped_or_traversal_paths(self):
  self.assertIsNone(analyzer.localize(Path('/tmp/a'),'relative/out.cif'))
  self.assertIsNone(analyzer.localize(Path('/tmp/a'),'/workspace/cryo/runs/../secret.cif'))
 def test_incomplete_attempt_uses_independent_fixture(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); (root/'data/phase16').mkdir(parents=True); (root/'data/raw/phase16/attempt1/runs').mkdir(parents=True)
   plan={'id':'fixture-plan','source_sha256':{}}
   pp=root/'data/phase16/pilot-plan-fixture.json'; pp.write_text(json.dumps(plan))
   archive=root/'data/raw/phase16/attempt1/results.tar.gz'; archive.write_bytes(b'fixture')
   receipt={'plan_sha256':hashlib.sha256(pp.read_bytes()).hexdigest(),'deleted':True,'result_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
   (root/'data/phase16/runpod-attempt1-receipt.json').write_text(json.dumps(receipt))
   with patch.object(analyzer,'ROOT',root):
    result=analyzer.check(1,root/'out.json')
   self.assertIsNone(result['directional_ordering_known_pIC50_higher_than_weak_control'])
   self.assertTrue(any('missing summary' in e for e in result['validation_errors']))

 def test_realistic_success_fixture_and_artifact_mutation(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); (root/'data/phase16').mkdir(parents=True); raw=root/'data/raw/phase16/attempt2'; (raw/'runs/cases').mkdir(parents=True)
   plan={'id':'fixture-plan','source_sha256':{'data/phase15/boltz-inputs/CHEMBL4522042.yaml':'a'*64,'data/phase15/boltz-inputs/CHEMBL4540054.yaml':'b'*64}}
   pp=root/'data/phase16/pilot-plan-attempt2.json'; pp.write_text(json.dumps(plan))
   cases=[]
   for name,h,val,prob in [('CHEMBL4522042.yaml','a'*64,2.0,.9),('CHEMBL4540054.yaml','b'*64,4.0,.1)]:
    stem=Path(name).stem; od=f'/workspace/cryo/runs/cases/{stem}'; artifact=raw/'runs/cases'/stem/'confidence.json'; artifact.parent.mkdir(parents=True); artifact.write_text(json.dumps({'affinity_pred_value':val,'affinity_probability_binary':prob,'confidence_score':.8})); struct=raw/'runs/cases'/stem/'pred.cif'; struct.write_text('data_x\n')
    cmd=['boltz','predict','data/phase15/boltz-inputs/'+name,'--out_dir',od,'--cache','/workspace/cryo/cache/boltz','--accelerator','gpu','--devices','1','--recycling_steps','3','--sampling_steps','200','--diffusion_samples','1','--sampling_steps_affinity','200','--diffusion_samples_affinity','5','--num_workers','1','--no_kernels']
    cases.append({'input':'data/phase15/boltz-inputs/'+name,'role':analyzer.EXPECTED[name],'status':'completed','input_sha256':h,'command':cmd,'output_artifacts':[{'path':'/workspace/cryo/runs/cases/'+stem+'/confidence.json','data':{'affinity_pred_value':val,'affinity_probability_binary':prob}}],'structural_files':['/workspace/cryo/runs/cases/'+stem+'/pred.cif'],'affinity_fields':{'affinity_pred_value':val,'affinity_probability_binary':prob},'wall_seconds':1,'gpu_samples':[]})
   summary={'parameters':{'recycling_steps':3,'sampling_steps':200,'diffusion_samples':1,'sampling_steps_affinity':200,'diffusion_samples_affinity':5,'no_kernels':True},'pip_freeze':['boltz==2.2.1','torch==2.8.0+cu128'],'checkpoint_sha256':[{'path':'/workspace/cryo/cache/boltz/boltz2_conf.ckpt','sha256':'c'*64},{'path':'/workspace/cryo/cache/boltz/boltz2_aff.ckpt','sha256':'d'*64}],'cases':cases}
   (raw/'runs/summary.json').write_text(json.dumps(summary)); archive=raw/'results.tar.gz'; archive.write_bytes(b'x'); (root/'data/phase16/runpod-attempt2-receipt.json').write_text(json.dumps({'plan_sha256':hashlib.sha256(pp.read_bytes()).hexdigest(),'deleted':True,'result_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))
   with patch.object(analyzer,'ROOT',root): good=analyzer.check(2,root/'good.json')
   self.assertTrue(good['valid']); self.assertTrue(good['directional_ordering_known_pIC50_higher_than_weak_control'])
   (raw/'runs/cases/CHEMBL4522042/confidence.json').write_text(json.dumps({'affinity_pred_value':9.0,'affinity_probability_binary':.9}))
   with patch.object(analyzer,'ROOT',root): bad=analyzer.check(2,root/'bad.json')
   self.assertFalse(bad['valid']); self.assertTrue(any('incomplete or invalid outputs' in e for e in bad['validation_errors']))

 def test_artifact_values_are_extracted_recursively(self):
  vals=analyzer.affinity_values({'confidence':{'affinity_pred_value':2.1},'x':[{'affinity_probability_binary':.3}]})
  self.assertEqual(vals,{'affinity_pred_value':2.1,'affinity_probability_binary':.3})

if __name__=='__main__': unittest.main()
