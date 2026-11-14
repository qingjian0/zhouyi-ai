import json
import os
import tempfile
import unittest

from prototype.yixiang_m55_1_repaired_study import (
    generate_scenario, run_cell, run_study, summarize, write_outputs,
)


class M551RepairedStudyTests(unittest.TestCase):
    def test_fixed_cardinality_baselines_do_not_follow_truth_cardinality(self):
        empty_truth, _ = run_cell("linear_null", 100, 7)
        two_parent_truth, _ = run_cell("nonlinear_interaction", 100, 7)
        by_name_empty = {row["method"]: row for row in empty_truth}
        by_name_two = {row["method"]: row for row in two_parent_truth}
        for method, expected_k in (
            ("random_k1", 1), ("correlation_k1", 1),
            ("random_k2", 2), ("correlation_k2", 2),
        ):
            self.assertEqual(len(by_name_empty[method]["predicted_parents"]), expected_k)
            self.assertEqual(len(by_name_two[method]["predicted_parents"]), expected_k)

    def test_reported_sample_size_is_training_size(self):
        rows, truth, metadata = generate_scenario(
            "linear_gaussian", train_n=120, seed=11
        )
        self.assertEqual(len(rows), 172)
        records, _ = run_cell("linear_gaussian", 120, 11)
        self.assertTrue(all(row["sample_size"] == 120 for row in records))
        self.assertTrue(all(row["train_sample_size"] == 120 for row in records))
        self.assertTrue(all(row["total_sample_size"] == 172 for row in records))

    def test_hidden_regime_is_randomized_and_not_in_agent_rows(self):
        rows, truth, metadata = generate_scenario(
            "mechanism_heterogeneity", train_n=1500, seed=101
        )
        regimes = metadata["hidden_regime_by_unit"]
        self.assertEqual(len(regimes), len(rows))
        self.assertTrue(all("regime" not in row for row in rows))
        self.assertTrue(all(set(row) == {"unit_id", "x", "z", "w", "y"} for row in rows))
        parity_matches = sum(regime == (unit_id % 2)
                             for unit_id, regime in enumerate(regimes))
        self.assertLess(parity_matches / len(regimes), 0.65)
        self.assertGreater(parity_matches / len(regimes), 0.35)

    def test_jsonl_is_physical_line_delimited_and_parseable(self):
        records, metadata = run_study(
            seeds=(2, 5), train_sample_sizes=(100,),
            scenarios=("linear_gaussian",),
        )
        report = summarize(records, bootstrap_repetitions=300)
        with tempfile.TemporaryDirectory() as directory:
            paths = write_outputs(records, metadata, report, directory)
            with open(paths["raw"], encoding="utf-8") as handle:
                lines = handle.read().splitlines()
            self.assertEqual(len(lines), len(records))
            decoded = [json.loads(line) for line in lines]
            self.assertEqual(len(decoded), len(records))
            self.assertTrue(all(row["train_sample_size"] == 100 for row in decoded))

    def test_small_study_has_complete_paired_method_cells(self):
        records, metadata = run_study(
            seeds=(3, 7, 9), train_sample_sizes=(100,),
            scenarios=("linear_gaussian", "linear_null"),
        )
        self.assertEqual(len(records), 2 * 1 * 3 * 5)
        report = summarize(records, bootstrap_repetitions=300)
        self.assertEqual(len(report["paired_f1_contrasts"]), 2 * 1 * 4)
        self.assertIn("exchangeability/symmetry", report["inference_note"])


if __name__ == "__main__":
    unittest.main()
