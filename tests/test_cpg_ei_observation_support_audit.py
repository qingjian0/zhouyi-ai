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

    def test_partial_context_coverage_without_flips_remains_inconclusive(self):
        rows = [
            {"state": [a, b, 0], "target_value": 0}
            for a in (0, 1) for b in (0, 1)
        ]
        report = _support_identifiability_audit(rows, 3)
        self.assertEqual(
            [item["status"] for item in report["variables"]],
            [
                "no_influence_observed_inconclusive",
                "no_influence_observed_inconclusive",
                "unobserved_counterpart",
            ],
        )

    def test_full_context_coverage_can_identify_an_irrelevant_variable(self):
        rows = [
            {"state": [a, b, c], "target_value": a ^ b}
            for a in (0, 1) for b in (0, 1) for c in (0, 1)
        ]
        report = _support_identifiability_audit(rows, 3)
        self.assertEqual(
            report["variables"][2]["status"],
            "observed_no_influence_full_context_coverage",
        )
        self.assertEqual(report["observed_irrelevant_variable_indices"], [2])
        self.assertEqual(report["unresolved_variable_indices"], [])

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
