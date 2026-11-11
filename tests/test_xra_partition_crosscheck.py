import itertools
import random
import unittest

from prototype.xra_partition import exact_predictive_partition
from prototype.xra_partition_crosscheck import (\n    greatest_bisimulation_partition,\n    shortest_distinguishing_sequence,\n)


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



class XRADistinguishingWitnessTests(unittest.TestCase):
    def test_immediate_distinction_has_one_action_witness(self):
        states = ("red", "blue")
        actions = ("inspect", "wait")
        outcomes = {
            ("red", "inspect"): "R", ("blue", "inspect"): "B",
            ("red", "wait"): "same", ("blue", "wait"): "same",
        }
        transitions = {
            (s, a): s for s in states for a in actions
        }
        self.assertEqual(
            shortest_distinguishing_sequence(
                states, actions, outcomes, transitions, "red", "blue"
            ),
            ("inspect",),
        )

    def test_delayed_distinction_returns_shortest_sequence(self):
        states = ("A", "B", "C", "D")
        actions = ("step", "jump")
        outcomes = {
            ("A", "step"): "go", ("B", "step"): "go",
            ("A", "jump"): "same", ("B", "jump"): "same",
            ("C", "step"): "red", ("D", "step"): "blue",
            ("C", "jump"): "same", ("D", "jump"): "same",
        }
        transitions = {
            ("A", "step"): "C", ("B", "step"): "D",
            ("A", "jump"): "A", ("B", "jump"): "B",
            ("C", "step"): "C", ("D", "step"): "D",
            ("C", "jump"): "C", ("D", "jump"): "D",
        }
        self.assertEqual(
            shortest_distinguishing_sequence(
                states, actions, outcomes, transitions, "A", "B"
            ),
            ("step", "step"),
        )

    def test_equivalent_states_have_no_finite_witness(self):
        states = ("A", "B")
        actions = ("step",)
        outcomes = {("A", "step"): "same", ("B", "step"): "same"}
        transitions = {("A", "step"): "A", ("B", "step"): "B"}
        self.assertIsNone(
            shortest_distinguishing_sequence(
                states, actions, outcomes, transitions, "A", "B"
            )
        )

    def test_unknown_query_state_is_rejected(self):
        with self.assertRaises(KeyError):
            shortest_distinguishing_sequence(
                ("A",), ("step",), {("A", "step"): "x"},
                {("A", "step"): "A"}, "A", "missing"
            )


if __name__ == "__main__":
    unittest.main()
