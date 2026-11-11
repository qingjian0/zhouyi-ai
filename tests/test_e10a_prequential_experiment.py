import unittest

from prototype.e10a_prequential_experiment import run, run_all, run_sweep
from prototype.e10a_object_disjoint import build_object_disjoint_task
from prototype.e10a_subprocess_learner import SubprocessRelationalVersionSpace


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
            result["arms"][1]["final_version_space_hashes"],
            result["arms"][2]["final_version_space_hashes"],
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


    def test_multi_seed_sweep_checks_exact_spaces_and_reports_distributions(self):
        result = run_sweep(start_seed=1400, seeds=3, instances_per_template=2)
        self.assertEqual(result["seeds"], 3)
        self.assertTrue(
            result["comparisons"]["batch_equals_incremental_exact_version_space_all_seeds"]
        )
        self.assertEqual(result["arms"]["FROZEN"]["coverage"]["n"], 3)
        self.assertEqual(len(result["comparisons"]["per_seed"]), 3)
        self.assertIsNotNone(
            result["comparisons"]["aggregate_incremental_to_batch_update_operation_ratio"]
        )


    def test_subprocess_backend_runs_prequential_lifecycle(self):
        result = run(
            seed=1501,
            mode="INCREMENTAL_FILTER",
            instances_per_template=2,
            learner_backend="subprocess",
        )
        self.assertEqual(result["learner_backend"], "subprocess")
        self.assertGreater(result["query_observations"], 0)
        self.assertEqual(
            result["persisted_event_count"],
            1 + 5 * result["query_observations"],
        )

    def test_hidden_truth_canary_does_not_change_learner_visible_bytes_or_output(self):
        import copy
        import json

        support, query, evaluator_truth = build_object_disjoint_task(
            1502, instances_per_template=2
        )
        altered_truth = copy.deepcopy(evaluator_truth)
        for row in altered_truth["query_truth"]:
            row["valid"] = not row["valid"]

        observation = query["observations"][0]
        object_map = {row["object_id"]: row for row in query["objects"]}
        current_objects = [
            object_map[object_id] for object_id in observation["participants"]
        ]
        learner_support = {
            key: support[key] for key in
            ("schema_version", "phase", "objects", "observations")
        }
        self.assertNotIn("mechanism_hash", learner_support)
        visible = {
            "support": learner_support,
            "observation": observation,
            "query_objects": current_objects,
        }
        # Evaluator truth is intentionally absent from the serialized IPC envelope.
        visible_after_truth_mutation = {
            "support": learner_support,
            "observation": observation,
            "query_objects": current_objects,
        }
        self.assertEqual(
            json.dumps(visible, sort_keys=True, separators=(",", ":")).encode(),
            json.dumps(visible_after_truth_mutation, sort_keys=True, separators=(",", ":")).encode(),
        )
        self.assertNotEqual(evaluator_truth["query_truth"], altered_truth["query_truth"])

        with SubprocessRelationalVersionSpace() as first, SubprocessRelationalVersionSpace() as second:
            first.fit(learner_support)
            second.fit(learner_support)
            prediction_a = first.predict(observation, current_objects)
            prediction_b = second.predict(observation, current_objects)
        self.assertEqual(prediction_a, prediction_b)


if __name__ == "__main__":
    unittest.main()
