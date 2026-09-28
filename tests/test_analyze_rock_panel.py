import json, unittest, tempfile
from pathlib import Path
from scripts.analyze_rock_panel import metrics, bootstrap, spearman
class RockPanelTests(unittest.TestCase):
 def rows(self):
  return [{'observed_pIC50':x,'panel_mean_pIC50':x+e,'panel_seed_pIC50':[x+e,x+e], 'control_pIC50':x+1,'baseline_predicted_pIC50':x+.1,'scaffold':s} for x,e,s in [(5,.2,'a'),(6,-.1,'a'),(7,.3,'b'),(8,-.2,'b')]]
 def test_metrics_uses_mean_control_and_retains_nn(self):
  m=metrics(self.rows()); self.assertAlmostEqual(m['mean_control_mae_pIC50'],1.0); self.assertAlmostEqual(m['neighbor_baseline_mae_pIC50'],.1); self.assertEqual(m['n'],4)
 def test_constant_correlation_is_none(self):
  rows=self.rows()
  for r in rows:r['panel_mean_pIC50']=6
  self.assertIsNone(metrics(rows)['spearman'])
 def test_bootstrap_reproducible_and_cluster_count(self):
  a=bootstrap(self.rows(),n=50,seed=1703); b=bootstrap(self.rows(),n=50,seed=1703)
  self.assertEqual(a,b); self.assertEqual(a['clusters'],2); self.assertEqual(a['resamples'],50)
 def test_spearman_monotonic(self): self.assertAlmostEqual(spearman([1,2,3],[3,6,9]),1.0)
if __name__=='__main__':unittest.main()

class RockPanelIntegrationTests(unittest.TestCase):
 def build(self, root, poor=False, mutate=False):
  import hashlib, tarfile
  phase=root/'data/phase17'; raw=root/'data/raw/phase17/attempt1'; (phase).mkdir(parents=True); (raw/'runs').mkdir(parents=True)
  ids=[f'CHEMBL{i:04d}' for i in range(43)]; inp=root/'data/phase17/boltz-inputs'; inp.mkdir()
  hashes={}
  for i,ident in enumerate(ids):
   p=inp/(ident+'.yaml'); p.write_text('x'); hashes['data/phase17/boltz-inputs/'+ident+'.yaml']=hashlib.sha256(p.read_bytes()).hexdigest()
  baseline=[]
  for i,ident in enumerate(ids): baseline.append({'molecule_id':ident,'observed_pIC50':float(i+5),'control_pIC50':float(i+6),'predicted_pIC50':float(i+6.5),'scaffold':'s'+str(i%3)})
  bp=root/'data/phase15'; bp.mkdir(parents=True); (bp/'rock-baseline-result.json').write_text(json.dumps({'predictions':baseline}))
  plan={'id':'fixture','source_sha256':hashes,'provenance_sha256':{},'model_checkpoint_sha256':{'boltz2_aff.ckpt':'a'*64,'boltz2_conf.ckpt':'b'*64},'evaluation':{'primary_ids':ids,'seeds':[1701,1702],'baseline_source':'data/phase15/rock-baseline-result.json','anchor_excluded_sensitivity':ids[0],'bootstrap_samples':20,'bootstrap_seed':1703,'minimum_mae_improvement_fraction':.5,'minimum_spearman':.5},'limits':[]}
  pp=phase/'panel-plan.json'; pp.write_text(json.dumps(plan));
  seedrecs=[]
  for seed in (1701,1702):
   sroot=raw/'runs'/f'seed-{seed}'; sroot.mkdir(parents=True); comps=[]
   for i,ident in enumerate(ids):
    y=float(i+5); pred=(y if not poor else 5.0); val=6-pred; prob=.5; ar=sroot/f'{ident}.json'; ar.write_text(json.dumps({'affinity_pred_value':val,'affinity_probability_binary':prob})); cif=sroot/f'{ident}_model_0.cif'; cif.write_text('data_'+ident)
    comps.append({'id':ident,'affinity_json':[{'path':f'{ident}.json','sha256':hashlib.sha256(ar.read_bytes()).hexdigest()}],'structure_cif':[{'path':f'{ident}_model_0.cif','sha256':hashlib.sha256(cif.read_bytes()).hexdigest()}],'affinity_fields':{'affinity_pred_value':val,'affinity_probability_binary':prob},'valid':True})
   cmd=['boltz','predict','data/phase17/boltz-inputs','--out_dir',f'/workspace/cryo/runs/seed-{seed}','--cache','/workspace/cryo/cache/boltz','--accelerator','gpu','--devices','1','--recycling_steps','3','--sampling_steps','200','--diffusion_samples','1','--sampling_steps_affinity','200','--diffusion_samples_affinity','5','--max_msa_seqs','512','--num_workers','1','--no_kernels','--seed',str(seed)]
   seedrecs.append({'seed':seed,'status':'completed','returncode':0,'command':cmd,'output_validation':{'compound_outputs':comps,'all_expected_outputs_valid':True},'gpu_samples':[],'wall_seconds':1})
  summary={'input_hashes':{Path(k).name:v for k,v in hashes.items()},'pip_freeze':['boltz==2.2.1','torch==2.8.0+cu128'],'checkpoint_hashes':[{'path':'/workspace/cryo/cache/boltz/boltz2_aff.ckpt','sha256':'a'*64},{'path':'/workspace/cryo/cache/boltz/boltz2_conf.ckpt','sha256':'b'*64}],'seeds':seedrecs}
  sf=raw/'runs/summary.json'; sf.write_text(json.dumps(summary)); archive=raw/'results.tar.gz'
  with tarfile.open(archive,'w:gz') as tar: tar.add(raw/'runs',arcname='runs')
  (phase/'runpod-attempt1-receipt.json').write_text(json.dumps({'deleted':True,'plan_sha256':hashlib.sha256(pp.read_bytes()).hexdigest(),'result_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))
  if mutate: (raw/'runs/seed-1701'/f'{ids[0]}.json').write_text(json.dumps({'affinity_pred_value':99,'affinity_probability_binary':.5}))
  return ids
 def test_check_full_and_poor_and_mutated(self):
  from unittest.mock import patch
  import scripts.analyze_rock_panel as a
  for poor,mutate,expected in [(False,False,'supported_internal_benchmark'),(True,False,'not_supported_internal_benchmark'),(False,True,'inconclusive')]:
   with tempfile.TemporaryDirectory() as d:
    root=Path(d); self.build(root,poor,mutate)
    with patch.object(a,'ROOT',root): result=a.check(1,root/'result.json')
    self.assertEqual(result['verdict'],expected)
