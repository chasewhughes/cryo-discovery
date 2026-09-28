"""Leakage and source-integrity tests for the optional scientific environment."""
import hashlib
from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
    from scripts import benchmark_iri as b
except ImportError:
    b = None


@unittest.skipIf(b is None, "Install requirements-iri.txt for the IRI tests")
class IRIBenchmarkTests(unittest.TestCase):
    def records(self):
        smiles = ["CCO", "CCC", "C[C@H](N)C(=O)O", "C[C@@H](N)C(=O)O",
                  "c1ccccc1", "Cc1ccccc1", "c1ccncc1", "C1CCCCC1",
                  "C1CCOC1", "c1ccoc1", "C1CCC1", "c1ccsc1"]
        return [{"id": str(i), "observed_mgs": float(i * 7), **b.structure(s)}
                for i, s in enumerate(smiles)]

    def test_stereoisomers_group_together_without_losing_identity(self):
        left, right = self.records()[2:4]
        self.assertNotEqual(left["canonical"], right["canonical"])
        self.assertEqual(left["connectivity"], right["connectivity"])
        for grouping in ("scaffold", "connectivity"):
            for train, test in b.make_splits(self.records(), grouping):
                self.assertEqual(2 in test, 3 in test)

    def test_all_acyclic_molecules_stay_in_one_scaffold_fold(self):
        records = self.records()
        for train, test in b.make_splits(records, "scaffold"):
            self.assertIn(len(set(range(4)) & set(test)), (0, 4))

    def test_held_out_labels_do_not_change_training_predictions(self):
        records = self.records()
        train, test = b.make_splits(records, "scaffold")[0]
        altered = [dict(r, observed_mgs=10000. if i in test else r["observed_mgs"])
                   for i, r in enumerate(records)]
        first = b.evaluate(records, "scaffold")["predictions"]
        second = b.evaluate(altered, "scaffold")["predictions"]
        for i in test:
            self.assertEqual(first[i]["predicted_mgs"], second[i]["predicted_mgs"])
            self.assertEqual(first[i]["predicted_mgs"]["median"], np.median([records[j]["observed_mgs"] for j in train]))

    def test_source_hash_rejects_modified_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").write_bytes(b"original")
            manifest = {"files": [{"local_path": "source", "sha256": hashlib.sha256(b"original").hexdigest()}]}
            b.verify_manifest(manifest, root)
            (root / "source").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                b.verify_manifest(manifest, root)

    def test_group_error_interval_does_not_count_rows_as_groups(self):
        y = np.array([0., 0., 0., 0.])
        result = b.paired_group_interval(y, np.ones(4), np.zeros(4), np.array(["A", "A", "A", "B"]))
        self.assertEqual(result["group_count"], 2)
        self.assertEqual(result["percentile_95_interval"], [1., 1.])

    def test_invalid_structure_fails_instead_of_silent_zero_features(self):
        with self.assertRaises(ValueError):
            b.structure("this is not a molecular structure")


if __name__ == "__main__":
    unittest.main()
