import inspect
import unittest

from prototype.e12a2b_policy_benchmark import (
    POLICIES,
    WorldAction,
    WorldFamily,
    _information_gain,
    _gini_disagreement,
    make_world_family,
    run_episode,
    select_policy_action,
)


class E12A2BPolicyBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.ids = tuple(f"h{i}" for i in range(8))
        self.active = tuple(range(8))
        self.rng_seed = 19

    def test_information_gain_and_pairwise_disagreement_are_distinct_objectives(self):
        balanced = WorldAction(
            "balanced", 1, ("0", "0", "0", "0", "1", "1", "1", "1")
        )
        skewed_three_way = WorldAction(
            "skewed_three_way", 1, ("a", "a", "a", "a", "a", "a", "b", "c")
        )
        self.assertGreater(
            _information_gain(skewed_three_way, self.active),
            _information_gain(balanced, self.active),
        )
        self.assertGreater(
            _gini_disagreement(balanced, self.active),
            _gini_disagreement(skewed_three_way, self.active),
        )

    def test_max_disagreement_and_expected_ig_can_choose_different_actions(self):
        actions = (
            WorldAction("balanced", 1, ("0", "0", "0", "0", "1", "1", "1", "1")),
            WorldAction("skewed_three_way", 1, ("a", "a", "a", "a", "a", "a", "b", "c")),
        )
        max_gini = select_policy_action(
            "max_disagreement", actions, self.active, (0, 1), 1,
            __import__("random").Random(self.rng_seed),
        )
        max_ig = select_policy_action(
            "expected_ig", actions, self.active, (0, 1), 1,
            __import__("random").Random(self.rng_seed),
        )
        self.assertEqual(actions[max_gini].action_id, "balanced")
        self.assertEqual(actions[max_ig].action_id, "skewed_three_way")

    def test_cost_normalized_ig_accounts_for_acquisition_cost(self):
        actions = (
            WorldAction("perfect_expensive", 3, ("0", "0", "0", "0", "1", "1", "1", "1")),
            WorldAction("partial_cheap", 1, ("a", "a", "a", "a", "a", "a", "b", "b")),
        )
        selected = select_policy_action(
            "cost_normalized_ig", actions, self.active, (0, 1), 3,
            __import__("random").Random(self.rng_seed),
        )
        self.assertEqual(actions[selected].action_id, "partial_cheap")

    def test_policy_api_does_not_accept_hidden_target(self):
        self.assertEqual(
            list(inspect.signature(select_policy_action).parameters),
            ["policy", "actions", "active", "available", "remaining_budget", "rng"],
        )

    def test_all_world_families_are_reproducible(self):
        for family in ("balanced", "skewed", "redundant"):
            self.assertEqual(make_world_family(family, 123), make_world_family(family, 123))

    def test_action_cost_is_respected(self):
        world = WorldFamily(
            "budget_case",
            self.ids,
            (WorldAction("too_expensive", 5, tuple(str(i) for i in range(8))),),
        )
        result = run_episode(world, 0, "expected_ig", budget=4, seed=1)
        self.assertEqual(result.spent_cost, 0)
        self.assertEqual(result.measurements, 0)

    def test_exact_optimal_is_no_worse_than_each_policy_on_small_world(self):
        world = make_world_family("balanced", 41)
        results = {
            policy: [
                run_episode(world, target, policy, budget=3, seed=target + 100)
                for target in range(len(world.hypothesis_ids))
            ]
            for policy in POLICIES
        }
        optimal_entropy = sum(
            item.residual_entropy_bits for item in results["exact_optimal"]
        ) / len(world.hypothesis_ids)
        for policy in POLICIES:
            policy_entropy = sum(
                item.residual_entropy_bits for item in results[policy]
            ) / len(world.hypothesis_ids)
            self.assertLessEqual(
                optimal_entropy, policy_entropy + 1e-12,
                msg=f"exact optimal was worse than {policy}",
            )

    def test_exhaustive_episode_scoring_has_one_row_per_target(self):
        world = make_world_family("redundant", 7)
        rows = [
            run_episode(world, target, "exact_optimal", budget=4, seed=target)
            for target in range(8)
        ]
        self.assertEqual(len(rows), 8)
        self.assertEqual(len({row.target_hypothesis for row in rows}), 8)

    def test_unknown_policy_is_rejected(self):
        with self.assertRaises(ValueError):
            select_policy_action(
                "oracle_cheat", (), self.active, (), 0,
                __import__("random").Random(1),
            )


if __name__ == "__main__":
    unittest.main()
