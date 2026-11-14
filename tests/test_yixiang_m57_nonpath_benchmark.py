import json
import os
import tempfile
import unittest

from prototype.yixiang_m57_nonpath_benchmark import (
    LEVELS, audit_dataset, check_mapping, evaluate_prediction,
    generate_dataset, validate_case, write_dataset,
)


class M57NonPathBenchmarkTests(unittest.TestCase):
    def test_reproducible_and_truth_is_separate(self):
        first = generate_dataset(count=60, seed=5702)
        self.assertEqual(first, generate_dataset(count=60, seed=5702))
        cases, truth = first
        self.assertEqual(len(cases), len(truth))
        for case in cases:
            self.assertNotIn("correct_candidate_id", case)
            self.assertNotIn("evaluator_truth", case)
            validate_case(case)

    def test_all_difficulty_levels_are_real_structural_variants(self):
        cases, truth = generate_dataset(count=90, seed=5703)
        self.assertEqual({case["difficulty"] for case in cases}, set(LEVELS))
        by_level = {level: next(c for c in cases if c["difficulty"] == level)
                    for level in LEVELS}
        self.assertEqual(len(by_level["basic"]["pattern"]["hyperedges"]), 0)
        self.assertGreater(len(by_level["compositional"]["pattern"]["hyperedges"]), 0)
        nonpath = by_level["nonpath"]["pattern"]
        self.assertGreaterEqual(len(nonpath["hyperedges"]), 2)
        self.assertTrue(nonpath["global_counts"])
        self.assertTrue(nonpath["forbidden_relations"])

    def test_planted_candidate_is_unique_and_valid(self):
        cases, truth = generate_dataset(count=60, seed=5704)
        for case in cases:
            expected = truth[case["case_id"]]["correct_candidate_id"]
            self.assertTrue(evaluate_prediction(case, expected)["accepted"])
            self.assertEqual(truth[case["case_id"]]["valid_candidate_count"], 1)

    def test_every_decoy_candidate_fails_at_least_one_constraint(self):
        cases, truth = generate_dataset(count=60, seed=5705)
        for case in cases:
            expected = truth[case["case_id"]]["correct_candidate_id"]
            for index in range(len(case["candidate_mappings"])):
                candidate_id = "candidate-" + str(index)
                if candidate_id != expected:
                    self.assertFalse(evaluate_prediction(case, candidate_id)["accepted"])

    def test_nonpath_constraints_are_not_reduced_to_binary_paths(self):
        cases, truth = generate_dataset(count=60, seed=5706)
        case = next(c for c in cases if c["difficulty"] == "nonpath")
        mapping = case["candidate_mappings"][int(truth[case["case_id"]]["correct_candidate_id"].split("-")[1])]
        pattern = case["pattern"]
        self.assertTrue(pattern["hyperedges"])
        self.assertTrue(pattern["global_counts"])
        target_edges = {
            (edge["source"], edge["predicate"], edge["target"])
            for edge in case["target_graph"]["binary_relations"]
        }
        # Every candidate in the hard non-path condition passes all binary
        # relation checks; hyperedges/global constraints must break the tie.
        for candidate in case["candidate_mappings"]:
            for edge in pattern["binary_relations"]:
                self.assertIn((candidate[edge["source"]], edge["predicate"],
                               candidate[edge["target"]]), target_edges)
        full_valid = [
            i for i, candidate in enumerate(case["candidate_mappings"])
            if check_mapping(pattern, case["target_graph"], candidate)["valid"]
        ]
        self.assertEqual(len(full_valid), 1)
        self.assertTrue(check_mapping(pattern, case["target_graph"], mapping)["valid"])

    def test_rejects_non_injective_mapping(self):
        cases, _ = generate_dataset(count=60, seed=5707)
        case = cases[0]
        mapping = dict(case["candidate_mappings"][0])
        roles = case["pattern"]["roles"]
        mapping[roles[1]] = mapping[roles[0]]
        result = check_mapping(case["pattern"], case["target_graph"], mapping)
        self.assertFalse(result["valid"])
        self.assertIn("injectivity", result["violations"])

    def test_rejects_evaluator_truth_leak(self):
        cases, _ = generate_dataset(count=60, seed=5708)
        leaked = dict(cases[0])
        leaked["correct_candidate_id"] = "candidate-0"
        with self.assertRaisesRegex(ValueError, "evaluator_truth_leakage"):
            validate_case(leaked)

    def test_split_and_difficulty_audit(self):
        cases, truth = generate_dataset(count=90, seed=5709)
        report = audit_dataset(cases, truth)
        self.assertEqual(report["cases"], 90)
        self.assertEqual(sum(report["split_counts"].values()),90)
        self.assertTrue(report["unique_valid_mapping_per_case"])

    def test_jsonl_and_evaluator_outputs_are_separate(self):
        cases, truth = generate_dataset(count=30, seed=5710)
        with tempfile.TemporaryDirectory() as directory:
            paths = write_dataset(cases, truth, os.path.join(directory, "m57"))
            with open(paths["agent"], encoding="utf-8") as handle:
                decoded = [json.loads(line) for line in handle.read().splitlines()]
            with open(paths["evaluator"], encoding="utf-8") as handle:
                labels = json.load(handle)
            self.assertEqual(len(decoded), 30)
            self.assertEqual(set(labels), {case["case_id"] for case in decoded})


if __name__ == "__main__":
    unittest.main()
