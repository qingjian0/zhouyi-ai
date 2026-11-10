import unittest

from prototype.e12a5_residual_pair_diagnosis import (
    FeatureSpec, ResidualRecord, ResidualView,
)
from prototype.e12a5_maxstat_permutation import maxstat_permutation_test


def make_view(n=16):
    rows = []
    for i in range(n):
        residual = int(i >= n // 2)
        # One feature pair separates the residual classes by a large margin.
        x = 10.0 if residual else 0.0
        rows.append(ResidualRecord(
            f"e{i:02d}", (("x", x), ("y", 0.0)), residual, 0
        ))
    return ResidualView(
        (FeatureSpec("x"), FeatureSpec("y")), tuple(rows),
        "out_of_fold", "a3-v2",
    )


class MaxStatPermutationTests(unittest.TestCase):
    def test_strong_signal_is_familywise_significant(self):
        result = maxstat_permutation_test(
            make_view(), permutations=199, seed=7, min_side_support=2,
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["observed_max_statistic"], 1.0)
        self.assertTrue(result["global_family_wise_significant"])
        self.assertLessEqual(result["global_maxT_adjusted_p_value"], 0.05)

    def test_seed_produces_identical_null_distribution(self):
        view = make_view()
        a = maxstat_permutation_test(view, permutations=49, seed=123)
        b = maxstat_permutation_test(view, permutations=49, seed=123)
        self.assertEqual(a["null_maxima"], b["null_maxima"])
        self.assertEqual(a["diagnoses"], b["diagnoses"])

    def test_max_statistic_repeats_the_full_scan_for_each_permutation(self):
        result = maxstat_permutation_test(make_view(), permutations=19, seed=3)
        self.assertEqual(
            result["required_candidate_evaluations"],
            result["per_threshold_polarity_evaluations"] * 20,
        )
        self.assertEqual(result["permutations_completed"], 19)

    def test_budget_exhaustion_abstains_without_partial_p_value(self):
        result = maxstat_permutation_test(
            make_view(), permutations=999, max_total_candidate_evaluations=1,
        )
        self.assertEqual(result["status"], "BUDGET_EXHAUSTED")
        self.assertEqual(result["permutations_completed"], 0)
        self.assertNotIn("global_maxT_adjusted_p_value", result)

    def test_invalid_seed_and_alpha_fail_closed(self):
        with self.assertRaises(TypeError):
            maxstat_permutation_test(make_view(), seed=True)
        with self.assertRaises(ValueError):
            maxstat_permutation_test(make_view(), alpha=1.0)

    def test_result_preserves_prediction_provenance_and_evidence(self):
        result = maxstat_permutation_test(make_view(), permutations=9)
        self.assertEqual(result["prediction_mode"], "out_of_fold")
        self.assertEqual(result["model_version"], "a3-v2")
        self.assertEqual(result["record_count"], 16)
        self.assertEqual(result["diagnoses"][0]["evidence_ids"],
                         tuple(f"e{i:02d}" for i in range(16)))

    def test_in_sample_predictions_are_rejected(self):
        view = make_view()
        invalid = ResidualView(view.schema, view.records, "in_sample", view.model_version)
        with self.assertRaises(ValueError):
            maxstat_permutation_test(invalid)


if __name__ == "__main__":
    unittest.main()
