import unittest

from prototype.tx02_experiment import aggregate_runs, run_sweep


class TX02ExperimentTests(unittest.TestCase):
    def test_small_sweep_records_all_families_and_audit(self):
        result = run_sweep(
            cardinalities=(2,), support_sizes=(1,), seeds=(3,),
            episodes_per_rule=1, epochs=1, hidden_size=3,
        )
        condition = result["conditions"][0]
        self.assertEqual(set(condition["aggregate"]), {
            "BINARY", "TERNARY", "HYBRID", "ONE_HOT", "LEARNED", "PERMUTED"
        })
        for family in condition["runs"][0]["families"].values():
            self.assertIn("query_accuracy", family["locked_test"])
            self.assertGreaterEqual(family["locked_test"]["audited_episodes"], 1)
            self.assertGreater(family["fit"]["parameter_count"], 0)

    def test_support_must_leave_unseen_query_pair(self):
        with self.assertRaises(ValueError):
            run_sweep(cardinalities=(2,), support_sizes=(4,), seeds=(1,))

    def test_aggregate_reports_seed_dispersion(self):
        runs = []
        for value in (0.25, 0.75):
            runs.append({"families": {
                family: {"locked_test": {"query_accuracy": value},
                         "fit": {"parameter_count": 10}}
                for family in ("BINARY", "TERNARY", "HYBRID", "ONE_HOT", "LEARNED", "PERMUTED")
            }})
        result = aggregate_runs(runs)
        self.assertEqual(result["TERNARY"]["mean_query_accuracy"], 0.5)
        self.assertGreater(result["TERNARY"]["stdev_query_accuracy"], 0.0)


if __name__ == "__main__":
    unittest.main()
