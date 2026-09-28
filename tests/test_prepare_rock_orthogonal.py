import unittest
from scripts.prepare_rock_orthogonal import split_rows
class SplitTests(unittest.TestCase):
 def test_single_scaffold_cannot_leak_to_test(self):
  with self.assertRaises(ValueError):split_rows([{'molecule_id':str(i),'scaffold':'same'} for i in range(30)])
 def test_split_ignores_labels_and_input_order(self):
  rows=[{'molecule_id':str(i),'scaffold':str(i),'observed_pIC50':i} for i in range(30)]
  first=split_rows(rows)
  for r in rows:r['observed_pIC50']=-r['observed_pIC50']
  self.assertEqual(first,split_rows(list(reversed(rows))))
if __name__=='__main__':unittest.main()
