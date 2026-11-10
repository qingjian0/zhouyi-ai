import unittest

from prototype.e02_ternary import (
    assert_pairwise_balanced, make_dataset, pair_marginal_counts,
)


class E02TernaryTests(unittest.TestCase):
    def test_rule_and_candidate_set(self):
        for ex in make_dataset(90, 7):
            self.assertEqual(len(ex.candidates), 3)
            self.assertEqual(len(set(ex.candidates)), 3)
            a, b, c = ex.candidates[ex.target]
            self.assertEqual((a + b + c) % 3, 0)
            for i, (x, y, z) in enumerate(ex.candidates):
                if i != ex.target:
                    self.assertNotEqual((x + y + z) % 3, 0)

    def test_exact_pairwise_balance(self):
        data = make_dataset(90, 11)
        assert_pairwise_balanced(data)
        counts = pair_marginal_counts(data)
        self.assertEqual(set(counts["positive"]), set(counts["negative"]))
        for key, positive_count in counts["positive"].items():
            self.assertEqual(counts["negative"][key], 2 * positive_count)

    def test_seed_reproducibility_and_independence(self):
        self.assertEqual(make_dataset(90, 19), make_dataset(90, 19))
        self.assertNotEqual(make_dataset(90, 19), make_dataset(90, 20))

    def test_requires_complete_nine_query_blocks(self):
        with self.assertRaises(ValueError):
            make_dataset(10, 1)

    def test_rejects_empty_dataset_for_balance_audit(self):
        with self.assertRaises(AssertionError):
            assert_pairwise_balanced([])


if __name__ == "__main__":
    unittest.main()
