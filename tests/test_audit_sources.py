import tempfile,unittest,json
from pathlib import Path
from scripts.audit_sources import norm,load_records,raw_text,index_metadata
class AuditTextTest(unittest.TestCase):
    def test_normalizes_entities_and_whitespace(self): self.assertEqual(norm(" A &amp; quoted\n text "),"A & quoted text")
    def test_failed_refresh_preserves_metadata_and_nested_success_keeps_abstract(self):
        with tempfile.TemporaryDirectory() as d:
            original=Path(d)/"original.json"; refresh=Path(d)/"refresh.json"
            original.write_text(json.dumps({"resultList":{"result":[{"doi":"10.x/a","title":"A","abstractText":"Original"}]}}))
            refresh.write_text(json.dumps({"records":[{"doi":"10.x/a","metadata_status":"failure"},{"doi":"10.x/b","metadata_status":"ok","metadata":{"doi":"10.x/b","title":"B","abstractText":"Nested"}}]}))
            result=index_metadata([original,refresh])
            self.assertEqual(result['10.x/a']['abstractText'],'Original')
            self.assertEqual(result['10.x/b']['abstractText'],'Nested')
    def test_europe_pmc_result_list_structure(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"m.json"; p.write_text(json.dumps({"resultList":{"result":[{"doi":"10.x/a"}]}})); self.assertEqual(load_records(p)[0]["doi"],"10.x/a")
    def test_html_source_text(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"source.html"; p.write_text("<html><body>Exact&nbsp; excerpt <b>here</b></body></html>"); self.assertIn("Exact excerpt here",raw_text(p))
if __name__=="__main__": unittest.main()
