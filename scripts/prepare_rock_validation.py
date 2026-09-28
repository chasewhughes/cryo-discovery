"""Curate a separate assay and freeze a label-independent split and transfer evaluation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator
from rdkit.Chem.Scaffolds import MurckoScaffold

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/phase20'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f: f.write(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def identity(smiles):
    m=Chem.MolFromSmiles(smiles)
    if m is None or not 0<m.GetNumHeavyAtoms()<=128 or len(Chem.GetMolFrags(m))!=1: raise ValueError('Unsupported ligand')
    return Chem.MolToSmiles(m,isomericSmiles=True), Chem.MolToSmiles(m,isomericSmiles=False), m

def split_rows(rows):
    groups={}
    for r in rows: groups.setdefault(r['scaffold'],[]).append(r['molecule_id'])
    ordered=sorted(groups,key=lambda s:hashlib.sha256(('cryo-phase19-split-1900:'+s).encode()).hexdigest())
    cal=[]
    for s in ordered:
        if len(cal)>=math.ceil(len(rows)/3): break
        cal.extend(groups[s])
    test=sorted(set(r['molecule_id'] for r in rows)-set(cal))
    if len(cal)<6 or len(test)<10 or len(set(groups)-{r['scaffold'] for r in rows if r['molecule_id'] in cal})<2:
        raise ValueError('Frozen label-independent partition too small; report ineligible, do not tune against outcomes')
    return {'calibration_ids':sorted(cal),'test_ids':test,'method':'Sort achiral Murcko scaffold strings by SHA256(cryo-phase19-split-1900: + scaffold), assign whole groups to calibration until at least ceil(n/3) compounds; remaining groups held out. No potency or prediction stratification.', 'scaffold_count':len(groups)}

def prepare(assay):
    raw=ROOT/f'data/raw/phase20/inventory/{assay}-activities.json'
    records=read(raw)['activities']; old=read(ROOT/'data/phase15/rock-benchmark.json')['exact_compounds']
    prior_external=read(ROOT/'data/phase18/external-dataset.json')['exact_compounds']
    overlap_rows=old+prior_external
    reconciled=read(OUT/'source-table-reconciliation.json')
    if reconciled['assay_id'] != assay: raise ValueError('Source reconciliation assay mismatch')
    overrides={r['activity_id']:r for r in reconciled['reconciled_rows']} if reconciled else {}
    audited_exclusions={r['activity_id']:r['reason'] for r in reconciled['excluded_records']} if reconciled else {}
    old_ids={r['molecule_id'] for r in overlap_rows}; old_struct={identity(r['canonical_smiles'])[0] for r in overlap_rows}; old_achiral={identity(r['canonical_smiles'])[1] for r in overlap_rows}
    included={}; excluded=[]
    for r in records:
        original=dict(r)
        correction=overrides.get(r['activity_id'])
        if reconciled and correction is None:
            excluded.append({'activity_id':r['activity_id'],'molecule_id':r['molecule_chembl_id'],'reason':audited_exclusions[r['activity_id']]});continue
        if correction:
            if not correction['identity_verified'] or correction['canonical_smiles']!=r['canonical_smiles'] or correction['original_value_nM']!=float(r['standard_value']): raise ValueError('Source reconciliation identity/value mismatch')
            r=dict(r,standard_value=correction['corrected_value_nM'],standard_relation=correction['corrected_relation'],data_validity_comment=None)
        reason=None
        if r['assay_chembl_id']!=assay: reason='different assay'
        elif r['standard_type']!='IC50': reason='different endpoint'
        elif r['standard_relation']!='=': reason='censored/non-exact'
        elif r['standard_units']!='nM' or r['standard_value'] is None: reason='unsupported units/missing value'
        elif r.get('data_validity_comment'): reason='source validity flag: '+r['data_validity_comment']
        if reason:
            excluded.append({'activity_id':r['activity_id'],'molecule_id':r['molecule_chembl_id'],'reason':reason});continue
        value=float(r['standard_value'])
        if not math.isfinite(value) or not 0<value<=10000: raise ValueError('Unqualified potency range; needs source audit')
        sm,achiral,mol=identity(r['canonical_smiles'])
        if r['molecule_chembl_id'] in old_ids or sm in old_struct or achiral in old_achiral:
            excluded.append({'activity_id':r['activity_id'],'molecule_id':r['molecule_chembl_id'],'reason':'Phase17/18 identity/achiral structure overlap'});continue
        entry={'molecule_id':r['molecule_chembl_id'],'canonical_smiles':r['canonical_smiles'],'rdkit_isomeric_smiles':sm,'achiral_smiles':achiral,
               'scaffold':MurckoScaffold.MurckoScaffoldSmiles(mol=mol),'observed_nM':value,'observed_pIC50':9-math.log10(value),
               'activity_ids':[r['activity_id']],'document_chembl_id':r['document_chembl_id'],'heavy_atoms':mol.GetNumHeavyAtoms()}
        entry['original_standard_value_nM']=original['standard_value']
        entry['original_validity_comment']=original.get('data_validity_comment')
        if correction:entry['source_compound_number']=correction['source_compound_number']
        if sm in included:
            prev=included[sm]
            if prev['observed_nM']!=value: raise ValueError('Conflicting duplicate measurements require source adjudication')
            prev['activity_ids'].append(r['activity_id'])
        else: included[sm]=entry
    rows=sorted(included.values(),key=lambda r:r['molecule_id'])
    if len(rows)<20: raise ValueError('Need at least20 qualified exact compounds')
    partition=split_rows(rows)
    gen=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048)
    old=sorted(old,key=lambda r:r['molecule_id']); oldfp=[gen.GetFingerprint(Chem.MolFromSmiles(r['canonical_smiles'])) for r in old]
    for r in rows:
        sim=DataStructs.BulkTanimotoSimilarity(gen.GetFingerprint(Chem.MolFromSmiles(r['canonical_smiles'])),oldfp); i=int(np.argmax(sim))
        r['source_nearest_neighbor_id']=old[i]['molecule_id'];r['source_nearest_tanimoto']=sim[i]
    source=read(ROOT/'data/phase17/panel-results.json')['panel_predictions']
    constants={'source_mean_pIC50':float(np.mean([r['observed_pIC50'] for r in source])),
               'source_median_residual_offset_pIC50':float(np.median([r['observed_pIC50']-r['panel_mean_pIC50'] for r in source])),
               'fit_policy':'Mean baseline and additive median-residual correction fitted only on all43 Phase17 compounds, before external model outputs. No slope fitting or hyperparameter selection.'}
    dataset={'assay_id':assay,'raw_path':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw),'source':'ChEMBL API snapshot, CC BY-SA3.0; primary assay audit is separate',
             'records_downloaded':len(records),'exact_compounds':rows,'exclusions':excluded,'split':partition,'source_constants':constants,
             'overlap_policy':'Exclude Phase17 and Phase18 molecule IDs, canonical isomeric identity and achiral identity. Preserve analogue similarity; no claim of pretrained-data independence.',
             'duplicate_policy':'Collapse exact structural duplicates only if values agree, otherwise require source adjudication.',
             'domain_policy':'Exact IC50<=10000nM only; no censored bounds treated as observed concentrations.'}
    write(OUT/'validation-dataset.json',dataset)
    target=read(ROOT/'data/phase17/target-sequence.json'); msa='data/raw/phase17/msa-assay/rock2-512.a3m'; entries=[]
    for r in rows:
        p=OUT/'boltz-inputs'/(r['molecule_id']+'.yaml')
        write(p,{'version':1,'sequences':[{'protein':{'id':'A','sequence':target['sequence'],'msa':msa}},{'ligand':{'id':'L','smiles':r['canonical_smiles']}}],
                 'templates':[{'cif':'data/raw/phase15/rock/6ED6.cif','chain_id':'A','template_id':'A'}],'properties':[{'affinity':{'binder':'L'}}]})
        entries.append({'molecule_id':r['molecule_id'],'path':str(p.relative_to(ROOT)),'sha256':sha(p)})
    write(OUT/'input-manifest.json',{'inputs':entries,'protein_length':542,'msa_rows':512,'configuration_policy':'Unchanged Phase17 sequence, MSA and partial template; external assay construct may differ, see assay audit.'})
    write(OUT/'inference-config.json',{'id':'rock2-validation-001','panel_ids':[r['molecule_id'] for r in rows],'seeds':[2001,2002]})
    print(json.dumps({'included':len(rows),'excluded_records':len(excluded),'calibration_n':len(partition['calibration_ids']),'heldout_n':len(partition['test_ids'])}))

def freeze():
    manifest=read(OUT/'input-manifest.json'); dataset=read(OUT/'validation-dataset.json'); audit=read(OUT/'eligibility-decision.json')
    if audit.get('eligible') is not True or audit['assay_id']!=dataset['assay_id']: raise ValueError('No matching audited eligibility decision')
    bundle=['scripts/boltz_validation_inference.py','requirements-boltz.txt','data/phase20/inference-config.json','data/raw/phase15/rock/6ED6.cif','data/raw/phase17/msa-assay/rock2-512.a3m']+[r['path'] for r in manifest['inputs']]
    sources=bundle+['scripts/runpod_boltz_validation.py','scripts/runpod_boltz_validation_worker.py']
    provenance=['scripts/prepare_rock_validation.py','scripts/analyze_rock_validation.py','data/phase20/validation-dataset.json','data/phase20/input-manifest.json','data/phase20/eligibility-decision.json','data/phase17/panel-results.json','data/phase15/rock-benchmark.json','data/phase18/external-dataset.json','data/phase20/selection-policy.json']+audit['review_paths']
    provenance+=audit['source_paths']
    prior=read(ROOT/'data/phase17/panel-plan-4090.json')
    plan={'id':'rock2-validation-001','frozen_at':datetime.now(timezone.utc).isoformat(),'cloud':prior['cloud'],'reservation_usd':2.7,
          'bundle_files':bundle,'source_sha256':{p:sha(ROOT/p) for p in sources},'provenance_sha256':{p:sha(ROOT/p) for p in provenance},
          'model_checkpoint_sha256':prior['model_checkpoint_sha256'],'configuration':dict(prior['configuration'],seeds=[2001,2002]),
          'evaluation':{'primary_ids':[r['molecule_id'] for r in dataset['exact_compounds']],'seeds':[2001,2002],
            'required_complete_predictions':2*len(dataset['exact_compounds']),'dataset_path':'data/phase20/validation-dataset.json',
            'primary_hypothesis':'Uncalibrated two-seed mean reduces MAE at least20% versus Phase17 source mean and Spearman>=0.5 across all eligible external compounds.',
            'minimum_mae_improvement_fraction':.2,'minimum_spearman':.5,
            'calibration':'Report raw, source-only median-residual offset and external calibration-subset median-residual offset on the scaffold-disjoint heldout subset. No slope/scale optimization, no test-label fitting, no best-method selection.',
            'calibration_gate':{'maximum_heldout_mae_pIC50':.5,'maximum_absolute_heldout_bias_pIC50':.25,'minimum_mae_improvement_vs_calibration_mean':.2,'minimum_spearman':.5,'require_no_worse_than_raw_mae':True},
            'screening_gate':'Both primary transfer and heldout external calibration criteria must pass for provisional prioritization; known-series retrospective data cannot establish novelty, pretrained-data independence or biological efficacy.',
            'diagnostics':'Report signed mean error, MAE, RMSE, Pearson/Spearman, observed-on-predicted OLS intercept/slope as diagnostic only, fraction within0.5/1pIC50, largest errors and nearest-source similarity.',
            'bootstrap_samples':2000,'bootstrap_seed':2003,'bootstrap_unit':'Paired scaffold-cluster resampling separately within each fixed evaluation set, descriptive intervals conditional on fitted offsets; calibration-fit uncertainty not included.',
            'partial_output_policy':'Any missing/invalid output makes primary and calibration conclusions inconclusive; no successful subset selection.'},
          'limits':['Separate publication/assay and no exact/achiral structure overlap with Phase17 or Phase18, but pretrained-model training overlap is unknown.',
                    'Assay-condition and construct transfer, not matched laboratory simulation. No explicit ATP, GST, substrate or luciferase/HTRF modeling.',
                    'Calibration is a scalar correction of model output, not improved molecular physics; two seeds are not physical replicates.',
                    'Small scaffold-disjoint test subset yields limited precision. Eligibility and split chosen before external outputs; labels were accessible for audit, so not a blinded benchmark.',
                    'No novel candidates screened and no conclusion about cryoprotection, cell viability/function, toxicity or selectivity.']}
    write(OUT/'validation-plan.json',plan);print('Frozen '+sha(OUT/'validation-plan.json'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','freeze']);p.add_argument('--assay');a=p.parse_args()
    if a.action=='prepare':
        if not a.assay:p.error('--assay required')
        prepare(a.assay)
    else:freeze()
