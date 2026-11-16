import unittest

from prototype.cpg_ei_context_coverage_sweep import run_context_coverage_sweep


class ConditionalContextCoverageSweepTests(unittest.TestCase):
    def test_sweep_is_deterministic_and_reports_all_sampling_levels(self):
        first = run_context_coverage_sweep(seeds=(11, 23), sample_fractions=(0.25, 1.0))
        second = run_context_coverage_sweep(seeds=(11, 23), sample_fractions=(0.25, 1.0))
        self.assertEqual(first, second)
        self.assertEqual(set(first["by_sample_fraction"]), {"0.25", "1.0"})
        self.assertEqual(first["by_sample_fraction"]["1.0"]["mean_support_recall"], 1.0)

    def test_inactive_context_adversary_is_explicitly_inconclusive(self):
        report = run_context_coverage_sweep(seeds=(11,), sample_fractions=(1.0,))
        adversary = report["adversarial_inactive_context"]
        self.assertEqual(adversary["sample_size"], 8)
        self.assertEqual(adversary["inferred_support"], [])
        self.assertEqual(adversary["support_recall"], 0.0)
        self.assertEqual(adversary["x0_status"], "no_influence_observed_inconclusive")
        self.assertEqual(adversary["x3_status"], "unobserved_counterpart")


if __name__ == "__main__":
    unittest.main()
