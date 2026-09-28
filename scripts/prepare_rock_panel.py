"""Prepare and freeze the retrospective ROCK2 panel before GPU inference."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from rdkit import Chem

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/phase17'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text())
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f: f.write(json.dumps(obj,indent=2,allow_nan=False)+'\n')

def prepare():
    data=read(ROOT/'data/phase15/rock-benchmark.json')
    target=read(OUT/'target-sequence.json')
    msa=ROOT/'data/raw/phase17/msa-assay/rock2-512.a3m'
    assert msa.is_file() and target['length']==542
    entries=[]
    for row in sorted(data['exact_compounds'],key=lambda x:x['molecule_id']):
        mol=Chem.MolFromSmiles(row['canonical_smiles'])
        if mol is None or not 0<mol.GetNumHeavyAtoms()<=128: raise ValueError('Unsupported ligand '+row['molecule_id'])
        path=OUT/'boltz-inputs'/(row['molecule_id']+'.yaml')
        payload={'version':1,'sequences':[
            {'protein':{'id':'A','sequence':target['sequence'],'msa':str(msa.relative_to(ROOT))}},
            {'ligand':{'id':'L','smiles':row['canonical_smiles']}}],
            'templates':[{'cif':'data/raw/phase15/rock/6ED6.cif','chain_id':'A','template_id':'A'}],
            'properties':[{'affinity':{'binder':'L'}}]}
        write(path,payload)
        entries.append({'molecule_id':row['molecule_id'],'path':str(path.relative_to(ROOT)),
                        'sha256':sha(path),'heavy_atoms':mol.GetNumHeavyAtoms()})
    assert len(entries)==43
    write(OUT/'panel-input-manifest.json',{'inputs':entries,'protein_length':542,'msa_rows':512,
          'target_sha256':sha(OUT/'target-sequence.json'),'msa_sha256':sha(msa),
          'template_sha256':sha(ROOT/'data/raw/phase15/rock/6ED6.cif'),
          'ligand_policy':'Source canonical isomeric SMILES unchanged; no potency-based tautomer/protonation search.',
          'construct_policy':'Model human ROCK2 residues 11-552 without assay GST fusion. Use 6ED6 as an unforced partial protein template; no ligand pose constraints.',
          'pilot_reuse_policy':'New assay-range protein and homologous MSA configuration, two new fixed seeds. Prior 415-residue single-sequence pilot outputs remain separate.'})
    print('Prepared 43 inputs; no measurements included in model inputs')

def freeze():
    manifest=read(OUT/'panel-input-manifest.json')
    checkpoint=read(ROOT/'data/phase16/pilot-results.json')['checkpoint_hashes']
    bundle=['scripts/boltz_panel_inference.py','requirements-boltz.txt',
            'data/raw/phase15/rock/6ED6.cif','data/raw/phase17/msa-assay/rock2-512.a3m']+[x['path'] for x in manifest['inputs']]
    source=bundle+['scripts/runpod_boltz_panel.py','scripts/runpod_boltz_panel_worker.py']
    provenance=['scripts/prepare_rock_panel.py','scripts/analyze_rock_panel.py',
        'data/phase15/rock-benchmark.json','data/phase15/rock-baseline-result.json',
        'data/phase17/target-sequence.json','data/phase17/msa-manifest.json',
        'data/phase17/assay-review.json','data/phase17/source-table-audit.json','data/phase17/panel-input-manifest.json']
    data=read(ROOT/'data/phase15/rock-benchmark.json')
    plan={'id':'rock2-boltz-panel-001','frozen_at':datetime.now(timezone.utc).isoformat(),
      'cloud':{'gpu':'NVIDIA RTX A6000','image':'pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime',
               'max_rate_usd_hour':.60,'max_lifetime_seconds':10800,'margin_usd':.30},
      'bundle_files':bundle,'source_sha256':{p:sha(ROOT/p) for p in source},
      'provenance_sha256':{p:sha(ROOT/p) for p in provenance},
      'model_checkpoint_sha256':{Path(x['path']).name:x['sha256'] for x in checkpoint},
      'configuration':{'boltz':'2.2.1','torch':'2.8.0','protein_length':542,'msa_rows':512,
        'template':'6ED6 protein chain A, unforced partial template','seeds':[1701,1702],
        'recycling_steps':3,'sampling_steps':200,'diffusion_samples':1,
        'sampling_steps_affinity':200,'diffusion_samples_affinity':5,'no_kernels':True},
      'evaluation':{'primary_ids':[x['molecule_id'] for x in manifest['inputs']],
        'seeds':[1701,1702],'aggregation':'Arithmetic mean pIC50-equivalent across the two fixed seeds; no selected best seed.',
        'output_conversion':'pIC50-equivalent = 6 - affinity_pred_value; binary probability remains separate.',
        'baseline_source':'data/phase15/rock-baseline-result.json',
        'hypothesis':'The fixed Boltz ensemble improves MAE by at least 20% over the preserved leave-scaffold-out mean baseline and achieves Spearman >=0.5 on all 43 exact compounds.',
        'minimum_mae_improvement_fraction':.2,'minimum_spearman':.5,
        'required_complete_predictions':86,'bootstrap_samples':2000,'bootstrap_seed':1703,
        'bootstrap_unit':'Resample the 13 complete achiral Murcko scaffold clusters with replacement; paired model/baseline predictions remain together. Percentile intervals are descriptive of this series only.',
        'anchor_excluded_sensitivity':'CHEMBL4522042','partial_output_policy':'Any missing/invalid prediction makes the primary conclusion inconclusive. Preserve failures and do not select a successful subset.',
        'model_fitting':'None. Existing baseline folds remain unchanged; no tuning or post-hoc offsets.',
        'censoring':'Exclude the >10000 nM weak control from exact regression and inference in this panel.'},
      'limits':['Retrospective same-paper benchmark; pretrained model overlap and publication/analogue dependence prevent claims of external generalization.',
        '542-residue human ROCK2 sequence matches annotated assay residue range; GST fusion is omitted and the 6ED6 template covers only residues 27-417 with tag context.',
        'Only 11 compound-number mappings independently audited against Table 1; remaining labels use the curated same-assay ChEMBL records.',
        'Two seeds assess limited stochastic sensitivity, not physical or biological replicate uncertainty.',
        'No learned prediction establishes ice inhibition, post-thaw viability/function, selectivity, or a novel CPA.',
        'Known 6ED6 ligand appears among 43 compounds; mandatory anchor-excluded sensitivity does not remove all template/training overlap.'],
      'counts':data['counts'],'reservation_usd':2.10}
    write(OUT/'panel-plan.json',plan)
    print('Frozen panel plan; SHA256 '+sha(OUT/'panel-plan.json'))

def freeze_4090():
    original=OUT/'panel-plan.json'
    plan=read(original)
    plan.update(id='rock2-boltz-panel-001-4090', frozen_at=datetime.now(timezone.utc).isoformat(),
                supersedes_unallocated_plan_sha256=sha(original),
                revision_reason='Two explicit A6000 capacity rejections, no allocated Pod. Use RTX 4090 with unchanged scientific inputs, sampling settings and evaluation criteria; retain both rejected intents.',
                reservation_usd=2.70)
    plan['cloud'].update(gpu='NVIDIA GeForce RTX 4090',max_rate_usd_hour=.80)
    plan['source_sha256']={p:sha(ROOT/p) for p in plan['source_sha256']}
    plan['provenance_sha256']={p:sha(ROOT/p) for p in plan['provenance_sha256']}
    write(OUT/'panel-plan-4090.json',plan)
    print('Frozen RTX 4090 revision; SHA256 '+sha(OUT/'panel-plan-4090.json'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','freeze','freeze-4090']);a=p.parse_args()
    {'prepare':prepare,'freeze':freeze,'freeze-4090':freeze_4090}[a.action]()
