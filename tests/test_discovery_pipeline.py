import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import discovery_pipeline as pipeline


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.h = copy.deepcopy(pipeline.read(pipeline.REGISTRY)["hypotheses"][0])
        (root/"source.txt").write_text("primary source fixture")
        (root/"code.txt").write_text("code fixture")
        self.h["evidence_refs"] = [{"source_path": "source.txt", "sha256": pipeline.sha(root/"source.txt")}]
        (root/"registry.json").write_text(json.dumps({"hypotheses": [self.h]}))
        self.folder = root/"runs/test-run"
        for name, value in {"ROOT": root, "REGISTRY": root/"registry.json", "RUNS": root/"runs", "CODE": ["code.txt"]}.items():
            p = patch.object(pipeline, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.git = patch.object(pipeline.subprocess, "check_output", return_value="fixture\n")
        self.git.start()
        self.addCleanup(self.git.stop)

    def fake_result(self, plan):
        return ({"hypothesis_id": self.h["id"], "plan_id": "test-run", "plan_hash": pipeline._digest(plan),
                 "result_type": "virtual", "claim_level": "model_prediction", "claims": ["Fixture prediction"],
                 "decision": "fixture", "numerical_checks": {"passed": True}}, {})

    def test_freeze_execute_verify_and_refuse_overwrite(self):
        pipeline.freeze("test-run")
        with self.assertRaises(FileExistsError):
            pipeline.freeze("test-run")
        with patch.object(pipeline, "transport", side_effect=self.fake_result):
            pipeline.run("test-run")
            pipeline.verify("test-run")
            with self.assertRaises(FileExistsError):
                pipeline.run("test-run")
        with (self.folder/"result.json").open("a") as f:
            f.write(" ")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            pipeline.verify("test-run")

    def test_verification_rechecks_code(self):
        pipeline.freeze("test-run")
        with patch.object(pipeline, "transport", side_effect=self.fake_result):
            pipeline.run("test-run")
        (pipeline.ROOT/"code.txt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "changed evidence: code.txt"):
            pipeline.verify("test-run")

    def test_changed_source_or_design_blocks_before_start(self):
        pipeline.freeze("test-run")
        (pipeline.ROOT/"source.txt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "changed evidence"):
            pipeline.run("test-run")
        self.assertFalse((self.folder/"started.json").exists())
        plan = pipeline.read(self.folder/"plan.json")
        plan["design"]["schedules"]["single"][0]["duration_min"] = 9
        (self.folder/"plan.json").write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, "Design or limitations"):
            pipeline.run("test-run")

    def test_failed_execution_cannot_silently_retry(self):
        pipeline.freeze("test-run")
        with patch.object(pipeline, "transport", side_effect=RuntimeError("solver failed")):
            with self.assertRaises(RuntimeError):
                pipeline.run("test-run")
        with self.assertRaises(FileExistsError):
            pipeline.run("test-run")
        self.assertFalse((self.folder/"manifest.json").exists())

    def test_unequal_duration_and_nonfinite_sensitivity_rejected(self):
        h = copy.deepcopy(self.h)
        h["design"]["schedules"]["single"][0]["duration_min"] = 9
        with self.assertRaisesRegex(ValueError, "equal total duration"):
            pipeline.validate_design(h)
        h = copy.deepcopy(self.h)
        h["design"]["sensitivity_b_factors"] = [float("nan")]
        with self.assertRaises(ValueError):
            pipeline.validate_design(h)


if __name__ == "__main__":
    unittest.main()
