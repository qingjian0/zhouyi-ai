import copy
import unittest

from prototype.e10a_finite_relational_learner import (
    FiniteRelationalVersionSpace, RelationalLearnerError,
)
from prototype.e10a_object_disjoint import build_object_disjoint_task


class E10AFiniteRelationalLearnerTests(unittest.TestCase):
    def setUp(self):
        self.support, self.query, self.truth = build_object_disjoint_task(1201)
        self.truth_by_id = {
            row["observation_id"]: row["valid"]
            for row in self.truth["query_truth"]
        }
        self.query_object_map = {
            row["object_id"]: row for row in self.query["objects"]
        }

    def objects_for(self, observation):
        return [
            self.query_object_map[object_id]
            for object_id in observation["participants"]
        ]

    def test_fits_support_without_template_truth(self):
        learner = FiniteRelationalVersionSpace().fit(self.support)
        snapshot = learner.snapshot()
        self.assertEqual(snapshot["report"]["relation_count"], 2)
        self.assertGreater(snapshot["report"]["consistent_candidate_count"], 0)
        self.assertFalse(snapshot["report"]["target_template_labels_received"])
        self.assertFalse(snapshot["report"]["role_order_identified"])
        self.assertNotIn("templates", snapshot)

    def test_query_prediction_is_label_blind_and_abstention_is_explicit(self):
        learner = FiniteRelationalVersionSpace().fit(self.support)
        query_before = copy.deepcopy(self.query)
        statuses = set()
        for row in self.query["observations"]:
            result = learner.predict(row, self.objects_for(row))
            self.assertIn(result["decision_status"], {
                "PREDICT", "ABSTAIN_AMBIGUOUS", "ABSTAIN_INCONSISTENT",
            })
            if result["decision_status"] == "PREDICT":
                self.assertIs(type(result["prediction"]), bool)
                self.assertEqual(result["confidence"], 1.0)
            else:
                self.assertIsNone(result["prediction"])
                self.assertIsNone(result["confidence"])
            statuses.add(result["decision_status"])
        self.assertEqual(self.query, query_before)
        self.assertNotIn("outcome", self.query["observations"][0])

    def test_role_participant_order_is_permutation_invariant(self):
        learner = FiniteRelationalVersionSpace().fit(self.support)
        row = self.query["observations"][0]
        swapped = dict(row)
        swapped["participants"] = list(reversed(row["participants"]))
        left = learner.predict(row, self.objects_for(row))
        right = learner.predict(swapped, self.objects_for(swapped))
        self.assertEqual(left["prediction"], right["prediction"])
        self.assertEqual(left["decision_status"], right["decision_status"])

    def test_incremental_filter_and_batch_refit_have_identical_version_spaces(self):
        incremental = FiniteRelationalVersionSpace().fit(self.support)
        batch = FiniteRelationalVersionSpace().fit(self.support)
        for row in self.query["observations"]:
            label = self.truth_by_id[row["observation_id"]]
            inc = incremental.update(
                row, label, self.objects_for(row), mode="INCREMENTAL_FILTER"
            )
            bat = batch.update(
                row, label, self.objects_for(row), mode="BATCH_REFIT"
            )
            self.assertEqual(
                incremental.snapshot()["version_spaces"],
                batch.snapshot()["version_spaces"],
            )
            self.assertEqual(inc["after_candidate_count"], bat["after_candidate_count"])
        self.assertEqual(
            incremental.snapshot()["version_spaces"],
            batch.snapshot()["version_spaces"],
        )

    def test_frozen_control_does_not_change_version_space(self):
        learner = FiniteRelationalVersionSpace().fit(self.support)
        before = learner.snapshot()["version_spaces"]
        row = self.query["observations"][0]
        learner.update(
            row, self.truth_by_id[row["observation_id"]],
            self.objects_for(row), mode="FROZEN",
        )
        self.assertEqual(learner.snapshot()["version_spaces"], before)

    def test_query_payload_rejects_hidden_truth_fields(self):
        learner = FiniteRelationalVersionSpace().fit(self.support)
        row = dict(self.query["observations"][0])
        row["valid"] = True
        with self.assertRaisesRegex(RelationalLearnerError, "evaluator-only"):
            learner.predict(row, self.query["objects"])

    def test_future_query_objects_are_not_available_to_current_prediction(self):
        learner = FiniteRelationalVersionSpace().fit(self.support)
        first = self.query["observations"][0]
        first_ids = set(first["participants"])
        current_objects = self.objects_for(first)
        learner.predict(first, current_objects)

        future = next(
            row for row in self.query["observations"][1:]
            if not set(row["participants"]) <= first_ids
        )
        with self.assertRaisesRegex(RelationalLearnerError, "unknown Query object"):
            learner.predict(future, current_objects)

    def test_candidate_budget_fails_closed(self):
        with self.assertRaisesRegex(RelationalLearnerError, "budget"):
            FiniteRelationalVersionSpace(max_candidates=1).fit(self.support)


if __name__ == "__main__":
    unittest.main()
