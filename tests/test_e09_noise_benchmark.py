import unittest

from prototype.e09_noise_benchmark import run, run_sweep


class E09NoiseBenchmarkTests(unittest.TestCase):
    def test_train_and_test_assignments_are_disjoint(self):
        result = run(seed=7, noise_rate=0.0)
        metrics = result["result"]
        self.assertEqual(metrics["train_size"] + metrics["test_size"], 27)
        self.assertEqual(metrics["train_size"], 18)
        self.assertEqual(metrics["test_size"], 9)
        self.assertEqual(result["learner_snapshot"]["report"]["gradient_updates"], 0)

    def test_noise_sweep_is_reproducible_and_has_control_arm(self):
        first = run_sweep(seeds=2, start_seed=31)
        second = run_sweep(seeds=2, start_seed=31)
        self.assertEqual(first, second)
        self.assertEqual(len(first["rows"]), 8)
        self.assertEqual(
            sorted({row["noise_rate"] for row in first["rows"]}),
            [0.0, 0.05, 0.10, 0.20],
        )
        self.assertEqual(
            {row["shortcut_enabled"] for row in first["rows"]},
            {True, False},
        )

    def test_rejects_invalid_noise_rate(self):
        with self.assertRaises(ValueError):
            run(noise_rate=1.1)


if __name__ == "__main__":
    unittest.main()
