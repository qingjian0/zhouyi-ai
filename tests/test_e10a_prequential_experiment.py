import unittest

from prototype.e10a_prequential_experiment import run, run_all


class E10APrequentialExperimentTests(unittest.TestCase):
    def test_runner_persists_complete_query_lifecycle(self):
        result = run(seed=1302, mode="INCREMENTAL_FILTER", instances_per_template=2)
        self.assertGreater(result["query_observations"], 0)
        self.assertEqual(
            result["persisted_event_count"],
            1 + 5 * result["query_observations"],
        )
        self.assertGreaterEqual(result["coverage"], 0.0)
        self.assertLessEqual(result["coverage"], 1.0)
        self.assertGreaterEqual(result["abstention_rate"], 0.0)
        self.assertLessEqual(result["abstention_rate"], 1.0)

    def test_incremental_filter_and_batch_refit_have_same_final_space(self):
        result = run_all(seed=1303, instances_per_template=2)
        self.assertTrue(
            result["comparisons"]["incremental_equals_batch_final_version_space"]
        )
        self.assertEqual(
            result["comparisons"]["frozen_candidate_update_operations"], 0
        )
        self.assertGreater(
            result["comparisons"]["batch_candidate_update_operations"], 0
        )
        self.assertGreater(
            result["comparisons"]["incremental_candidate_update_operations"], 0
        )


if __name__ == "__main__":
    unittest.main()
