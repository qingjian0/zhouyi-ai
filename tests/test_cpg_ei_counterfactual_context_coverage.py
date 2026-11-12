import unittest

from prototype.cpg_ei_observation_discovery import _support_identifiability_audit


class CounterfactualContextCoverageTests(unittest.TestCase):
    def test_inactive_context_does_not_prove_conditional_operand_irrelevant(self):
        # x0 XOR x1 is active only when x2 == 1. The observed training
        # partition contains every x0/x1 combination only at x2 == 0.
        rows = [
            {"state": [x0, x1, 0], "target_value": 0}
            for x0 in (0, 1) for x1 in (0, 1)
        ]
        report = _support_identifiability_audit(rows, 3)
        x0 = report["variables"][0]
        self.assertEqual(x0["matched_pair_count"], 2)
        self.assertEqual(x0["influence_flip_count"], 0)
        self.assertEqual(x0["observed_context_count"], 2)
        self.assertEqual(x0["context_space_size"], 4)
        self.assertEqual(x0["context_coverage"], 0.5)
        self.assertEqual(x0["status"], "no_influence_observed_inconclusive")

    def test_active_context_exposes_conditional_influence(self):
        rows = [
            {"state": [x0, x1, 1], "target_value": x0 ^ x1}
            for x0 in (0, 1) for x1 in (0, 1)
        ]
        report = _support_identifiability_audit(rows, 3)
        x0 = report["variables"][0]
        self.assertEqual(x0["influence_flip_count"], 2)
        self.assertEqual(x0["influence_context_count"], 2)
        self.assertEqual(x0["status"], "observed_influence")

    def test_context_coverage_is_reported_per_variable(self):
        rows = [
            {"state": [a, b, c], "target_value": a ^ b}
            for a in (0, 1) for b in (0, 1) for c in (0, 1)
        ]
        report = _support_identifiability_audit(rows, 3)
        self.assertTrue(all(item["context_coverage"] == 1.0
                            for item in report["variables"]))


if __name__ == "__main__":
    unittest.main()
