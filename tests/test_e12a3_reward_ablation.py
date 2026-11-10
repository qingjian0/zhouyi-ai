import unittest

from prototype.e12a3_adaptive_benchmark import make_four_way_world
from prototype.e12a3_reward_ablation import REWARD_MODES, run_benchmark, run_episode
from prototype.e12a3_adaptive_benchmark import _adaptive_allocate


class E12A3RewardAblationTests(unittest.TestCase):
    def test_all_reward_modes_are_bounded_and_exact_budget(self):
        support, gate_dev, _, _ = make_four_way_world(31, "THRESHOLD")
        for mode in REWARD_MODES:
            result = _adaptive_allocate(
                support, gate_dev, 31, budget=19, reward_mode=mode,
            )
            self.assertEqual(result["proposal_slots_used"], 19)
            self.assertEqual(sum(result["allocations"].values()), 19)
            self.assertEqual(result["reward_mode"], mode)
            self.assertTrue(all(
                0.0 <= event["reward"] <= 1.0
                for event in result["trace"]
            ))

    def test_unknown_reward_mode_is_rejected(self):
        support, gate_dev, _, _ = make_four_way_world(32, "THRESHOLD")
        with self.assertRaises(ValueError):
            _adaptive_allocate(
                support, gate_dev, 32, budget=16, reward_mode="LOOKAHEAD_TEST",
            )

    def test_reward_ablation_is_reproducible(self):
        first = run_episode(33, "PAIRWISE_DIFFERENCE", budget=20)
        second = run_episode(33, "PAIRWISE_DIFFERENCE", budget=20)
        self.assertEqual(first, second)
        self.assertTrue(all(
            item["proposal_slots_used"] == 20
            for item in first["methods"].values()
        ))

    def test_small_reward_ablation_benchmark_reports_paired_controls(self):
        result = run_benchmark(seeds=2, start_seed=34, budget=20)
        self.assertEqual(result["episode_count"], 4)
        self.assertIn("UCB1_MAX", result["aggregate"])
        self.assertIn("UCB1_DELTA_BEST", result["paired_vs_equal"])
        self.assertEqual(result["paired_vs_equal"]["UCB1_MAX"]["seed_clusters"], 2)


if __name__ == "__main__":
    unittest.main()
