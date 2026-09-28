import unittest
from scripts.analyze_combination_tables import additive_interaction, percentage_check


class CombinationInterpretationTests(unittest.TestCase):
    def test_beating_each_component_need_not_be_supra_additive(self):
        self.assertEqual(additive_interaction(60, 80, 80, 90), -10)

    def test_rounding_and_aggregation_discrepancy_are_distinct(self):
        self.assertFalse(percentage_check(78.05, 224, 287)['needs_aggregation_clarification'])
        self.assertTrue(percentage_check(83.90, 73, 85)['needs_aggregation_clarification'])
        with self.assertRaises(ValueError): percentage_check(0, 0, 0)


if __name__ == '__main__': unittest.main()
