import copy
import unittest

from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_mixed_operator_discovery import (
    _truth_mask,
    enumerate_rule_hypotheses,
    run_discovery_benchmark,
)
from prototype.cpg_ei_relation_operators import RelationRule


class TestMixedOperatorDiscoveryBaseline(unittest.TestCase):
    def test_hypothesis_space_contains_all_generated_teacher_rules(self):
        corpus = generate_mixed_corpus(
            family_count=7, input_dim=4, output_dim=7, seed=91
        )
        candidates = {
            (
                rule.operator, rule.support, rule.threshold,
                rule.context_index, rule.context_value,
            )
            for rule in enumerate_rule_hypotheses(4)
        }
        for teacher in corpus["teachers"]:
            for spec in teacher["rules"]:
                key = (
                    spec["operator"], tuple(spec["support"]), spec["threshold"],
                    spec["context_index"],
                    spec["context_value"] if spec["context_value"] is not None else 1,
                )
                self.assertIn(key, candidates)

    def test_and_or_are_semantically_aliased_by_threshold(self):
        self.assertEqual(
            _truth_mask(RelationRule("and", (0, 1)), 2),
            _truth_mask(RelationRule("threshold", (0, 1), threshold=2), 2),
        )
        self.assertEqual(
            _truth_mask(RelationRule("or", (0, 1)), 2),
            _truth_mask(RelationRule("threshold", (0, 1), threshold=1), 2),
        )

    def test_discovery_report_separates_semantic_and_structural_recovery(self):
        corpus = generate_mixed_corpus(
            family_count=10, input_dim=4, output_dim=7, seed=123
        )
        report = run_discovery_benchmark(corpus)
        self.assertGreater(report["candidate_hypothesis_count"], 0)
        self.assertGreater(report["candidate_truth_function_count"], 0)
        self.assertEqual(
            report["candidate_structural_alias_count"],
            report["candidate_hypothesis_count"] - report["candidate_truth_function_count"],
        )
        self.assertEqual(report["family_split_results"]["train"]["families"], 6)
        self.assertEqual(report["family_split_results"]["development"]["families"], 2)
        self.assertEqual(report["family_split_results"]["locked"]["families"], 2)
        for split in report["family_split_results"].values():
            if split["outputs"]:
                self.assertTrue(0.0 <= split["mean_locked_bit_accuracy"] <= 1.0)
                self.assertTrue(0.0 <= split["operator_recovery_rate"] <= 1.0)
                self.assertTrue(0.0 <= split["teacher_function_identifiability_rate"] <= 1.0)
        self.assertEqual(len(report["family_results"]), 10)
        for family in report["family_results"]:
            for output in family["output_results"]:
                self.assertGreaterEqual(output["teacher_function_equivalence_class_size"], 1)
                self.assertGreaterEqual(output["selected_function_equivalence_class_size"], 1)
                self.assertEqual(
                    output["teacher_function_structurally_identifiable"],
                    output["teacher_function_equivalence_class_size"] == 1,
                )

    def test_locked_labels_do_not_change_selected_hypotheses(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=4, output_dim=7, seed=77
        )
        changed = copy.deepcopy(corpus)
        for row in changed["rows"]:
            if row["state_split"] == "locked":
                row["target"] = [1 - value for value in row["target"]]
        original_report = run_discovery_benchmark(corpus)
        changed_report = run_discovery_benchmark(changed)
        for original_family, changed_family in zip(
            original_report["family_results"], changed_report["family_results"]
        ):
            for original_output, changed_output in zip(
                original_family["output_results"], changed_family["output_results"]
            ):
                self.assertEqual(
                    original_output["selected_rule"],
                    changed_output["selected_rule"],
                )

    def test_invalid_dimension_rejected(self):
        with self.assertRaises(ValueError):
            enumerate_rule_hypotheses(2)


if __name__ == "__main__":
    unittest.main()
