import unittest

from prototype.e12m2_exact_state_audit import (
    audit_small_state_space,
    enumerate_degree_realizations,
)


class E12M2ExactStateAuditTests(unittest.TestCase):
    def test_two_by_two_regular_degree_sequence_is_connected_and_symmetric(self):
        report = audit_small_state_space(
            row_degrees=(1, 1),
            item_degrees={"a": 1, "b": 1},
        )
        self.assertEqual(report["state_count"], 2)
        self.assertTrue(report["connected"])
        self.assertEqual(report["asymmetric_transition_pairs"], 0)
        self.assertTrue(report["stationary_uniformity_supported"])

    def test_enumerator_returns_exact_fixed_margin_states(self):
        states = enumerate_degree_realizations(
            row_degrees=(1, 1),
            item_degrees={"a": 1, "b": 1},
        )
        self.assertEqual(len(states), 2)
        for state in states:
            self.assertEqual(tuple(map(len, state)), (1, 1))
            self.assertEqual(
                {item: sum(item in row for row in state) for item in ("a", "b")},
                {"a": 1, "b": 1},
            )

    def test_infeasible_margins_return_empty_state_space(self):
        report = audit_small_state_space(
            row_degrees=(2, 2, 0),
            item_degrees={"a": 3, "b": 1, "c": 0},
        )
        self.assertEqual(report["state_count"], 0)
        self.assertFalse(report["stationary_uniformity_supported"])

    def test_invalid_margins_and_state_cap_are_rejected(self):
        with self.assertRaises(ValueError):
            enumerate_degree_realizations((1,), {"a": 2})
        with self.assertRaises(ValueError):
            enumerate_degree_realizations((1, 1), {"a": 1, "b": 1}, max_states=0)
        with self.assertRaises(ValueError):
            enumerate_degree_realizations((1, 1), {"a": 1, "b": 1}, max_states=1)


if __name__ == "__main__":
    unittest.main()
