import unittest

from benchmarks.benchmark_n010_model_compute import build_examples, throughput


class N010ModelComputeBenchmarkTests(unittest.TestCase):
    def test_builds_balanced_three_role_parity_examples(self):
        examples = build_examples(16)
        self.assertEqual(len(examples), 16)
        self.assertEqual(sum(row.label == 1 for row in examples), 8)
        self.assertEqual(sum(row.label == -1 for row in examples), 8)
        self.assertEqual(len(examples[0].assignment), 3)

    def test_rejects_unbalanced_size(self):
        with self.assertRaises(ValueError):
            build_examples(10)

    def test_reports_example_epoch_rate(self):
        self.assertEqual(
            throughput(100, 5, 2.0),
            {
                "training_example_epochs_per_second": 250.0,
                "training_epochs_per_second": 2.5,
            },
        )

    def test_rejects_nonpositive_elapsed_time(self):
        with self.assertRaises(ValueError):
            throughput(100, 5, 0.0)


if __name__ == "__main__":
    unittest.main()
