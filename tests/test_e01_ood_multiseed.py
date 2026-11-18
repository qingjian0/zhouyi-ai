import unittest

from prototype.e01_ood_multiseed import run_multiseed


class CompositionalOODMultiseedTests(unittest.TestCase):
    def test_reports_pair_and_triple_composition(self):
        result = run_multiseed(seed_count=2, start_seed=4)
        self.assertEqual(result["test_query_cardinalities"], [2, 3])
        self.assertIn("2", result["experiments"])
        self.assertIn("3", result["experiments"])
        self.assertIn("learned_ranker", result["experiments"]["2"]["aggregate"])


if __name__ == "__main__":
    unittest.main()
