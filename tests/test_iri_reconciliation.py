import unittest

try:
    from scripts import reconcile_iri_data as r
except ImportError:
    r = None


@unittest.skipIf(r is None, "Install requirements-iri.txt for reconciliation tests")
class ReconciliationTests(unittest.TestCase):
    def test_dichloro_exception_does_not_change_monochloro_compound(self):
        dichloro = "(2s)-2-amino-3-(3,5-dichloro-4-hydroxyphenyl)propanoic acid"
        monochloro = "(2s)-2-amino-3-(3-chloro-4-hydroxyphenyl)propanoic acid"
        result = r.resolve_condition(dichloro, "predict", "20")
        self.assertEqual(result["resolved_compound_mM"], 10.)
        self.assertEqual(result["figure4_compound_number"], 8)
        self.assertTrue(result["source_conflict"])
        self.assertEqual(r.resolve_condition(monochloro, "predict", "20")["resolved_compound_mM"], 20.)

    def test_exception_cannot_silently_apply_to_changed_source(self):
        name = next(iter(r.EXCEPTIONS))
        with self.assertRaises(ValueError):
            r.resolve_condition(name, "train/test", "20")
        with self.assertRaises(ValueError):
            r.resolve_condition(name, "predict", "5")

    def test_overlap_normalization_groups_stereoisomers(self):
        self.assertEqual(r.normalized_parent("C[C@H](N)C(=O)O"), r.normalized_parent("C[C@@H](N)C(=O)O"))

    def test_overlap_normalization_handles_salt_without_asserting_assay_state(self):
        self.assertEqual(r.normalized_parent("C[NH3+].[Cl-]"), r.normalized_parent("CN"))
        with self.assertRaises(ValueError):
            r.normalized_parent("invalid structure")


if __name__ == "__main__":
    unittest.main()
