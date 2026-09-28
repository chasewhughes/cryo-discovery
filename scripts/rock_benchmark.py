"""Curate a single-assay ROCK2 reference and freeze/evaluate cheap baselines.

No pretrained-model inference or cloud rental occurs here. Prepared Boltz inputs
are a single-sequence smoke-test configuration, not a validated affinity protocol.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import rdFingerprintGenerator
from rdkit.Chem.Scaffolds import MurckoScaffold
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/'data/raw/phase15/rock'
OUT = ROOT/'data/phase15'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value, exclusive=False):
    data = json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x' if exclusive else 'w') as f:
        f.write(data)


def classify(row):
    """Keep assay, endpoint and censoring distinct; never impute an inactive label."""
    if row.get('target_chembl_id') != 'CHEMBL2973' or row.get('assay_chembl_id') != 'CHEMBL4328667':
        return 'different_target_or_assay'
    if row.get('standard_type') != 'IC50' or row.get('standard_units') != 'nM':
        return 'different_endpoint_or_units'
    if row.get('data_validity_comment') or row.get('potential_duplicate'):
        return 'quality_flag'
    try:
        value = float(row['standard_value'])
    except (ValueError, TypeError, KeyError):
        return 'missing_value'
    if not math.isfinite(value) or value <= 0:
        return 'invalid_value'
    if row.get('standard_relation') not in ('=', '>'):
        return 'unsupported_relation'
    return 'exact' if row['standard_relation'] == '=' else 'right_censored'


def curate():
    manifest = read(OUT/'rock-source-manifest.json')
    for ref in manifest['sources']:
        if sha(ROOT/ref['source_path']) != ref['sha256']:
            raise ValueError('Changed source: '+ref['source_path'])
    assay = read(RAW/'assay.json')
    if assay['confidence_score'] != 9 or assay['target_chembl_id'] != 'CHEMBL2973':
        raise ValueError('Unexpected assay target confidence')
    activities = read(RAW/'activities.json')['activities']
    retained, excluded = [], []
    groups = defaultdict(list)
    for raw in activities:
        status = classify(raw)
        base = {'activity_id': raw['activity_id'], 'molecule_id': raw['molecule_chembl_id'],
                'assay_id': raw['assay_chembl_id'], 'status': status,
                'endpoint': raw['standard_type'], 'relation': raw['standard_relation'],
                'value': raw['standard_value'], 'unit': raw['standard_units']}
        if status not in ('exact', 'right_censored'):
            excluded.append(base)
            continue
        mol = Chem.MolFromSmiles(raw['canonical_smiles'])
        if mol is None:
            raise ValueError('Invalid source SMILES')
        base.update({'canonical_smiles': Chem.MolToSmiles(mol, isomericSmiles=True),
                     'scaffold': MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False),
                     'ic50_nM': float(raw['standard_value']),
                     'pIC50': 9-math.log10(float(raw['standard_value'])) if status == 'exact' else None})
        retained.append(base)
        if status == 'exact':
            groups[base['canonical_smiles']].append(base)
    exact = []
    for smiles, rows in sorted(groups.items()):
        exact.append({'molecule_id': min(r['molecule_id'] for r in rows),
                      'activity_ids': [r['activity_id'] for r in rows],
                      'canonical_smiles': smiles, 'scaffold': rows[0]['scaffold'],
                      'pIC50': float(np.median([r['pIC50'] for r in rows])),
                      'replicate_policy': 'Median log potency only for identical stereochemical SMILES in this same assay'})
    ligand = Chem.MolFromSmiles(read(RAW/'J0P.json')['rcsb_chem_comp_descriptor']['SMILES_stereo'])
    ligand_smiles = Chem.MolToSmiles(ligand, isomericSmiles=True)
    anchor = [r for r in retained if r['canonical_smiles'] == ligand_smiles]
    if len(anchor) != 1:
        raise ValueError('Structure ligand must map unambiguously to one assay record')
    result = {'source_manifest': 'data/phase15/rock-source-manifest.json',
              'license': 'ChEMBL-derived table: CC BY-SA 3.0; original measurements DOI10.1021/acs.jmedchem.8b01098; PDB data CC0',
              'target': 'Human ROCK2, CHEMBL2973, UniProt O75116', 'assay': assay,
              'retained_records': retained, 'excluded_records': excluded, 'exact_compounds': exact,
              'counts': {'downloaded': len(activities), 'retained': len(retained), 'exact_unique': len(exact),
                         'scaffolds': len(set(r['scaffold'] for r in exact)),
                         'excluded': len(excluded), 'statuses': dict(Counter(r['status'] for r in retained))},
              'structure_anchor': {'pdb_id': '6ED6', 'ligand_ccd': 'J0P', 'match_rule': 'Exact RDKit canonical isomeric SMILES equality', 'record': anchor[0]},
              'limits': ['Single selected medicinal chemistry paper and assay; not an external prospective test.',
                         'IC50 is an assay-specific inhibition endpoint, not binding Kd or cell viability.',
                         'The deposited 415-residue construct including tags differs from the assay description (residues11-552); preserve this before structural inference.',
                         'ChEMBL assay description mentions both33P-ATP and HTRF; original assay protocol and ATP concentration require reconciliation before quantitative structural calibration.',
                         'Known2018 ligands/structures may overlap pretrained model training data; performance cannot establish out-of-training generalization.']}
    write(OUT/'rock-benchmark.json', result)
    print(result['counts'])


def freeze():
    data = read(OUT/'rock-benchmark.json')
    plan = {'id': 'rock-baseline-001', 'frozen_at': datetime.now(timezone.utc).isoformat(),
            'data_sha256': sha(OUT/'rock-benchmark.json'), 'code_sha256': sha(Path(__file__)),
            'hypothesis': 'A nearest-fingerprint-neighbor baseline improves MAE at least20% over training-mean prediction and achieves Spearman>=0.5 under leave-one-Murcko-scaffold-out evaluation.',
            'endpoint': 'pIC50 = 9-log10(IC50 in nM); exact values only',
            'split': 'Leave every complete achiral Murcko scaffold out; stereochemical variants stay grouped; every eligible exact compound predicted once.',
            'fingerprint': {'radius': 2, 'bits': 2048, 'chirality': True},
            'prediction': 'Most Tanimoto-similar training compound; ties resolved by molecule ID. No tuned hyperparameters.',
            'controls': ['Training-fold mean prediction', 'Preserved right-censored weak compound, excluded from exact-value regression'],
            'criteria': {'minimum_mae_improvement_fraction': .2, 'minimum_spearman': .5},
            'minimum_rows': 20, 'minimum_scaffolds': 5,
            'eligibility': data['counts'], 'claim_level': 'internal_reference_benchmark',
            'novelty_status': 'known_reference', 'limitations': data['limits']}
    write(OUT/'rock-baseline-plan.json', plan, exclusive=True)
    print('Frozen baseline before evaluation')


def neighbor_predictions(rows):
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048, includeChirality=True)
    fps = [generator.GetFingerprint(Chem.MolFromSmiles(r['canonical_smiles'])) for r in rows]
    predictions = []
    for i, row in enumerate(rows):
        train = [j for j, other in enumerate(rows) if other['scaffold'] != row['scaffold']]
        if not train:
            raise ValueError('No independent training scaffold')
        sims = {j: float(DataStructs.TanimotoSimilarity(fps[i], fps[j])) for j in train}
        nearest = min(train, key=lambda j: (-sims[j], rows[j]['molecule_id']))
        predictions.append({'molecule_id': row['molecule_id'], 'scaffold': row['scaffold'],
                            'observed_pIC50': row['pIC50'], 'predicted_pIC50': rows[nearest]['pIC50'],
                            'control_pIC50': float(np.mean([rows[j]['pIC50'] for j in train])),
                            'nearest_training_id': rows[nearest]['molecule_id'],
                            'nearest_training_scaffold': rows[nearest]['scaffold'],
                            'similarity': sims[nearest], 'training_n': len(train)})
    return predictions


def run():
    plan = read(OUT/'rock-baseline-plan.json')
    if plan['data_sha256'] != sha(OUT/'rock-benchmark.json') or plan['code_sha256'] != sha(Path(__file__)):
        raise ValueError('Frozen data or code changed')
    write(OUT/'rock-baseline-started.json', {'started_at': datetime.now(timezone.utc).isoformat(),
                                           'plan_sha256': sha(OUT/'rock-baseline-plan.json')}, exclusive=True)
    data = read(OUT/'rock-benchmark.json')
    if data['counts']['exact_unique'] < plan['minimum_rows'] or data['counts']['scaffolds'] < plan['minimum_scaffolds']:
        raise ValueError('Insufficient benchmark coverage; do not relax frozen eligibility after execution')
    predictions = neighbor_predictions(data['exact_compounds'])
    observed = np.array([r['observed_pIC50'] for r in predictions])
    predicted = np.array([r['predicted_pIC50'] for r in predictions])
    control = np.array([r['control_pIC50'] for r in predictions])
    mae = float(np.mean(np.abs(predicted-observed)))
    control_mae = float(np.mean(np.abs(control-observed)))
    corr = float(spearmanr(observed, predicted).statistic)
    gain = 1-mae/control_mae if control_mae else None
    passed = gain is not None and gain >= .2 and math.isfinite(corr) and corr >= .5
    result = {'completed_at': datetime.now(timezone.utc).isoformat(),
              'plan_sha256': sha(OUT/'rock-baseline-plan.json'), 'rdkit_version': rdBase.rdkitVersion,
              'metrics': {'nearest_neighbor_mae_pIC50': mae, 'training_mean_mae_pIC50': control_mae,
                          'mae_improvement_fraction': gain, 'spearman': corr if math.isfinite(corr) else None},
              'decision': 'supported_in_internal_benchmark' if passed else 'not_supported_in_internal_benchmark',
              'predictions': predictions, 'limitations': plan['limitations']}
    write(OUT/'rock-baseline-result.json', result, exclusive=True)
    print(result['decision'], result['metrics'])


def prepare():
    data = read(OUT/'rock-benchmark.json')
    protein = read(RAW/'6ED6-polymer.json')['entity_poly']['pdbx_seq_one_letter_code_can']
    if not set(protein) <= set('ACDEFGHIKLMNPQRSTVWY'):
        raise ValueError('Unresolved protein sequence')
    records = [data['structure_anchor']['record']] + [r for r in data['retained_records'] if r['status']=='right_censored']
    folder = OUT/'boltz-inputs'
    paths = []
    for r in records:
        # JSON is valid YAML; no external MSA submission in these smoke-test inputs.
        payload = {'version': 1, 'sequences': [
            {'protein': {'id': 'A', 'sequence': protein, 'msa': 'empty'}},
            {'ligand': {'id': 'L', 'smiles': r['canonical_smiles']}}],
            'templates': [{'cif': 'data/raw/phase15/rock/6ED6.cif', 'chain_id': 'A', 'template_id': 'A'}],
            'properties': [{'affinity': {'binder': 'L'}}]}
        p = folder/(r['molecule_id']+'.yaml')
        write(p, payload)
        paths.append({'path': str(p.relative_to(ROOT)), 'sha256': sha(p),
                      'molecule_id': r['molecule_id'], 'role': 'known_bound_ligand' if r['status']=='exact' else 'measured_right_censored_weak_control',
                      'observed_relation': r['relation'], 'observed_IC50_nM': r['ic50_nM']})
    write(OUT/'boltz-input-manifest.json', {
        'status': 'prepared_not_executed_or_Boltz_parser_validated', 'source_dataset_sha256': sha(OUT/'rock-benchmark.json'),
        'template_sha256': sha(RAW/'6ED6.cif'), 'protein_source_sha256': sha(RAW/'6ED6-polymer.json'),
        'protein_length': len(protein), 'inputs': paths,
        'inference_mode': 'Single sequence with protein template; lower-accuracy smoke test, not a validation configuration.',
        'output_conversion': 'Current official documentation defines affinity_pred_value as log10(IC50 in uM), hence pIC50=6-value. Reverify semantics against the pinned model version before evaluating outputs; binder probability is separate.',
        'required_next': ['Pin/install Boltz and validate YAML through its parser', 'Hash downloaded structure and affinity checkpoints',
                          'Reconcile provider spending and reserve a bounded run with automatic cleanup before rental',
                          'Measure runtime and memory on one complex', 'Resolve MSA, assay and construct mismatches before validation'],
        'claim_limit': 'Two selected controls only check execution/ranking direction. They cannot validate performance or novelty.'})
    print('Prepared', len(paths), 'Boltz input drafts; no inference executed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['curate', 'freeze', 'run', 'prepare'])
    args = parser.parse_args()
    {'curate': curate, 'freeze': freeze, 'run': run, 'prepare': prepare}[args.command]()
