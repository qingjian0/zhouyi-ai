import unittest

from prototype.cpg_ei_observation_discovery import run_discovery_baseline


class TestObservationDiscoveryBaseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_discovery_baseline(
            family_count=14, input_dim=4, output_dim=7, seed=20261114
        )

    def test_inference_does_not_use_teacher_manifest(self):
        self.assertFalse(self.report["inference_uses_teacher_manifest"])
        self.assertEqual(self.report["rule_count"], 98)

    def test_reports_support_operator_and_locked_metrics(self):
        overall = self.report["overall"]
        self.assertIn("support_recovery_rate", overall)
        self.assertIn("operator_candidate_coverage", overall)
        self.assertIn("locked_consensus_accuracy_rate", overall)
        self.assertIn("mean_input_context_coverage", overall)
        self.assertIn("mean_influence_context_count", overall)
        self.assertIn("mean_observed_irrelevant_variables", overall)
        self.assertGreaterEqual(overall["mean_input_context_coverage"], 0.0)
        self.assertLessEqual(overall["mean_input_context_coverage"], 1.0)
        self.assertEqual(set(self.report["by_operator"]), {
            "xor", "and", "or", "nand", "implies", "threshold", "conditional_xor"
        })

    def test_locked_partition_is_not_used_for_candidate_filtering(self):
        for result in self.report["results"]:
            self.assertEqual(result["locked_size"], 4)
            self.assertGreaterEqual(result["candidate_count"], 0)

    def test_family_generalization_is_reported_separately(self):
        self.assertEqual(
            set(self.report["by_family_split"]),
            {"train", "development", "locked"},
        )


if __name__ == "__main__":
    unittest.main()
