import unittest

from prototype.e02h_boolean_rules import (
    admissible_target_tables, run_episode,
)


class E02HBooleanRuleTests(unittest.TestCase):
    def test_target_generator_excludes_affine_and_pairwise_easy_rules(self):
        tables = admissible_target_tables()
        self.assertGreater(len(tables), 50)

    def test_unknown_boolean_rule_members_and_table_are_recovered(self):
        result = run_episode(seed=23)
        self.assertTrue(result["member_recovered"])
        self.assertTrue(result["truth_table_recovered"])
        self.assertTrue(result["created"])
        self.assertGreater(result["test_accuracy"], 0.9)

    def test_nonmultiplicative_rule_beats_pairwise_baseline(self):
        result = run_episode(seed=37)
        self.assertGreater(result["gate_gain"], 0.05)
        self.assertGreater(result["gate_accuracy"], 0.9)
        self.assertGreater(
            result["test_accuracy"], result["pairwise_test_accuracy"]
        )

    def test_locked_test_data_is_reported_after_gate(self):
        result = run_episode(seed=59)
        self.assertIn("test_accuracy", result)
        self.assertIn("target_truth_table_for_audit_only", result)
        self.assertIn("counterexample_count", result)


if __name__ == "__main__":
    unittest.main()
