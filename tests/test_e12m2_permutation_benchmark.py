import unittest
from collections import Counter

from prototype.e12m2_permutation_benchmark import (
    degree_preserving_swaps,
    permutation_test,
)


def degrees(rows):
    row_degrees = [len(row) for row in rows]
    item_degrees = Counter(item for row in rows for item in row)
    return row_degrees, item_degrees


class E12M2PermutationTests(unittest.TestCase):
    def test_switches_preserve_row_and_item_degrees(self):
        rows = [
            {"a", "b"}, {"a", "c"}, {"b", "d"}, {"c", "d"},
            {"a", "d"}, {"b", "c"},
        ]
        randomized, accepted = degree_preserving_swaps(rows, swaps=500, seed=19)
        self.assertGreater(accepted, 0)
        self.assertNotEqual(rows, randomized)
        self.assertEqual(degrees(rows), degrees(randomized))
        self.assertEqual(len(randomized), len(rows))

    def test_same_seed_is_deterministic(self):
        rows = [{"a", "b"}, {"a", "c"}, {"b", "d"}, {"c", "d"}]
        first, accepted_first = degree_preserving_swaps(rows, swaps=300, seed=7)
        second, accepted_second = degree_preserving_swaps(rows, swaps=300, seed=7)
        self.assertEqual(first, second)
        self.assertEqual(accepted_first, accepted_second)

    def test_permutation_test_reports_empirical_and_max_statistic_p(self):
        rows = [
            {"a", "c", "x"}, {"a", "c", "y"}, {"a", "c", "z"},
            {"a", "c", "w"}, {"b", "x"}, {"d", "y"},
            {"b", "z"}, {"d", "w"},
        ]
        result = permutation_test(rows, ("a", "c"), permutations=49,
                                  swaps_per_edge=20, max_order=2, seed=31)
        self.assertGreater(result.observed_score, 0)
        self.assertGreaterEqual(result.p_value, 1 / 50)
        self.assertLessEqual(result.p_value, 1.0)
        self.assertGreaterEqual(result.max_statistic_p_value, 1 / 50)
        self.assertLessEqual(result.max_statistic_p_value, 1.0)
        self.assertEqual(result.permutations, 49)
        self.assertGreater(result.attempted_swaps, 0)

    def test_no_swappable_graph_has_valid_conservative_p_value(self):
        rows = [{"a", "b", "c"}] * 5
        result = permutation_test(rows, ("a", "b"), permutations=9,
                                  swaps_per_edge=2, seed=3)
        self.assertEqual(result.accepted_swaps, 0)
        self.assertEqual(result.acceptance_rate, 0.0)
        self.assertEqual(result.p_value, 1.0)

    def test_invalid_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            degree_preserving_swaps([{"a"}], swaps=-1)
        with self.assertRaises(ValueError):
            permutation_test([{"a", "b"}], ("a", "b"), permutations=0)
        with self.assertRaises(ValueError):
            permutation_test([{"a", "b"}], ("a", "a"))
        with self.assertRaises(ValueError):
            permutation_test([{"a", "b"}], ("a", "b"), max_order=1)

    def test_empty_observations_return_zero_score_without_crashing(self):
        result = permutation_test([], ("a", "b"), permutations=3, seed=2)
        self.assertEqual(result.observed_score, 0.0)
        self.assertEqual(result.p_value, 1.0)


if __name__ == "__main__":
    unittest.main()
