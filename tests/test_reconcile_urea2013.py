import copy, json, unittest
from pathlib import Path
from rdkit import Chem
from scripts.reconcile_urea2013_sources import primary_rows,reconcile
class UreaAuditTests(unittest.TestCase):
    def setUp(self):
        self.acts=json.loads(Path('data/raw/phase20/inventory/CHEMBL2341182-activities.json').read_text())['activities']
    def test_complete_graph_join_and_exclusions(self):
        r=reconcile(self.acts)
        self.assertEqual(r['counts'],{'source_rows':45,'eligible_exact':41,'excluded_records':4})
        self.assertEqual({x['source_compound_number'] for x in r['excluded_records']},{'8d','12g','12h','19b'})
        a=next(x for x in primary_rows() if x['source_compound_number']=='19a')
        m=Chem.MolFromSmiles(a['expected_smiles'])
        self.assertEqual([x.GetProp('_CIPCode') for x in m.GetAtoms() if x.HasProp('_CIPCode')],['S'])
    def test_potency_cannot_rescue_wrong_structure(self):
        rows=copy.deepcopy(self.acts); rows[0]['canonical_smiles']='CCO'
        with self.assertRaises(ValueError):reconcile(rows)
    def test_altered_value_rejected_after_identity_join(self):
        rows=copy.deepcopy(self.acts);rows[0]['standard_value']=float(rows[0]['standard_value'])+1
        with self.assertRaises(ValueError):reconcile(rows)
    def test_duplicate_structural_identity_rejected(self):
        with self.assertRaises(ValueError):reconcile(self.acts+[copy.deepcopy(self.acts[0])])
