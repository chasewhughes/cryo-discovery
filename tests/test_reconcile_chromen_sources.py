import unittest
from scripts.reconcile_chromen_sources import reconcile
class SourceTests(unittest.TestCase):
 def setUp(self):
  self.source=[['Compound_ID','SMILES','ROCK Ⅰ IC50 (um)','ROCK Ⅱ IC50 (um)','PKA IC50 (um)'],['a','CCO','99','0.003','99']]
  self.records=[dict(canonical_smiles='OCC',standard_value='3',standard_relation='=',standard_type='IC50',standard_units='nM',activity_id=1,molecule_chembl_id='CHEMBL1')]
 def test_uses_rock_two_and_canonical_identity(self):
  self.assertEqual(reconcile(self.source,self.records)[0]['corrected_value_nM'],3)
 def test_rejects_unit_disagreement(self):
  self.records[0]['standard_value']='.003'
  with self.assertRaises(ValueError):reconcile(self.source,self.records)
 def test_censored_bound_is_preserved(self):
  self.source[1][3]='>10';self.records[0].update(standard_value='10000',standard_relation='>')
  self.assertEqual(reconcile(self.source,self.records)[0]['corrected_relation'],'>')
 def test_rejects_ambiguous_duplicate(self):
  with self.assertRaises(ValueError):reconcile(self.source,self.records*2)
 def test_rejects_wrong_isoform_header(self):
  self.source[0][3]='ROCK I IC50 (um)'
  with self.assertRaises(ValueError):reconcile(self.source,self.records)
if __name__=='__main__':unittest.main()
