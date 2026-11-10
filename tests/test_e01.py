import unittest

from prototype.e01_sparse_composition import Candidate, exact_match, select_sparse


class SparseCompositionTests(unittest.TestCase):
    def test_can_select_non_adjacent_members(self):
        candidates = [
            Candidate("a", 0.9),
            Candidate("b", 0.8),
            Candidate("c", 0.7),
            Candidate("d", 0.1),
            Candidate("e", 0.6),
        ]
        self.assertEqual(select_sparse(candidates, k=4, threshold=0.5), ["a", "b", "c", "e"])

    def test_respects_budget(self):
        candidates = [Candidate(str(i), 1.0 - i / 10) for i in range(8)]
        self.assertEqual(len(select_sparse(candidates, k=3)), 3)

    def test_stable_tie_breaking(self):
        candidates = [Candidate("x", 0.5), Candidate("y", 0.5), Candidate("z", 0.5)]
        self.assertEqual(select_sparse(candidates, k=2), ["x", "y"])

    def test_negative_budget_rejected(self):
        with self.assertRaises(ValueError):
            select_sparse([], k=-1)

    def test_exact_match_ignores_order(self):
        self.assertTrue(exact_match(["a", "e"], ["e", "a"]))


if __name__ == "__main__":
    unittest.main()
