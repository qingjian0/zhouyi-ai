import unittest

from prototype.tx02_experiment import aggregate_runs, choose_hidden_size_for_budget, model_parameter_count, run_sweep


class TX02ExperimentTests(unittest.TestCase):
    def test_small_sweep_records_all_families_and_audit(self):
        result = run_sweep(
            cardinalities=(2,), support_sizes=(1,), seeds=(3,),
            episodes_per_rule=1, epochs=1, hidden_size=3,
        )
        condition = result["conditions"][0]
        self.assertEqual(set(condition["aggregate"]), {
            "BINARY", "TERNARY", "HYBRID", "ONE_HOT", "LEARNED", "FIXED_RANDOM", "PERMUTED"
        })
        for family in condition["runs"][0]["families"].values():
            self.assertIn("query_accuracy", family["locked_test"])
            self.assertGreaterEqual(family["locked_test"]["audited_episodes"], 1)
            self.assertGreater(family["fit"]["parameter_count"], 0)

    def test_parameter_budget_selection_respects_shared_upper_bound(self):
        target = max(
            model_parameter_count(family, 3, 8, 6)
            for family in ("BINARY", "TERNARY", "HYBRID", "ONE_HOT", "LEARNED", "FIXED_RANDOM", "PERMUTED")
        )
        for family in ("BINARY", "TERNARY", "HYBRID", "ONE_HOT", "LEARNED", "FIXED_RANDOM", "PERMUTED"):
            hidden, count = choose_hidden_size_for_budget(family, 3, target, 6)
            self.assertGreaterEqual(hidden, 1)
            self.assertLessEqual(count, target)
            self.assertEqual(count, model_parameter_count(family, 3, hidden, 6))

    def test_budget_below_minimum_model_is_rejected(self):
        with self.assertRaises(ValueError):
            choose_hidden_size_for_budget("HYBRID", 3, 1, 6)

    def test_parameter_matched_sweep_reports_hidden_sizes_and_deltas(self):
        result = run_sweep(
            cardinalities=(2,), support_sizes=(1,), seeds=(5,),
            episodes_per_rule=1, epochs=1, hidden_size=3,
            parameter_matched=True,
        )
        families = result["conditions"][0]["runs"][0]["families"]
        self.assertIn("FIXED_RANDOM", families)
        budgets = {item["target_parameter_budget"] for item in families.values()}
        self.assertEqual(len(budgets), 1)
        for item in families.values():
            self.assertLessEqual(item["parameter_budget_delta"], 0)

    def test_support_must_leave_unseen_query_pair(self):
        with self.assertRaises(ValueError):
            run_sweep(cardinalities=(2,), support_sizes=(4,), seeds=(1,))

    def test_aggregate_reports_seed_dispersion(self):
        runs = []
        for value in (0.25, 0.75):
            runs.append({"families": {
                family: {"locked_test": {"query_accuracy": value},
                         "fit": {"parameter_count": 10}}
                for family in ("BINARY", "TERNARY", "HYBRID", "ONE_HOT", "LEARNED", "FIXED_RANDOM", "PERMUTED")
            }})
        result = aggregate_runs(runs)
        self.assertEqual(result["TERNARY"]["mean_query_accuracy"], 0.5)
        self.assertGreater(result["TERNARY"]["stdev_query_accuracy"], 0.0)


if __name__ == "__main__":
    unittest.main()
