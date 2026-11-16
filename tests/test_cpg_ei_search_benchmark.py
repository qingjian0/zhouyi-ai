import unittest

from benchmarks.benchmark_cpg_ei_search import build_case, run_benchmark


class CpgEiSearchBenchmarkTests(unittest.TestCase):
    def test_case_generation_is_deterministic(self):
        first_model, first_nodes = build_case(11, 4, "mixed_random")
        second_model, second_nodes = build_case(11, 4, "mixed_random")
        self.assertEqual(first_model.weights, second_model.weights)
        self.assertEqual(first_nodes, second_nodes)

    def test_small_benchmark_requires_exact_ranking_agreement(self):
        result = run_benchmark(
            pool_sizes=(3,),
            seeds=1,
            repeats=1,
            scenarios=("mixed_random",),
        )
        self.assertEqual(len(result["raw"]), 1)
        self.assertTrue(result["raw"][0]["exact_agreement"])
        self.assertGreater(result["raw"][0]["exact_seconds"], 0.0)
        self.assertGreater(result["raw"][0]["branch_bound_seconds"], 0.0)
        self.assertGreater(result["raw"][0]["upper_bound_evaluations"], 0)
        self.assertTrue(result["summaries"][0]["all_exact"])


if __name__ == "__main__":
    unittest.main()
