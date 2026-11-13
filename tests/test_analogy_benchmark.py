import unittest

from prototype.analogy_benchmark import (
    build_analogy_benchmark,
    evaluate_analogy_benchmark,
)


class AnalogyBenchmarkTests(unittest.TestCase):
    def test_generates_balanced_valid_and_counterfactual_examples(self):
        rows = build_analogy_benchmark(variants_per_family=2)
        self.assertEqual(len(rows), 24)
        self.assertEqual(sum(row.expected_valid for row in rows), 12)
        self.assertEqual(sum(not row.expected_valid for row in rows), 12)

    def test_template_families_are_isolated_by_split(self):
        rows = build_analogy_benchmark()
        family_splits = {}
        for row in rows:
            family_splits.setdefault(row.template_family, set()).add(row.split)
        self.assertTrue(all(len(splits) == 1 for splits in family_splits.values()))
        self.assertEqual({row.split for row in rows}, {"train", "validation", "test"})

    def test_exact_relation_baseline_accepts_valid_and_rejects_counterfactual(self):
        result = evaluate_analogy_benchmark()
        self.assertEqual(result["overall"]["accuracy"], 1.0)
        self.assertEqual(result["overall"]["false_accept_rate"], 0.0)
        for split in result["splits"].values():
            self.assertEqual(split["accuracy"], 1.0)

    def test_rejects_invalid_variant_count(self):
        with self.assertRaises(ValueError):
            build_analogy_benchmark(variants_per_family=True)
        with self.assertRaises(ValueError):
            build_analogy_benchmark(variants_per_family=0)

    def test_rejects_duplicate_example_ids(self):
        rows = build_analogy_benchmark()
        with self.assertRaises(ValueError):
            evaluate_analogy_benchmark((rows[0], rows[0]))


if __name__ == "__main__":
    unittest.main()
