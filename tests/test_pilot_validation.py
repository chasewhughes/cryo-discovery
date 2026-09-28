import math, unittest
from scripts.validate_pilot import validate

def study(**changes):
    e={"experiment_id":"e1","model":"human iPSC","intervention":"CPA","comparator":None,"formulation":[{"compound":"DMSO","concentration":10,"unit":"% v/v"}],"treatment_stage":["freezing"],"cooling":None,"warming":None,"storage":None,"outcome_name":"recovery","outcome_type":"recovery","timepoint":None,"result":"Recovery was measured.","effect_numeric":None,"effect_unit":None,"sample_size":None,"source_locator":"Table 1","evidence_excerpt":"Recovery was measured."}
    s={"study_id":"doi:10.x/a","doi":"10.x/a","title":"Study","year":2024,"pmcid":None,"source_url":"https://doi.org/10.x/a","source_access":"full_text","raw_source_path":None,"retrieved_at":"2026-09-05","evidence_scope":"ipsc_direct","species":["Homo sapiens"],"cell_types":["human iPSC"],"study_design":"experiment","interventions":["CPA"],"mechanism_axes":["physical_ice"],"experiments":[e],"main_finding":"Finding","limitations":[],"mechanism_claim":"Measured recovery","review_status":"agent_extracted","reviewer":"test"}; s.update(changes); return s

class PilotValidationTest(unittest.TestCase):
    def test_valid(self): self.assertEqual(validate([study()]), [])
    def test_rejects_outcome_duplicate_and_nonfinite(self):
        a=study(); a["experiments"][0]["outcome_type"]="bogus"; a["experiments"][0]["effect_numeric"]=math.nan; a["experiments"][0]["effect_unit"]="%"; b=study(study_id="doi:10.x/b",doi="10.x/a"); errors=validate([a,b]); self.assertTrue(any("outcome_type" in x for x in errors)); self.assertTrue(any("finite" in x for x in errors)); self.assertTrue(any("duplicate doi" in x for x in errors))
    def test_requires_nullable_keys_and_locator(self):
        a=study(); del a["pmcid"]; del a["experiments"][0]["cooling"]; a["experiments"][0]["source_locator"]=""; errors=validate([a]); self.assertTrue(any("pmcid" in x for x in errors)); self.assertTrue(any("cooling" in x for x in errors)); self.assertTrue(any("source_locator" in x for x in errors))
if __name__ == "__main__": unittest.main()
