import unittest

from prototype.recurrent_benchmark import BenchmarkConfig
from prototype.recurrent_length_sweep import run_length_sweep


class RecurrentLengthSweepTests(unittest.TestCase):
    def test_sweep_reports_all_models_at_each_heldout_gap(self):
        report = run_length_sweep(
            BenchmarkConfig(
                task="delayed_copy", train_examples=4, eval_examples=3,
                epochs=1, seed=19, payload_length=2, gap_length=3,
            ),
            eval_gap_lengths=(3, 9),
            seeds=(19, 20),
        )
        self.assertEqual(report["eval_gap_lengths"], [3, 9])
        self.assertEqual(len(report["raw_results"]), 12)
        self.assertEqual(len(report["summary"]), 6)
        for row in report["summary"]:
            self.assertEqual(row["seeds"], 2)
            self.assertEqual(row["parameter_counts"], [29])
            self.assertTrue(row["chunk_state_parity_all"])
        by_length = {
            gap: [
                row for row in report["raw_results"]
                if row["eval_gap_length"] == gap
            ]
            for gap in (3, 9)
        }
        self.assertEqual(
            {row["evaluation_context_symbols"] for row in by_length[3]},
            {3 * 14},
        )
        self.assertEqual(
            {row["evaluation_context_symbols"] for row in by_length[9]},
            {3 * 20},
        )

    def test_rejects_non_gap_tasks_and_duplicate_lengths(self):
        with self.assertRaises(ValueError):
            run_length_sweep(BenchmarkConfig(task="periodic"), (4, 8), seeds=(1,))
        with self.assertRaises(ValueError):
            run_length_sweep(BenchmarkConfig(), (4, 4), seeds=(1,))


if __name__ == "__main__":
    unittest.main()
