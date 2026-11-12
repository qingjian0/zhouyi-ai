import unittest

from prototype.cpg_ei_observation_discovery import _support_identifiability_audit


class ObservationSupportIdentifiabilityAuditTests(unittest.TestCase):
    def test_missing_counterparts_are_reported_as_unobserved_not_irrelevant(self):
        rows = [
            {"state": [0, 0], "target_value": 0},
            {"state": [1, 0], "target_value": 1},
        ]
        report = _support_identifiability_audit(rows, 2)
        self.assertEqual(report["variables"][0]["status"], "observed_influence")
        self.assertEqual(report["variables"][1]["status"], "unobserved_counterpart")
        self.assertEqual(report["unresolved_variable_indices"], [1])

    def test_matched_pairs_without_flips_remain_inconclusive(self):
        rows = [
            {"state": [0, 0], "target_value": 0},
            {"state": [1, 0], "target_value": 0},
            {"state": [0, 1], "target_value": 0},
            {"state": [1, 1], "target_value": 0},
        ]
        report = _support_identifiability_audit(rows, 2)
        self.assertEqual(
            [item["status"] for item in report["variables"]],
            ["no_influence_observed_inconclusive"] * 2,
        )

    def test_full_truth_table_has_matched_pair_coverage(self):
        rows = [
            {"state": [a, b, c], "target_value": a ^ b ^ c}
            for a in (0, 1) for b in (0, 1) for c in (0, 1)
        ]
        report = _support_identifiability_audit(rows, 3)
        self.assertEqual(report["matched_pair_total"], 12)
        self.assertTrue(all(
            item["status"] == "observed_influence"
            for item in report["variables"]
        ))


if __name__ == "__main__":
    unittest.main()
