import unittest

from prototype.e10b_transfer_experiment import run


class E10BTransferExperimentTests(unittest.TestCase):
    def test_renaming_invariance_and_ood_abstention_gates(self):
        result = run(seed=1801, instances_per_template=3)
        self.assertTrue(result["checks"]["consistent_renaming_invariant"])
        self.assertTrue(result["checks"]["schema_shift_all_abstain"])
        self.assertTrue(result["checks"]["value_shift_all_abstain"])
        self.assertTrue(result["checks"]["context_shift_all_abstain"])
        self.assertEqual(
            result["query_only_shift"]["renamed_attribute_schema"]["decision_counts"],
            {"ABSTAIN_OOD_SCHEMA": result["native"]["n"]},
        )
        self.assertEqual(
            result["query_only_shift"]["unseen_categorical_values"]["decision_counts"],
            {"ABSTAIN_OOD_VALUE": result["native"]["n"]},
        )
        self.assertEqual(
            result["query_only_shift"]["unseen_context_values"]["decision_counts"],
            {"ABSTAIN_OOD_VALUE": result["native"]["n"]},
        )
        self.assertIn("support_majority", result["baselines"])
        self.assertIn("deterministic_random", result["baselines"])
        self.assertIn("evaluator_oracle_upper_bound", result["baselines"])


if __name__ == "__main__":
    unittest.main()
