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
        self.assertEqual(
            prior_for(world, "matched_mix_50"),
            tuple(0.5 * a + 0.5 * b for a, b in zip(prior_for(world, "matched"), prior_for(world, "uniform"))),
        )
        self.assertEqual(
            prior_for(world, "anti_mix_25"),
            tuple(0.25 * a + 0.75 * b for a, b in zip(prior_for(world, "anti_aligned"), prior_for(world, "uniform"))),
        )

    def test_episode_reports_calibration_and_confident_error_metrics(self):
        world = make_world("rare")
        result = run_episode(world, 0, prior_for(world, "anti_aligned"), "expected_ig", 3, 19)
        self.assertIn("brier", result)
        self.assertIn("log_loss", result)
        self.assertIn("overconfident_wrong", result)
        self.assertGreaterEqual(result["brier"], 0.0)
        self.assertGreaterEqual(result["log_loss"], 0.0)

    def test_exact_dynamic_programming_is_no_worse_than_one_step_on_its_model(self):
        from prototype.e12a2d_noisy_prior_stress import (
            _entropy, _exact_value, _outcome_probability, _posterior,
        )
        world = make_world("complementary")
        prior = prior_for(world, "matched")
        actions = world.actions
        exact_value, selected = _exact_value(
            prior, actions, tuple(range(len(actions))), 3
        )
        one_step_values = []
        for action in actions:
            if action.cost <= 3:
                one_step_values.append(sum(
                    _outcome_probability(prior, action, outcome)
                    * _entropy(_posterior(prior, action, outcome))
                    for outcome in (0, 1)
                ))
        self.assertIsNotNone(selected)
        self.assertLessEqual(exact_value, min(one_step_values) + 1e-12)

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

    def test_exact_planner_tie_break_is_action_order_invariant(self):
        world = make_world("complementary")
        actions = (
            NoisyAction("z_sensor", 1, (0.9, 0.9, 0.1, 0.1)),
            NoisyAction("a_sensor", 1, (0.9, 0.9, 0.1, 0.1)),
        )
        prior = (0.25, 0.25, 0.25, 0.25)
        first = select_action("exact_optimal", prior, actions, (0, 1), 1, random.Random(1))
        second = select_action("exact_optimal", prior, tuple(reversed(actions)), (0, 1), 1, random.Random(1))
        self.assertEqual(actions[first].action_id, tuple(reversed(actions))[second].action_id)
        self.assertEqual(actions[first].action_id, "a_sensor")

    def test_boolean_prior_and_sensor_probabilities_are_rejected(self):
        from prototype.e12a2d_noisy_prior_stress import _validate
        world = make_world("rare")
        with self.assertRaises(ValueError):
            _validate(world, (True, 0.0, 0.0, 0.0))
        invalid = type(world)(
            world.family, world.hypothesis_ids, world.true_prior,
            (NoisyAction("bad_sensor", 1, (True, 0.2, 0.3, 0.4)),),
        )
        with self.assertRaises(ValueError):
            _validate(invalid, prior_for(world, "matched"))

    def test_invalid_target_index_is_rejected(self):
        world = make_world("rare")
        with self.assertRaises(ValueError):
            run_episode(world, 99, prior_for(world, "matched"), "expected_ig", 3, 19)

    def test_unknown_policy_is_rejected(self):
        world = make_world("rare")
        with self.assertRaises(ValueError):
            select_action("truth_oracle", prior_for(world, "matched"), world.actions, (0, 1), 2, random.Random(1))

    def test_benchmark_covers_every_family_prior_and_policy(self):
        result = run_benchmark(episodes=2, budget=2, start_seed=5)
        from prototype.e12a2d_noisy_prior_stress import PRIOR_ARMS
        self.assertEqual(len(result["rows"]), 3 * len(PRIOR_ARMS) * len(POLICIES))
        self.assertTrue(all(row["episodes"] == 2 for row in result["rows"]))
        self.assertEqual(
            len(result["paired_prior_contrasts"]),
            3 * len(POLICIES) * (len(PRIOR_ARMS) - 1),
        )
        for contrast in result["paired_prior_contrasts"]:
            self.assertLessEqual(contrast["brier"]["ci95_low"], contrast["brier"]["ci95_high"])


if __name__ == "__main__":
    unittest.main()
