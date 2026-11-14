import json
import os
import tempfile
import unittest

from prototype.yixiang_m56_executable_core import (
    SCHEMA_VERSION, TASK_FEATURES, audit_dataset, category_decision,
    generate_dataset, relation_preservation, revise_category,
    select_features_by_rule, task_shift_views, validate_case, write_dataset,
)


class M56ExecutableCoreTests(unittest.TestCase):
    def test_generator_is_reproducible(self):
        self.assertEqual(generate_dataset(count=60, seed=17),
                         generate_dataset(count=60, seed=17))

    def test_agent_view_contains_no_evaluator_truth(self):
        cases, truth = generate_dataset(count=60, seed=18)
        self.assertEqual(len(cases), len(truth))
        for case in cases:
            self.assertNotIn("evaluator_truth", case)
            self.assertNotIn("gold", case)
            validate_case(case)

    def test_truth_is_stored_in_separate_object(self):
        cases, truth = generate_dataset(count=90, seed=19)
        self.assertTrue(all("selected_features" in truth[c["case_id"]] for c in cases))
        self.assertTrue(all("selected_features" not in c for c in cases))

    def test_provenance_layers_are_explicit(self):
        cases, _ = generate_dataset(count=30, seed=20)
        for case in cases:
            for observation in case["observations"]:
                self.assertEqual(observation["provenance"]["text_layer"],
                                 "synthetic_observation")
                self.assertTrue(observation["evidence"])

    def test_validator_rejects_truth_leakage(self):
        cases, _ = generate_dataset(count=30, seed=21)
        leaked = dict(cases[0])
        leaked["evaluator_truth"] = {"class_member": True}
        with self.assertRaisesRegex(ValueError, "evaluator_truth_leakage"):
            validate_case(leaked)

    def test_task_conditioned_feature_selection_changes_with_purpose(self):
        cases, truth = generate_dataset(count=30, seed=22)
        views = task_shift_views(cases[0])
        selections = [select_features_by_rule(view) for view in views]
        self.assertEqual(len(set(selections)), 3)
        self.assertEqual(set(selections[0]), set(TASK_FEATURES["support_task"]))
        self.assertEqual(set(selections[1]), set(TASK_FEATURES["flow_task"]))
        self.assertEqual(set(selections[2]), set(TASK_FEATURES["containment_task"]))
        self.assertEqual(cases[0]["observations"], views[1]["observations"])

    def test_nuisance_does_not_enter_gold_relevant_features(self):
        cases, truth = generate_dataset(count=60, seed=23)
        for case in cases:
            relevant = truth[case["case_id"]]["selected_features"]
            self.assertNotIn("incidental_marker", relevant)
            self.assertNotIn("surface_color", relevant)
            self.assertNotIn("surface_shape", relevant)

    def test_spurious_nuisance_is_confined_to_declared_split_pattern(self):
        cases, truth = generate_dataset(count=300, seed=24,
                                        nuisance_mode="train_spurious")
        audit = audit_dataset(cases, truth)
        self.assertEqual(audit["nuisance_class_agreement"]["train"], 1.0)
        self.assertEqual(audit["nuisance_class_agreement"]["test"], 0.0)
        self.assertGreaterEqual(audit["nuisance_class_agreement"]["validation"], 0.25)
        self.assertLessEqual(audit["nuisance_class_agreement"]["validation"], 0.75)

    def test_independent_nuisance_is_not_perfect_shortcut(self):
        cases, truth = generate_dataset(count=300, seed=25)
        audit = audit_dataset(cases, truth)
        for split in ("train", "validation", "test"):
            agreement = audit["nuisance_class_agreement"][split]
            self.assertGreater(agreement, 0.25)
            self.assertLess(agreement, 0.75)

    def test_dataset_audit_reports_disjoint_split_counts(self):
        cases, truth = generate_dataset(count=200, seed=26)
        audit = audit_dataset(cases, truth)
        self.assertEqual(audit["cases"], 200)
        self.assertEqual(sum(audit["splits"].values()), 200)
        self.assertEqual(audit["public_truth_leaks"], 0)
        self.assertEqual(audit["task_count"], 3)

    def test_open_set_category_can_abstain(self):
        self.assertEqual(category_decision({}, ("capacity",)), "unknown")
        self.assertEqual(category_decision({"capacity": 0.9}, ("capacity",)), "member")
        self.assertEqual(category_decision({"capacity": 0.2}, ("capacity",)), "non_member")
        self.assertEqual(category_decision({"capacity": "high"}, ("capacity",)), "unknown")

    def test_relation_mapping_requires_direction_and_predicate(self):
        source = [{"source_role": "agent", "predicate": "supports",
                   "target_role": "object"}]
        good = [{"source_role": "actor", "predicate": "supports",
                 "target_role": "load"}]
        reversed_edge = [{"source_role": "load", "predicate": "supports",
                          "target_role": "actor"}]
        mapping = {"agent": "actor", "object": "load"}
        self.assertTrue(relation_preservation(source, good, mapping)["valid"])
        self.assertFalse(relation_preservation(source, reversed_edge, mapping)["valid"])

    def test_missing_role_mapping_is_rejected(self):
        source = [{"source_role": "agent", "predicate": "flows_to",
                   "target_role": "object"}]
        result = relation_preservation(source, [], {"agent": "actor"})
        self.assertFalse(result["valid"])

    def test_counterexample_narrows_only_affected_scope(self):
        hypothesis = {"version": 1, "scope": ["wood", "stone", "metal"],
                      "revision_history": []}
        revised = revise_category(
            hypothesis,
            {"case_id": "ce-1", "family": "wood",
             "violated_features": ["load_capacity"]},
        )
        self.assertEqual(revised["action"] if "action" in revised else
                         revised["revision_history"][-1]["action"], "narrow")
        self.assertEqual(revised["scope"], ["stone", "metal"])
        self.assertEqual(hypothesis["scope"], ["wood", "stone", "metal"])
        self.assertEqual(revised["version"], 2)

    def test_unscoped_counterexample_does_not_expand_or_destroy_class(self):
        hypothesis = {"version": 1, "scope": ["wood", "stone"],
                      "revision_history": []}
        revised = revise_category(
            hypothesis,
            {"case_id": "ce-2", "family": "glass",
             "violated_features": ["surface_similarity"]},
        )
        self.assertEqual(revised["scope"], ["wood", "stone"])
        self.assertEqual(revised["revision_history"][-1]["action"], "retain")

    def test_incomplete_counterexample_requests_more_evidence(self):
        revised = revise_category(
            {"version": 0, "scope": ["wood"], "revision_history": []},
            {"case_id": "ce-3", "family": "wood", "violated_features": []},
        )
        self.assertEqual(revised["revision_history"][-1]["action"],
                         "request_more_evidence")

    def test_public_and_truth_files_are_separate_parseable_outputs(self):
        cases, truth = generate_dataset(count=30, seed=27)
        with tempfile.TemporaryDirectory() as directory:
            paths = write_dataset(cases, truth, os.path.join(directory, "m56"))
            with open(paths["agent"], encoding="utf-8") as handle:
                decoded = [json.loads(line) for line in handle.read().splitlines()]
            with open(paths["evaluator"], encoding="utf-8") as handle:
                evaluator = json.load(handle)
            self.assertEqual(len(decoded), 30)
            self.assertEqual(set(item["case_id"] for item in decoded), set(evaluator))
            self.assertTrue(all("evaluator_truth" not in item for item in decoded))


if __name__ == "__main__":
    unittest.main()
