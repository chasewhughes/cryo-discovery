import copy
import hashlib
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import analyze_rock_validation as analyzer


def fixture_dataset(offset=0.0, poor=False):
    rows = []
    cal, test = set(), set()
    for i in range(20):
        ident = f'CHEMBL{i:07d}'
        is_cal = i < 10
        (cal if is_cal else test).add(ident)
        prediction = 6.0 if poor else 7.0 + (i % 3) * .1
        observed = prediction + (offset if is_cal else 0.5)
        rows.append({'molecule_id': ident, 'scaffold': f"{'cal' if is_cal else 'test'}-{i}",
                     'split': 'calibration' if is_cal else 'test',
                     'observed_pIC50': observed, 'panel_mean_pIC50': prediction,
                     'seed_absolute_difference_pIC50': .1})
    dataset = {'exact_compounds': rows, 'split': {'calibration_ids': sorted(cal), 'test_ids': sorted(test)},
               'source_constants': {'source_median_residual_offset_pIC50': .2, 'source_mean_pIC50': 7.0}}
    ev = {'minimum_mae_improvement_fraction': 0.0, 'minimum_spearman': -1.0,
          'calibration_gate': {'maximum_heldout_mae_pIC50': 10.0,
                               'maximum_absolute_heldout_bias_pIC50': 10.0,
                               'minimum_mae_improvement_vs_calibration_mean': -1.0,
                               'minimum_spearman': -1.0},
          'bootstrap_samples': 3, 'bootstrap_seed': 17}
    return rows, dataset, ev


class ValidationRockAnalysisTests(unittest.TestCase):
    def test_dynamic_twenty_id_fixture_has_disjoint_scaffolds(self):
        rows, dataset, _ = fixture_dataset()
        self.assertGreaterEqual(len({r['molecule_id'] for r in rows}), 20)
        cal = set(dataset['split']['calibration_ids']); test = set(dataset['split']['test_ids'])
        self.assertFalse(cal & test)
        self.assertFalse({r['scaffold'] for r in rows if r['molecule_id'] in cal} &
                         {r['scaffold'] for r in rows if r['molecule_id'] in test})

    def test_calibration_offset_does_not_depend_on_test_labels(self):
        rows, dataset, ev = fixture_dataset(offset=.4)
        first = analyzer.analyze(copy.deepcopy(rows), copy.deepcopy(dataset), ev)
        changed = copy.deepcopy(rows)
        for row in changed:
            if row['split'] == 'test':
                row['observed_pIC50'] += 5
        second = analyzer.analyze(changed, copy.deepcopy(dataset), ev)
        self.assertEqual(first['calibration_fit']['offset_pIC50'], second['calibration_fit']['offset_pIC50'])

    def test_poor_predictions_do_not_pass_primary_transfer(self):
        rows, dataset, ev = fixture_dataset(poor=True)
        result = analyzer.analyze(rows, dataset, ev)
        self.assertFalse(result['primary_transfer_passed'])
        self.assertEqual(result['screening_decision'], 'novel_screening_not_qualified')

    def test_constant_scores_have_undefined_spearman(self):
        result = analyzer.score([1, 2, 3], [4, 4, 4], [2, 2, 2])
        self.assertIsNone(result['spearman'])

    def test_missing_artifact_is_rejected_safely(self):
        with self.assertRaises(ValueError):
            analyzer.safe_artifact(Path('/tmp/rock-validation-fixture'), '../escape.json')


