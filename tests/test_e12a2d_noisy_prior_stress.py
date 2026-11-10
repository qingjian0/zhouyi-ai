import unittest

from prototype.e12a2d_noisy_prior_stress import (
    POLICIES,
    NoisyAction,
    information_gain,
    make_world,
    prior_for,
    run_benchmark,
    run_episode,
    select_action,
)
import random


class E12A2DNoisyPriorStressTests(unittest.TestCase):
    def test_noisy_sensor_has_fractional_information_gain(self):
        world = make_world("complementary")
        gain = information_gain((0.5, 0.0, 0.5, 0.0), world.actions[0])
        self.assertGreater(gain, 0.0)
        self.assertLess(gain, 1.0)

    def test_exact_optimal_is_no_worse_than_greedy_on_tiny_noisy_world(self):
        world = make_world("complementary")
        prior = (0.4, 0.3, 0.2, 0.1)
        greedy = select_action("expected_ig", prior, world.actions, (0, 1, 2, 3), 3, random.Random(1))
        exact = select_action("exact_optimal", prior, world.actions, (0, 1, 2, 3), 3, random.Random(1))
        self.assertIsNotNone(greedy)
        self.assertIsNotNone(exact)

    def test_prior_arms_are_normalized_and_distinct_when_world_is_skewed(self):
        world = make_world("rare")
        self.assertAlmostEqual(sum(prior_for(world, "matched")), 1.0)
        self.assertNotEqual(prior_for(world, "matched"), prior_for(world, "uniform"))
        self.assertNotEqual(prior_for(world, "matched"), prior_for(world, "anti_aligned"))

    def test_episode_reports_calibration_and_confident_error_metrics(self):
        world = make_world("rare")
        result = run_episode(world, 0, prior_for(world, "anti_aligned"), "expected_ig", 3, 19)
        self.assertIn("brier", result)
        self.assertIn("log_loss", result)
        self.assertIn("overconfident_wrong", result)
        self.assertGreaterEqual(result["brier"], 0.0)
        self.assertGreaterEqual(result["log_loss"], 0.0)

    def test_policy_api_does_not_accept_hidden_target(self):
        import inspect
        from prototype.e12a2d_noisy_prior_stress import select_action
        self.assertEqual(
            list(inspect.signature(select_action).parameters),
            ["policy", "prior", "actions", "available", "remaining_budget", "rng"],
        )

    def test_zero_information_sensor_does_not_get_selected(self):
        world = make_world("complementary")
        uninformative = NoisyAction("uninformative", 1, (0.3, 0.3, 0.3, 0.3))
        self.assertAlmostEqual(information_gain((0.25, 0.25, 0.25, 0.25), uninformative), 0.0)
        self.assertIsNone(select_action(
            "expected_ig", (0.25, 0.25, 0.25, 0.25), (uninformative,),
            (0,), 1, random.Random(3),
        ))

    def test_exact_planner_respects_budget_and_does_not_reuse_actions(self):
        world = make_world("complementary")
        result = run_episode(
            world, 0, prior_for(world, "matched"), "exact_optimal", 1, 77
        )
        self.assertLessEqual(result["spent_cost"], 1)

    def test_unknown_policy_is_rejected(self):
        world = make_world("rare")
        with self.assertRaises(ValueError):
            select_action("truth_oracle", prior_for(world, "matched"), world.actions, (0, 1), 2, random.Random(1))

    def test_benchmark_covers_every_family_prior_and_policy(self):
        result = run_benchmark(episodes=2, budget=2, start_seed=5)
        self.assertEqual(len(result["rows"]), 3 * 3 * len(POLICIES))
        self.assertTrue(all(row["episodes"] == 2 for row in result["rows"]))


if __name__ == "__main__":
    unittest.main()
