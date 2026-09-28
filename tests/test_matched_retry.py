import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from scripts import runpod_phase13_retry as c

class RetryReservation(unittest.TestCase):
    def test_live_reservations_and_failed_only_selection(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);states={j:{'job_id':j,'pod_id':j,'name':'cryo-'+j,'created_epoch':1,'deadline_epoch':3601,'cost_per_hour':.74} for j in c.JOB_IDS}
            old=root/'data/raw/phase13/runpod-attempt2/batch-state.json';old.parent.mkdir(parents=True);old.write_text(json.dumps(states))
            rec=root/'data/phase13/billing-reconciliation.json';rec.parent.mkdir(parents=True);rec.write_text(json.dumps({'prior_gpu_reserve_usd':2.31}))
            receipts=[{'pod_id':j,'deleted':True,'estimated_gpu_cost_usd':.1,'worker_status':{'state':'failed'}} for j in c.RETRY_IDS]
            live=[{'id':j,'name':'cryo-'+j,'costPerHr':.74} for j in c.JOB_IDS if j not in c.RETRY_IDS]
            with patch.object(c,'ROOT',root),patch.object(c,'receipts',return_value=receipts),patch.object(c,'api',return_value=live):
                c.check_retry_reservation()
                result=json.loads((rec.parent/'retry-reservation.json').read_text())
                self.assertEqual(len(result['outstanding_pod_ids']),3)
                self.assertAlmostEqual(result['conservative_total_bound_usd'],7.71)
                live.append({'id':'untracked','name':'cryo-unknown','costPerHr':.74})
                with self.assertRaisesRegex(ValueError,'Unreserved'):c.check_retry_reservation()
                live.pop();receipts[0]['worker_status']['current']=c.RETRY_IDS[0]
                with self.assertRaisesRegex(ValueError,'pre-simulation'):c.check_retry_reservation()
    def test_full_six_reserve_still_enforces_ten_dollars(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'rec.json';p.write_text(json.dumps({'prior_gpu_reserve_usd':4.61,'verified_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'all_prior_research_pods_absent':True}))
            with self.assertRaisesRegex(ValueError,'budget'):c.check_budget([],p)
