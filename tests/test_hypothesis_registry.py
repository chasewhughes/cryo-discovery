import hashlib
import unittest

from scripts.hypothesis_registry import validate_conclusion, validate_hypothesis, validate_plan


SHA = "a" * 64


def hypothesis():
    return {"id": "water-iri-01", "statement": "The adapter changes water occupancy",
            "model": "ridge", "domain": "matched 22mM assay", "endpoints": ["MGS"],
            "controls": ["vehicle", "untreated"], "acceptance_criteria": {"mae": 20.0},
            "evidence_refs": [{"source_path": "data/raw/source.csv", "sha256": SHA}],
            "status": "prospective_hypothesis"}


def plan():
    h = hypothesis()
    return {**h, "plan_id": "plan-water-01", "hypothesis_id": h["id"],
            "hypothesis_hash": hashlib.sha256(__import__("json").dumps(h, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "frozen_at": "2026-09-06T12:00:00Z"}


class RegistryTests(unittest.TestCase):
    def test_missing_controls(self):
        h = hypothesis(); h.pop("controls")
        self.assertTrue(any("controls" in e for e in validate_hypothesis(h)))

    def test_nonfinite_criteria(self):
        h = hypothesis(); h["acceptance_criteria"] = {"mae": float("nan")}
        self.assertTrue(any("non-finite" in e for e in validate_hypothesis(h)))

    def test_wrong_plan_hash(self):
        p = plan(); p["hypothesis_hash"] = SHA
        self.assertTrue(any("hypothesis_hash" in e for e in validate_plan(p, hypothesis())))

    def test_virtual_claim_escalation(self):
        p = plan()
        result = {"hypothesis_id": p["hypothesis_id"], "plan_id": p["plan_id"],
                  "plan_hash": hashlib.sha256(__import__("json").dumps(p, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                  "result_type": "virtual", "claim_level": "model_prediction",
                  "claims": ["experimental efficacy established", "synergy"]}
        self.assertTrue(any("virtual results" in e for e in validate_conclusion(result, p)))

    def test_non_dict_inputs_and_numeric_sha(self):
        self.assertTrue(validate_hypothesis(None))
        self.assertTrue(validate_plan(None, None))
        h = hypothesis(); h["evidence_refs"][0]["sha256"] = 42
        self.assertTrue(any("sha256" in e for e in validate_hypothesis(h)))

    def test_virtual_claim_level_and_finite_metrics(self):
        p = plan()
        result = {"hypothesis_id": p["hypothesis_id"], "plan_id": p["plan_id"],
                  "plan_hash": hashlib.sha256(__import__("json").dumps(p, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                  "result_type": "virtual", "claim_level": "established_novelty",
                  "claims": ["prediction"], "metrics": {"mae": float("inf")}}
        errors = validate_conclusion(result, p)
        self.assertTrue(any("claim_level" in e or "novelty" in e for e in errors))
        self.assertTrue(any("non-finite" in e for e in errors))

    def test_measurement_requires_hashed_reference(self):
        p = plan()
        result = {"hypothesis_id": p["hypothesis_id"], "plan_id": p["plan_id"],
                  "plan_hash": hashlib.sha256(__import__("json").dumps(p, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                  "result_type": "measurement", "claim_level": "experimental_observation",
                  "claims": ["observed"], "measurement_refs": [{"source_path": "x"}]}
        self.assertTrue(any("measurement_refs" in e for e in validate_conclusion(result, p)))


if __name__ == "__main__":
    unittest.main()