class ValidationRockCheckIntegrationTests(unittest.TestCase):
    def build(self, root, missing=False, leakage=False):
        phase = root / 'data/phase20'; raw = root / 'data/raw/phase20/attempt1'
        (raw / 'runs').mkdir(parents=True); (phase / 'boltz-inputs').mkdir(parents=True)
        ids = [f'CHEMBL{i:04d}' for i in range(20)]
        source_hashes = {}
        for ident in ids:
            path = phase / 'boltz-inputs' / f'{ident}.yaml'; path.write_text('yaml')
            source_hashes[f'data/phase20/boltz-inputs/{ident}.yaml'] = hashlib.sha256(path.read_bytes()).hexdigest()
        exact = []
        for i, ident in enumerate(ids):
            scaffold = 'shared' if leakage else ('cal-' if i < 10 else 'test-') + str(i)
            exact.append({'molecule_id': ident, 'observed_pIC50': 5.0 + i, 'scaffold': scaffold})
        dataset = {'exact_compounds': exact,
                   'split': {'calibration_ids': ids[:10], 'test_ids': ids[10:]},
                   'source_constants': {'source_median_residual_offset_pIC50': .1, 'source_mean_pIC50': 14.5}}
        (phase / 'validation-dataset.json').write_text(json.dumps(dataset))
        evaluation = {'primary_ids': ids, 'seeds': [2001, 2002], 'dataset_path': 'data/phase20/validation-dataset.json',
                      'required_complete_predictions': 40, 'bootstrap_samples': 3, 'bootstrap_seed': 2003, 'minimum_mae_improvement_fraction': -.1,
                      'minimum_spearman': .5, 'calibration_gate': {'maximum_heldout_mae_pIC50': 2.,
                      'maximum_absolute_heldout_bias_pIC50': 2., 'minimum_mae_improvement_vs_calibration_mean': -.1,
                      'minimum_spearman': .5}}
        plan = {'id': 'validation-fixture', 'source_sha256': source_hashes, 'provenance_sha256': {},
                'model_checkpoint_sha256': {'aff.ckpt': 'a' * 64, 'conf.ckpt': 'b' * 64},
                'evaluation': evaluation, 'limits': []}
        plan_path = phase / 'validation-plan.json'; plan_path.write_text(json.dumps(plan))
        for seed in evaluation['seeds']:
            seedroot = raw / 'runs' / f'seed-{seed}'; seedroot.mkdir(parents=True)
            compounds = []
            for i, ident in enumerate(ids):
                pred = 5.0 + i - .2
                affinity = seedroot / f'{ident}.json'; affinity.write_text(json.dumps({'affinity_pred_value': 6 - pred, 'affinity_probability_binary': .5}))
                cif = seedroot / f'{ident}.cif'; cif.write_text('data_' + ident)
                compounds.append({'id': ident, 'affinity_json': [{'path': affinity.name, 'sha256': analyzer.sha(affinity)}],
                                  'structure_cif': [{'path': cif.name, 'sha256': analyzer.sha(cif)}],
                                  'affinity_fields': {'affinity_pred_value': 6 - pred, 'affinity_probability_binary': .5}})
            if missing and seed == 2002:
                (seedroot / f'{ids[-1]}.json').unlink()
            command = ['boltz', 'predict', 'data/phase20/boltz-inputs', '--out_dir', f'/workspace/cryo/runs/seed-{seed}',
                       '--cache', '/workspace/cryo/cache/boltz', '--accelerator', 'gpu', '--devices', '1',
                       '--recycling_steps', '3', '--sampling_steps', '200', '--diffusion_samples', '1',
                       '--sampling_steps_affinity', '200', '--diffusion_samples_affinity', '5', '--max_msa_seqs', '512',
                       '--num_workers', '1', '--no_kernels', '--seed', str(seed)]
            (raw / 'runs' / f'seed-{seed}-components.json').write_text('[]')
            if missing and seed == 2002:
                compounds[-1]['affinity_json'][0]['sha256'] = '0' * 64
            # Keep the fixture summary valid for all artifacts except the deliberate missing file.
            records = locals().get('seed_records', [])
            records.append({'seed': seed, 'status': 'completed', 'returncode': 0, 'command': command,
                            'output_validation': {'compound_outputs': compounds, 'all_expected_outputs_valid': not (missing and seed == 2002)}, 'gpu_samples': [], 'wall_seconds': 1})
            seed_records = records
        summary = {'plan_id': plan['id'], 'input_hashes': {Path(k).name: v for k, v in source_hashes.items()},
                   'pip_freeze': ['boltz==2.2.1', 'torch==2.8.0+cu128'],
                   'checkpoint_hashes': [{'path': '/workspace/cryo/cache/aff.ckpt', 'sha256': 'a' * 64},
                                        {'path': '/workspace/cryo/cache/conf.ckpt', 'sha256': 'b' * 64}], 'seeds': seed_records}
        summary_path = raw / 'runs/summary.json'; summary_path.write_text(json.dumps(summary))
        archive = raw / 'results.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar: tar.add(raw / 'runs', arcname='runs')
        (phase / 'runpod-attempt1-receipt.json').write_text(json.dumps({'deleted': True,
            'plan_sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest(),
            'result_archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}))

    def test_check_success_missing_artifact_and_scaffold_leakage(self):
        for missing, leakage, expected in [(False, False, 'provisional_prioritization_gate_passed'),
                                           (True, False, 'inconclusive'), (False, True, 'inconclusive')]:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td); self.build(root, missing, leakage)
                with patch.object(analyzer, 'ROOT', root):
                    result = analyzer.check(1, root / 'result.json')
                self.assertEqual(result['verdict'], expected)


if __name__ == '__main__':
    unittest.main()
