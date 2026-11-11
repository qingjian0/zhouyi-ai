import unittest
from fractions import Fraction

from prototype.e12m2_finite_chain_audit import (
    _transition_matrix,
    exact_stationary_distribution,
    run_finite_chain_convergence,
)
from prototype.e12m2_exact_state_audit import enumerate_degree_realizations


class E12M2FiniteChainAuditTests(unittest.TestCase):
    def test_exact_stationary_distribution_for_two_state_chain(self):
        states = enumerate_degree_realizations((1, 1), {"a": 1, "b": 1})
        matrix = _transition_matrix(states)
        stationary = exact_stationary_distribution(matrix)
        self.assertEqual(stationary, [Fraction(1, 2), Fraction(1, 2)])
        for column in range(len(matrix)):
            self.assertEqual(
                sum(stationary[row] * matrix[row][column]
                    for row in range(len(matrix))),
                stationary[column],
            )

    def test_one_state_chain_has_unit_stationary_mass(self):
        self.assertEqual(exact_stationary_distribution([[Fraction(1, 1)]]),
                         [Fraction(1, 1)])

    def test_finite_chain_report_is_deterministic_and_normalized(self):
        kwargs = {
            "row_degrees": (1, 1),
            "item_degrees": {"a": 1, "b": 1},
            "chains": 2,
            "burn_in_steps": 10,
            "sample_steps": 100,
            "seed": 7,
        }
        first = run_finite_chain_convergence(**kwargs)
        self.assertEqual(first, run_finite_chain_convergence(**kwargs))
        self.assertEqual(first["state_count"], 2)
        self.assertEqual(sum(first["pooled_state_counts"]), 200)
        self.assertEqual(first["stationary_distribution"][0]["probability"], "1/2")

    def test_invalid_margins_and_matrix_are_rejected(self):
        with self.assertRaises(ValueError):
            exact_stationary_distribution([])
        with self.assertRaises(ValueError):
            exact_stationary_distribution([[Fraction(1, 2)]])


if __name__ == "__main__":
    unittest.main()
