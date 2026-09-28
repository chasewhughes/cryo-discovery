import copy
import unittest
from scripts.analyze_rock_imap_diagnostic import ROOT,read,assemble,metrics
class IMAPTests(unittest.TestCase):
 def setUp(self):
  self.source=read(ROOT/'data/phase19/morwick-imap-source.json');self.recon=read(ROOT/'data/phase18/source-table-reconciliation.json');self.pred=read(ROOT/'data/phase18/external-results.json')
 def test_censoring_and_ambiguous_identity_excluded(self):
  rows,excluded=assemble(self.source,self.recon,self.pred)
  self.assertEqual(len(rows),13);self.assertEqual(len(excluded),5)
  self.assertFalse({30,31,32,33,37}&{r['source_compound_number'] for r in rows})
  self.assertEqual({r['source_compound_number'] for r in rows}|{r['source_compound_number'] for r in excluded},{r['source_compound_number'] for r in self.source['rows']})
 def test_source_label_mismatch_fails(self):
  self.source['rows'][0]['luciferase_nM']*=1000
  with self.assertRaises(ValueError):assemble(self.source,self.recon,self.pred)
 def test_invalid_prior_predictions_fail(self):
  self.pred['archive_hash_verified']=False
  with self.assertRaises(ValueError):assemble(self.source,self.recon,self.pred)
 def test_constant_offset_cannot_improve_rank(self):
  a=metrics([1,2,3],[3,1,2]);b=metrics([1,2,3],[4,2,3]);self.assertEqual(a['spearman'],b['spearman'])
if __name__=='__main__':unittest.main()
