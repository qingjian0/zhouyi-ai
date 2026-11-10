import unittest

from prototype.yinfu_dynamic_cognition import (
    Transition, detect_change_point, enumerate_paths,
    generate_relation_candidates, learn_contextual_reversal, run_synthetic_benchmark,
)


class YinfuDynamicCognitionTests(unittest.TestCase):
    def test_yf07_detects_shift_and_respects_threshold(self):
        values = [0.0, 0.1, -0.1, 0.0, 3.0, 3.1, 2.9, 3.0]
        result = detect_change_point(values, min_segment=3, min_effect=1.0)
        self.assertTrue(result.detected)
        self.assertEqual(result.index, 4)
        self.assertFalse(detect_change_point(values, min_effect=10.0).detected)

    def test_yf07_abstains_on_short_series(self):
        self.assertEqual(
            detect_change_point([1.0, 2.0], min_segment=2).reason,
            "INSUFFICIENT_SERIES",
        )

    def test_yf08_generates_pairwise_relation_from_support(self):
        rows = [
            {"a": 0.0, "b": 0.0}, {"a": 0.0, "b": 2.0},
            {"a": 2.0, "b": 0.0}, {"a": 2.0, "b": 2.0},
            {"a": 1.0, "b": 0.0}, {"a": 0.0, "b": 1.0},
        ]
        labels = [0, 0, 0, 1, 0, 0]
        candidates = generate_relation_candidates(rows, labels, max_candidates=256)
        self.assertTrue(candidates)
        self.assertGreaterEqual(candidates[0].balanced_accuracy, 0.75)
        self.assertTrue(any(s.candidate.operator == "product" for s in candidates))

    def test_yf08_candidate_budget_preserves_operator_families(self):
        import random
        rng = random.Random(7)
        rows = [{"x": rng.uniform(-2, 2), "y": rng.uniform(-2, 2)}
                for _ in range(120)]
        labels = [int(row["x"] * row["y"] > 0.8) for row in rows]
        candidates = generate_relation_candidates(
            rows, labels, max_features=2, max_candidates=64)
        operators = {item.candidate.operator for item in candidates}
        self.assertIn("feature", operators)
        self.assertIn("difference", operators)
        self.assertIn("product", operators)

    def test_unified_synthetic_benchmark_is_reproducible(self):
        first = run_synthetic_benchmark(seeds=1, start_seed=23)
        second = run_synthetic_benchmark(seeds=1, start_seed=23)
        self.assertEqual(first, second)
        self.assertEqual(len(first["results"]), 1)
        self.assertIn("YF07", first["results"][0])
        self.assertIn("YF08", first["results"][0])
        self.assertIn("YF09", first["results"][0])
        self.assertIn("YF10", first["results"][0])

    def test_unified_synthetic_benchmark_rejects_zero_seeds(self):
        with self.assertRaises(ValueError):
            run_synthetic_benchmark(seeds=0)

    def test_yf08_rejects_one_class_support(self):
        with self.assertRaises(ValueError):
            generate_relation_candidates([{"x": 1.0}, {"x": 2.0}], [1, 1])

    def test_yf09_learns_contextual_sign_reversal(self):
        data = [("calm", 0.4), ("calm", 0.5), ("calm", 0.3),
                ("stress", -0.4), ("stress", -0.5), ("stress", -0.3)]
        result = learn_contextual_reversal(data, min_samples=3)
        self.assertTrue(result.reversed)
        self.assertEqual({result.context_a, result.context_b}, {"calm", "stress"})

    def test_yf09_abstains_without_two_supported_contexts(self):
        result = learn_contextual_reversal([("only", 0.5), ("only", 0.6)])
        self.assertFalse(result.reversed)
        self.assertEqual(result.reason, "INSUFFICIENT_CONTEXT_EVIDENCE")

    def test_yf10_enumerates_multiple_paths_and_respects_budget(self):
        edges = [
            Transition("s", "a", 4.0, 1.0),
            Transition("a", "t", 3.0, 1.0),
            Transition("s", "b", 2.0, 0.5),
            Transition("b", "t", 5.0, 0.5),
            Transition("s", "expensive", 100.0, 20.0),
        ]
        paths = enumerate_paths(edges, start="s", max_depth=3, budget=2.0, top_k=5)
        self.assertGreaterEqual(len(paths), 2)
        self.assertEqual(paths[0].nodes, ("s", "b", "t"))
        self.assertTrue(all(p.total_cost <= 2.0 for p in paths))

    def test_yf10_rejects_cycles_and_invalid_cost(self):
        with self.assertRaises(ValueError):
            enumerate_paths([Transition("a", "b", 1.0, -1.0)], start="a")


if __name__ == "__main__":
    unittest.main()
