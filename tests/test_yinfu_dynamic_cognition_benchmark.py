import unittest

from prototype.yinfu_dynamic_cognition_benchmark import (
    benchmark_yf07, benchmark_yf08, benchmark_yf09, benchmark_yf10, run,
)


class YinfuDynamicCognitionBenchmarkTests(unittest.TestCase):
    def test_yf07_reports_detection_and_null_control(self):
        result = benchmark_yf07(13, episodes=8)
        self.assertEqual(result["episodes"], 8)
        self.assertGreaterEqual(result["change_detection_rate"], 0.0)
        self.assertGreaterEqual(result["null_false_alarm_rate"], 0.0)

    def test_yf08_uses_independent_test_samples(self):
        result = benchmark_yf08(13, episodes=3)
        self.assertEqual(result["test_examples_per_episode"], 500)
        self.assertEqual(result["episodes"], 3)

    def test_yf09_includes_negative_controls(self):
        result = benchmark_yf09(13, episodes=10)
        self.assertIn("same_sign_false_reversal_rate", result)
        self.assertIn("zero_effect_false_reversal_rate", result)

    def test_yf10_compares_greedy_to_enumeration(self):
        result = benchmark_yf10(13, episodes=8)
        self.assertEqual(result["episodes"], 8)
        self.assertGreaterEqual(result["mean_greedy_regret"], 0.0)

    def test_suite_is_reproducible(self):
        self.assertEqual(run(seeds=1, start_seed=19), run(seeds=1, start_seed=19))

    def test_invalid_seed_count_rejected(self):
        with self.assertRaises(ValueError):
            run(seeds=0)


if __name__ == "__main__":
    unittest.main()
