import unittest
from collections import Counter

from prototype.e12m2_chain_diagnostics import (
    _initial_positive_ess,
    _lag1_autocorrelation,
    diagnose_permutation_chains,
)


class E12M2ChainDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"a", "b", "x"}, {"a", "c", "y"}, {"b", "d", "z"},
            {"c", "d", "w"}, {"a", "d", "w"}, {"b", "c", "x"},
            {"a", "c", "z"}, {"b", "d", "y"},
        ]

    def test_trace_diagnostics_are_reproducible(self):
        kwargs = dict(
            chains=3, samples_per_chain=20, burn_in_swaps_per_edge=2,
            thinning_swaps_per_edge=1, seed=41,
        )
        first = diagnose_permutation_chains(self.rows, ("a", "b"), **kwargs)
        second = diagnose_permutation_chains(self.rows, ("a", "b"), **kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first["total_samples"], 60)
        self.assertEqual(len(first["chain_reports"]), 3)
        self.assertIn("do not prove", first["warning"])

    def test_chain_reports_acceptance_and_trace_bounds(self):
        result = diagnose_permutation_chains(
            self.rows, ("a", "b"), chains=2, samples_per_chain=12, seed=5
        )
        for report in result["chain_reports"]:
            self.assertEqual(len(report["trace"]), 12)
            self.assertGreaterEqual(report["acceptance_rate"], 0.0)
            self.assertLessEqual(report["acceptance_rate"], 1.0)
            self.assertGreaterEqual(report["ess_initial_positive"], 1.0)
            self.assertLessEqual(report["ess_initial_positive"], 12.0)

    def test_zero_thinning_produces_constant_trace_without_attempts(self):
        result = diagnose_permutation_chains(
            self.rows, ("a", "b"), chains=1, samples_per_chain=5,
            burn_in_swaps_per_edge=0, thinning_swaps_per_edge=0, seed=8,
        )
        report = result["chain_reports"][0]
        self.assertEqual(report["attempted_swaps"], 0)
        self.assertEqual(report["acceptance_rate"], 0.0)
        self.assertEqual(len(set(report["trace"])), 1)

    def test_constant_trace_has_full_ess_and_zero_autocorrelation(self):
        self.assertEqual(_initial_positive_ess([2.0] * 10), 10.0)
        self.assertEqual(_lag1_autocorrelation([2.0] * 10), 0.0)

    def test_ess_is_bounded(self):
        values = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
        ess = _initial_positive_ess(values)
        self.assertGreaterEqual(ess, 1.0)
        self.assertLessEqual(ess, len(values))

    def test_invalid_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            diagnose_permutation_chains(self.rows, ("a", "b"), chains=0)
        with self.assertRaises(ValueError):
            diagnose_permutation_chains(self.rows, ("a", "b"), samples_per_chain=1)
        with self.assertRaises(ValueError):
            diagnose_permutation_chains(self.rows, ("a", "a"))
        with self.assertRaises(ValueError):
            diagnose_permutation_chains(
                self.rows, ("a", "b"), burn_in_swaps_per_edge=-1
            )


if __name__ == "__main__":
    unittest.main()
