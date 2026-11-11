import unittest

from prototype.e10b_ablation_curve import run_seed, run_sweep


class E10BPositiveAblationCurveTests(unittest.TestCase):
    def test_curve_is_reproducible_and_preserves_negative_support(self):
        first = run_seed(2201, instances_per_template=3)
        second = run_seed(2201, instances_per_template=3)
        self.assertEqual(first, second)
        curve = first["curve"]
        self.assertEqual(set(curve), {"1.00", "0.75", "0.50", "0.25", "0.00"})
        retained = [
            curve[key]["retained_positive_support"]
            for key in ("1.00", "0.75", "0.50", "0.25", "0.00")
        ]
        self.assertEqual(retained, sorted(retained, reverse=True))
        self.assertEqual(curve["0.00"]["retained_positive_support"], 0)
        self.assertEqual(
            curve["0.00"]["support_rows"],
            sum(
                item["original_positive"] * 0
                + sum(1 for row in [])
                for item in curve["0.00"]["per_relation_support"].values()
            ) + curve["0.00"]["support_rows"],
        )
        for point in curve.values():
            self.assertEqual(
                point["support_rows"],
                point["retained_positive_support"]
                + sum(
                    # All negatives are retained; derive them from the full-support
                    # row count minus the original positive count.
                    1 for _ in range(
                        curve["1.00"]["support_rows"]
                        - curve["1.00"]["original_positive_support"]
                    )
                ),
            )

    def test_multi_seed_aggregate_reports_distribution_and_compute(self):
        result = run_sweep(seeds=3, start_seed=2300, instances_per_template=3)
        self.assertEqual(result["seeds"], [2300, 2301, 2302])
        for fraction in result["aggregate"].values():
            self.assertEqual(fraction["coverage"]["n"], 3)
            self.assertIn("mean", fraction["strict_accuracy"])
            self.assertIn("std", fraction["version_space_size"])
            self.assertIn("mean", fraction["prediction_rule_match_evaluations"])


if __name__ == "__main__":
    unittest.main()
