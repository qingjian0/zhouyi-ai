import unittest

from prototype.xra_partition import exact_predictive_partition


class XRAPredictivePartitionTests(unittest.TestCase):
    def test_equivalent_states_merge_when_all_future_behavior_matches(self):
        states = ("A", "B", "C", "D")
        actions = ("step",)
        outcomes = {
            ("A", "step"): "start", ("B", "step"): "start",
            ("C", "step"): "loop", ("D", "step"): "loop",
        }
        transitions = {
            ("A", "step"): "C", ("B", "step"): "D",
            ("C", "step"): "C", ("D", "step"): "D",
        }
        result = exact_predictive_partition(states, actions, outcomes, transitions)
        self.assertEqual(result.blocks, (("A", "B"), ("C", "D")))
        self.assertTrue(result.equivalent("A", "B"))
        self.assertTrue(result.equivalent("C", "D"))
        self.assertFalse(result.equivalent("A", "C"))

    def test_refinement_propagates_future_distinction_backwards(self):
        states = ("A", "B", "C", "D")
        actions = ("step",)
        outcomes = {
            ("A", "step"): "go", ("B", "step"): "go",
            ("C", "step"): "red", ("D", "step"): "blue",
        }
        transitions = {
            ("A", "step"): "C", ("B", "step"): "D",
            ("C", "step"): "C", ("D", "step"): "D",
        }
        result = exact_predictive_partition(states, actions, outcomes, transitions)
        self.assertEqual(len(result.blocks), 4)
        self.assertFalse(result.equivalent("A", "B"))
        self.assertGreaterEqual(result.refinement_rounds, 3)

    def test_one_action_can_distinguish_states(self):
        states = ("left", "right")
        actions = ("inspect", "wait")
        outcomes = {
            ("left", "inspect"): "yes", ("right", "inspect"): "no",
            ("left", "wait"): "same", ("right", "wait"): "same",
        }
        transitions = {
            ("left", "inspect"): "left", ("right", "inspect"): "right",
            ("left", "wait"): "left", ("right", "wait"): "right",
        }
        result = exact_predictive_partition(states, actions, outcomes, transitions)
        self.assertEqual(len(result.blocks), 2)

    def test_rejects_empty_or_duplicate_domains(self):
        with self.assertRaises(ValueError):
            exact_predictive_partition((), ("a",), {}, {})
        with self.assertRaises(ValueError):
            exact_predictive_partition(("s",), (), {}, {})
        with self.assertRaises(ValueError):
            exact_predictive_partition(("s", "s"), ("a",), {}, {})

    def test_rejects_incomplete_tables(self):
        with self.assertRaises(ValueError):
            exact_predictive_partition(("s",), ("a",), {}, {("s", "a"): "s"})
        with self.assertRaises(ValueError):
            exact_predictive_partition(("s",), ("a",), {("s", "a"): "x"}, {})

    def test_rejects_unknown_transition_target(self):
        with self.assertRaises(ValueError):
            exact_predictive_partition(
                ("s",), ("a",),
                {("s", "a"): "x"},
                {("s", "a"): "missing"},
            )

    def test_rejects_unhashable_outcomes(self):
        with self.assertRaises(ValueError):
            exact_predictive_partition(
                ("s",), ("a",),
                {("s", "a"): ["not", "hashable"]},
                {("s", "a"): "s"},
            )

    def test_block_ids_are_deterministic_in_input_order(self):
        states = ("z", "a", "m")
        actions = ("step",)
        outcomes = {
            ("z", "step"): "first",
            ("a", "step"): "second",
            ("m", "step"): "first",
        }
        transitions = { (state, "step"): state for state in states }
        result = exact_predictive_partition(states, actions, outcomes, transitions)
        self.assertEqual(result.blocks, (("z", "m"), ("a",)))
        self.assertEqual(result.block_of("z"), 0)
        self.assertEqual(result.block_of("a"), 1)


if __name__ == "__main__":
    unittest.main()
