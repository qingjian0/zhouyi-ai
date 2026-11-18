import unittest

from prototype.cpg_ei_regularization_dose_response import (
    TRUE_SUPPORT, _aggregate, _score, run_sweep,
)


class TestCpgEiRegularizationDoseResponse(unittest.TestCase):
    def test_score_reports_false_discoveries_and_exact_recovery(self):
        metrics = _score(set(TRUE_SUPPORT), 0.95)
        self.assertEqual(metrics["support_precision"], 1.0)
        self.assertEqual(metrics["support_recall"], 1.0)
        self.assertEqual(metrics["false_discoveries"], 0)
        self.assertTrue(metrics["exact_support_recovery"])

    def test_aggregate_keeps_normalization_conditions_separate(self):
        rows = [
            {"edge_group_l1": 0.003, "normalized_candidate_scores": False,
             "bit_accuracy": 0.9, "support_precision": 0.5,
             "support_recall": 0.5, "active_edges": 6,
             "false_discoveries": 3, "exact_support_recovery": False},
            {"edge_group_l1": 0.003, "normalized_candidate_scores": True,
             "bit_accuracy": 0.91, "support_precision": 0.6,
             "support_recall": 0.6, "active_edges": 6,
             "false_discoveries": 2, "exact_support_recovery": False},
        ]
        summary = _aggregate(rows)
        self.assertEqual(len(summary), 2)
        self.assertEqual(summary[0]["mean_support_recall"], 0.5)
        self.assertEqual(summary[1]["mean_support_recall"], 0.6)

    def test_small_sweep_is_paired_and_deterministic(self):
        kwargs = {
            "seeds": (7,), "penalties": (0.001, 0.03),
            "normalized_modes": (False, True), "samples": 128,
            "epochs_per_round": 5, "rounds": 1,
        }
        first = run_sweep(**kwargs)
        second = run_sweep(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(len(first["records"]), 4)
        self.assertEqual(len(first["summary"]), 4)
        self.assertFalse(first["protocol"]["validation_used_for_selection"])
        self.assertFalse(first["protocol"]["true_support_used_for_selection"])


if __name__ == "__main__":
    unittest.main()
