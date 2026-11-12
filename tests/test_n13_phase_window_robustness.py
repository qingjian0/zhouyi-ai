import math
import unittest

from prototype.n13_phase_window_robustness import (
    WINDOW_STARTS,
    make_dataset,
    run,
    run_condition,
)


def recovered_phase(row, role_index):
    node = row.assignment[role_index]
    sine_index = 2 if role_index == 0 else 1
    return math.atan2(node.features[sine_index], node.features[0]) % (2.0 * math.pi)


class N13PhaseWindowRobustnessTests(unittest.TestCase):
    def test_all_roles_and_windows_have_disjoint_train_test_regions(self):
        for role in range(3):
            for start in WINDOW_STARTS:
                train = make_dataset(40, 17, "train", role, start)
                test = make_dataset(40, 29, "test", role, start)
                for row in train:
                    offset = (recovered_phase(row, role) - start) % (2.0 * math.pi)
                    self.assertGreaterEqual(offset, math.pi / 2.0)
                for row in test:
                    offset = (recovered_phase(row, role) - start) % (2.0 * math.pi)
                    self.assertLess(offset, math.pi / 2.0)

    def test_invalid_split_role_and_window_are_rejected(self):
        with self.assertRaises(ValueError):
            make_dataset(10, 1, "validation_bad", 0, 0.0)
        with self.assertRaises(ValueError):
            make_dataset(10, 1, "train", 3, 0.0)
        with self.assertRaises(ValueError):
            make_dataset(10, 1, "train", 0, 0.0, heldout_width=0.0)

    def test_condition_returns_all_three_ablation_metrics(self):
        result = run_condition(
            7, 1, math.pi / 2.0,
            train_count=120, validation_count=60,
            test_count=60, epochs=3,
        )
        self.assertIn("unary_only", result)
        self.assertIn("unary_pairwise", result)
        self.assertIn("unary_pairwise_triple", result)
        self.assertIn("triple_model_after_triple_mask", result)

    def test_sweep_covers_three_roles_and_four_windows(self):
        result = run(
            seeds=2, start_seed=7, train_count=60,
            validation_count=30, test_count=30, epochs=2,
        )
        self.assertEqual(result["condition_count"], 12)
        self.assertEqual(result["total_runs"], 24)
        self.assertEqual(len(result["condition_summary"]), 12)
        self.assertEqual(len(result["per_seed"]), 24)


if __name__ == "__main__":
    unittest.main()
