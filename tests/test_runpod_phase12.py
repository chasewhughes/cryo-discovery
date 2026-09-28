import json
import tempfile
import time
import unittest
from pathlib import Path

from scripts import runpod_phase12 as cloud


class Phase12Guards(unittest.TestCase):
    def rec(self, **extra):
        d = {'prior_gpu_reserve_usd': 1.05,
             'verified_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
             'all_prior_research_pods_absent': True}
        d.update(extra)
        f = tempfile.NamedTemporaryFile(mode='w', delete=False)
        json.dump(d, f); f.close()
        return Path(f.name)

    def test_four_job_reservation_and_prior_cost(self):
        cloud.check_budget([{'id': 'old', 'deleted': True,
                             'estimated_gpu_cost_usd': 1.0}], self.rec())
        with self.assertRaises(ValueError):
            cloud.check_budget([{'id': 'old', 'deleted': True,
                                 'estimated_gpu_cost_usd': 8.0}], self.rec())

    def test_conflicting_receipt_and_unconfirmed_cleanup_fail_closed(self):
        with self.assertRaises(ValueError):
            cloud.check_budget([{'id': 'p', 'deleted': True,
                                 'estimated_gpu_cost_usd': .1},
                                {'id': 'p', 'deleted': False,
                                 'estimated_gpu_cost_usd': .1}], self.rec())
        with self.assertRaises(ValueError):
            cloud.check_budget([{'id': 'p', 'deleted': False,
                                 'estimated_gpu_cost_usd': .1}], self.rec())

    def test_stale_or_missing_reconciliation_fails(self):
        old = self.rec(verified_at='2020-01-01T00:00:00Z')
        with self.assertRaises(ValueError): cloud.check_budget([], old)
        with self.assertRaises(ValueError): cloud.check_budget([], old.with_name('missing-reconciliation'))

    def test_parent_archive_excludes_trajectory_and_worker_checks_hashes(self):
        import io,tarfile,hashlib
        from scripts.runpod_phase12_worker import unpack_parent
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);parent=p/'parent';parent.mkdir()
            names=('system.xml','integrator.xml','final-state.xml','topology-final-box.pdb','result.json')
            for name in names:(parent/name).write_text('source '+name)
            (parent/'trajectory.npz').write_bytes(b'large excluded data')
            packed=cloud.archive_parent(parent)
            with tarfile.open(fileobj=io.BytesIO(packed)) as archive:self.assertEqual(set(archive.getnames()),set(names))
            archive_path=p/'input.tar.gz';archive_path.write_bytes(packed)
            hashes={n:hashlib.sha256((parent/n).read_bytes()).hexdigest() for n in names}
            unpack_parent(archive_path,p/'output',hashes)
            hashes['system.xml']='wrong'
            with self.assertRaises(ValueError):unpack_parent(archive_path,p/'bad',hashes)

    def test_nonfinite_missing_reserve_and_naive_time_rejected(self):
        for value in [float('nan'),float('inf'),-1]:
            with self.assertRaises(ValueError):cloud.check_budget([],self.rec(prior_gpu_reserve_usd=value))
        with self.assertRaises(ValueError):cloud.check_budget([],self.rec(verified_at=time.strftime('%Y-%m-%dT%H:%M:%S',time.gmtime())))

    def test_cleanup_verifies_identity_and_absence(self):
        from unittest.mock import patch
        from urllib.error import HTTPError
        s={'pod_id':'p','name':'ours'}
        with patch.object(cloud,'api',return_value={'name':'someone-else'}) as api:
            with self.assertRaises(ValueError):cloud.delete_pod(s)
            self.assertEqual(api.call_count,1)
        with patch.object(cloud,'api',side_effect=[{'name':'ours'},None,HTTPError('',404,'absent',{},None)]):
            self.assertTrue(cloud.delete_pod(s))

    def test_result_archive_rejects_traversal_and_links(self):
        import tarfile,io
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bad.tar.gz'
            for name,kind in [('runs/../../escape',tarfile.REGTYPE),('runs/link',tarfile.SYMTYPE)]:
                with tarfile.open(p,'w:gz') as a:
                    m=tarfile.TarInfo(name);m.type=kind;m.linkname='/etc/passwd'
                    a.addfile(m,io.BytesIO())
                with self.assertRaises(ValueError):cloud.extract_results(p,Path(td)/'out')

    def test_watchdog_does_not_kill_unrelated_reused_pid(self):
        from unittest.mock import patch,Mock
        with patch.object(cloud.subprocess,'run',return_value=Mock(stdout='unrelated program')),patch.object(cloud.os,'kill') as kill:
            self.assertFalse(cloud.stop_watchdog({'watchdog_pid':987654}))
            kill.assert_not_called()

    def test_overrate_second_pod_is_recorded_and_both_pods_cleaned(self):
        from unittest.mock import patch,Mock
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'scripts').mkdir();(root/'scripts/runpod_phase12_worker.py').write_text('worker')
            plan=root/'plan.json';plan.write_text('{}')
            jobs={j:{'id':j} for j in cloud.JOB_IDS};bundles={j:(b'archive',{}) for j in cloud.JOB_IDS}
            pods={};created=[];deleted=[]
            def api(method,endpoint,payload=None):
                if method=='POST':
                    ident=str(len(created)+1);created.append(ident)
                    pods[ident]={'id':ident,'name':payload['name'],'costPerHr':.74 if ident=='1' else 2.0}
                    return pods[ident]
                ident=endpoint.split('/')[-1]
                if method=='DELETE':deleted.append(ident);pods.pop(ident);return None
                if ident not in pods:raise HTTPError('',404,'absent',{},None)
                return pods[ident]
            with patch.multiple(cloud,ROOT=root,LOCAL=root/'raw',PLAN=plan),patch.object(cloud,'prepare',return_value=(jobs,bundles,{})),patch.object(cloud,'api',side_effect=api),patch.object(cloud,'key',return_value='test-secret'),patch.object(cloud.subprocess,'Popen',return_value=Mock(pid=123)),patch.object(cloud,'stop_watchdog',return_value=True):
                with self.assertRaisesRegex(ValueError,'rate'):cloud.launch()
                self.assertEqual(created,['1','2']);self.assertEqual(deleted,['1','2'])
                self.assertEqual(len(json.loads((root/'raw/batch-state.json').read_text())),2)
                receipts=list((root/'data/phase12').glob('*receipt.json'))
                self.assertEqual(len(receipts),2)
                self.assertTrue(all(json.loads(p.read_text())['deleted'] for p in receipts))

if __name__ == '__main__':unittest.main()
