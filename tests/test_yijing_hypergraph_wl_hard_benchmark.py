import unittest

from prototype.yijing_hypergraph_automorphism import AutomorphismOracleError
from prototype.yijing_hypergraph_wl_hard_benchmark import (
    WLHardBenchmarkError, build_wl_hard_state, run_wl_hard_orbit_benchmark,
)


class WLHardOrbitBenchmarkTests(unittest.TestCase):
    def test_both_cases_are_seven_vertex_two_regular_graphs(self):
        for name in ("cycle7", "triangle_plus_square"):
            state = build_wl_hard_state(name)
            self.assertEqual(len(state.entities), 7)
            self.assertEqual(len(state.hyperedges), 7)
            degree = {entity.entity_id: 0 for entity in state.entities}
            for edge in state.hyperedges:
                for binding in edge.bindings:
                    degree[binding.entity_id] += 1
            self.assertEqual(set(degree.values()), {2})

    def test_one_wl_histograms_match_but_exact_orbits_differ(self):
        report = run_wl_hard_orbit_benchmark()
        cycle, disjoint = report.cases
        self.assertTrue(report.wl_histograms_match)
        self.assertTrue(report.exact_orbit_partitions_differ)
        self.assertEqual(cycle.wl_class_sizes, (7,))
        self.assertEqual(disjoint.wl_class_sizes, (7,))
        self.assertEqual(cycle.exact_orbit_sizes, (7,))
        self.assertEqual(disjoint.exact_orbit_sizes, (3, 4))

    def test_exact_automorphism_group_orders(self):
        report = run_wl_hard_orbit_benchmark()
        self.assertEqual(report.cases[0].automorphism_count, 14)
        self.assertEqual(report.cases[1].automorphism_count, 48)

    def test_pairwise_wl_overmerge_is_measured(self):
        report = run_wl_hard_orbit_benchmark()
        disjoint = report.cases[1]
        self.assertEqual(disjoint.pairwise_false_merge, 12)
        self.assertEqual(disjoint.pairwise_false_split, 0)
        self.assertEqual(disjoint.pairwise_true_positive, 9)
        self.assertAlmostEqual(disjoint.wl_pairwise_precision, 9 / 21)
        self.assertEqual(disjoint.wl_pairwise_recall, 1.0)

    def test_exact_search_budget_fails_closed(self):
        with self.assertRaises(WLHardBenchmarkError):
            run_wl_hard_orbit_benchmark(max_candidate_bijections=5_039)

    def test_unknown_case_is_rejected(self):
        with self.assertRaises(WLHardBenchmarkError):
            build_wl_hard_state("unknown")


if __name__ == "__main__":
    unittest.main()
