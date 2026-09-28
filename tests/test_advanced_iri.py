"""Tests for descriptor identity, nested tuning and reusable kernel models."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

try:
    import joblib
    import numpy as np
    from scripts import advanced_iri as a
except ImportError:
    a = None


@unittest.skipIf(a is None, "Install requirements-iri.txt for advanced IRI tests")
class AdvancedIRITests(unittest.TestCase):
    def test_missing_source_row_does_not_shift_descriptor_identity(self):
        records = [{"name": "First"}, {"name": "Missing"}, {"name": "Last"}]
        X, status = a.join_by_name(records, ["FIRST", "LAST"], np.array([[1., 2.], [8., 9.]]))
        np.testing.assert_array_equal(X[0], [1., 2.])
        self.assertTrue(np.isnan(X[1]).all())
        np.testing.assert_array_equal(X[2], [8., 9.])
        self.assertEqual(status, ["matched", "unmapped", "matched"])

    def test_conflicting_duplicate_names_are_quarantined(self):
        X, status = a.join_by_name([{"name": "compound"}], ["compound", "COMPOUND"], np.array([[1., 2.], [1., 3.]]))
        self.assertEqual(status, ["conflicting_duplicate_name"])
        self.assertTrue(np.isnan(X).all())
        X, status = a.join_by_name([{"name": "compound"}], ["compound", "COMPOUND"], np.array([[1., 2.], [1., 2.]]))
        np.testing.assert_array_equal(X, [[1., 2.]])

    def test_blank_and_literal_nan_names_are_not_identifiers(self):
        X, status = a.join_by_name([{"name": "nan"}, {"name": ""}], ["nan", ""], np.array([[1.], [2.]]))
        self.assertTrue(np.isnan(X).all())
        self.assertEqual(status, ["unmapped", "unmapped"])

    def test_tanimoto_matches_known_overlap(self):
        X = np.array([[1., 0., 1.], [1., 1., 0.]])
        K = a.tanimoto(X, X)
        np.testing.assert_allclose(K, [[1., 1/3], [1/3, 1.]])
        self.assertTrue((np.linalg.eigvalsh(K) >= 0).all())

    def test_outer_labels_cannot_affect_tuning_or_predictions(self):
        smiles = ["CCO", "CCC", "c1ccccc1", "Cc1ccccc1", "c1ccncc1", "C1CCCCC1",
                  "C1CCOC1", "c1ccoc1", "C1CCC1", "c1ccsc1", "C1CCNC1", "c1ncncn1"]
        records = [{"id": str(i), "observed_mgs": float(i * 7), **a.base.structure(s)} for i, s in enumerate(smiles)]
        previous = a.base.evaluate(records, "scaffold")
        X = np.array([r["features"] for r in records])
        features = {"standard_svr": X, "hydration_svr": X.copy(), "fingerprint_krr": (X > X.mean(axis=0)).astype(float)}
        train, test = a.base.make_splits(records, "scaffold")[0]
        altered = [dict(r, observed_mgs=9999. if i in test else r["observed_mgs"]) for i, r in enumerate(records)]
        def small_grid(family):
            return [{"alpha": 1.}] if family == "fingerprint_krr" else [{"C": 10., "gamma": "scale"}]
        with patch.object(a, "configurations", small_grid):
            before = a.evaluate("test", records, features, "scaffold", previous)
            after = a.evaluate("test", altered, features, "scaffold", previous)
        self.assertEqual(before["tuning"][0], after["tuning"][0])
        for i in test:
            self.assertEqual(before["predictions"][i]["predicted_mgs"], after["predictions"][i]["predicted_mgs"])

    def test_kernel_model_serialization_keeps_predictions(self):
        X = np.array([[1., 0.], [0., 1.], [1., 1.]])
        fitted = a.TanimotoRegressor(alpha=.1).fit(X, np.array([5., 30., 20.]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.joblib"
            joblib.dump(fitted, path)
            loaded = joblib.load(path)
            np.testing.assert_array_equal(fitted.predict(X), loaded.predict(X))


if __name__ == "__main__":
    unittest.main()
