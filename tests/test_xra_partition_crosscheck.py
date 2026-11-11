import itertools
import random
import unittest

from prototype.xra_partition import exact_predictive_partition
from prototype.xra_partition_crosscheck import greatest_bisimulation_partition


def _tables(states, actions, outcomes_flat, targets_flat):
    outcomes = {}
    transitions = {}
    index = 0
    for state in states:
        for action in actions:
            outcomes[(state, action)] = outcomes_flat[index]
            transitions[(state, action)] = targets_flat[index]
            index += 1
    return outcomes, transitions


class XRAPartitionCrossCheckTests(unittest.TestCase):
    def assert_oracles_agree(self, states, actions, outcomes, transitions):
        refined = exact_predictive_partition(states, actions, outcomes, transitions)
        eliminated = greatest_bisimulation_partition(states, actions, outcomes, transitions)
        self.assertEqual(refined.blocks, eliminated.blocks)
        for left in states:
            for right in states:
                self.assertEqual(
                    refined.equivalent(left, right),
                    (left, right) in eliminated.related_pairs,
                )

    def test_exhaustive_all_two_state_one_action_worlds(self):
        states = (0, 1)
        actions = ("a",)
        choices = tuple(itertools.product((0, 1), states))
        for per_state in itertools.product(choices, repeat=len(states)):
            outcomes = {(s, "a"): per_state[s][0] for s in states}
            transitions = {(s, "a"): per_state[s][1] for s in states}
            self.assert_oracles_agree(states, actions, outcomes, transitions)

    def test_exhaustive_three_state_one_action_worlds(self):
        states = (0, 1, 2)
        actions = ("a",)
        choices = tuple(itertools.product((0, 1), states))
        # 6 choices per state -> 6^3 = 216 complete deterministic worlds.
        for per_state in itertools.product(choices, repeat=len(states)):
            outcomes = {(s, "a"): per_state[s][0] for s in states}
            transitions = {(s, "a"): per_state[s][1] for s in states}
            self.assert_oracles_agree(states, actions, outcomes, transitions)

    def test_seeded_four_state_multi_action_worlds(self):
        rng = random.Random(20261111)
        states = tuple(range(4))
        actions = ("inspect", "wait")
        for _ in range(500):
            outcomes = {
                (s, a): rng.randrange(3)
                for s in states for a in actions
            }
            transitions = {
                (s, a): rng.choice(states)
                for s in states for a in actions
            }
            self.assert_oracles_agree(states, actions, outcomes, transitions)

    def test_rejects_incomplete_and_invalid_tables(self):
        with self.assertRaises(ValueError):
            greatest_bisimulation_partition(("s",), ("a",), {}, {})
        with self.assertRaises(ValueError):
            greatest_bisimulation_partition(
                ("s",), ("a",), {("s", "a"): "x"},
                {("s", "a"): "missing"},
            )

    def test_rejects_unhashable_outcome(self):
        with self.assertRaises(ValueError):
            greatest_bisimulation_partition(
                ("s",), ("a",), {("s", "a"): ["x"]},
                {("s", "a"): "s"},
            )


if __name__ == "__main__":
    unittest.main()
