import unittest
from prototype.e10a_object_disjoint import build_object_disjoint_task
from prototype.e10a_mechanism_controls import run_mechanism_controls


class MechanismControlsTests(unittest.TestCase):
    def test_three_arms_share_query_order_and_report_metrics(self):
        support, query, truth = build_object_disjoint_task(1201)
        result = run_mechanism_controls(support, query, truth)
        self.assertEqual(set(result["arms"]), {
            "frozen", "online_candidate_elimination", "batch_refit"
        })
        for metrics in result["arms"].values():
            self.assertEqual(metrics["observations"], len(query["observations"]))
            self.assertGreaterEqual(metrics["coverage"], 0.0)
            self.assertLessEqual(metrics["coverage"], 1.0)
        self.assertEqual(
            result["arms"]["online_candidate_elimination"]["revision_events"],
            len(query["observations"]),
        )

    def test_truth_id_mismatch_fails_closed(self):
        support, query, truth = build_object_disjoint_task(1202)
        truth["query_truth"].pop()
        with self.assertRaises(ValueError):
            run_mechanism_controls(support, query, truth)


if __name__ == "__main__":
    unittest.main()
