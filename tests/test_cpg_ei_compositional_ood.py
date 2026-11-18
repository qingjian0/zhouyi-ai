import copy
import itertools
import unittest

from prototype.cpg_ei_compositional_ood import (
    generate_compositional_corpus,
    run_compositional_ood_benchmark,
    run_symbolic_baseline,
)
from prototype.cpg_ei_compute_accounted_hybrid import derive_train_only_support_features
from prototype.cpg_ei_mixed_operator_discovery import enumerate_rule_hypotheses
from prototype.cpg_ei_relation_operators import evaluate_rule


class TestCompositionalOOD(unittest.TestCase):
    def test_generator_is_deterministic_and_covers_disjoint_state_splits(self):
        first = generate_compositional_corpus(
            family_count=5, input_dim=4, output_dim=2, seed=17
        )
        second = generate_compositional_corpus(
            family_count=5, input_dim=4, output_dim=2, seed=17
        )
        self.assertEqual(first, second)
        self.assertEqual(first["manifest"]["row_count"], 5 * 16)
        for family_id in {row["family_id"] for row in first["rows"]}:
            rows = [row for row in first["rows"] if row["family_id"] == family_id]
            self.assertEqual(len({tuple(row["state"]) for row in rows}), 16)
            self.assertEqual(
                {split: sum(row["state_split"] == split for row in rows)
                 for split in ("train", "development", "locked")},
                {"train": 8, "development": 4, "locked": 4},
            )

    def test_hybrid_support_selection_ignores_development_and_locked_labels(self):
        corpus = generate_compositional_corpus(
            family_count=5, input_dim=4, output_dim=2, seed=23
        )
        changed = copy.deepcopy(corpus)
        for row in changed["rows"]:
            if row["state_split"] != "train":
                row["target"] = [1 - bit for bit in row["target"]]
        original = derive_train_only_support_features(corpus)
        mutated = derive_train_only_support_features(changed)
        self.assertEqual(original["family_features"], mutated["family_features"])

    def test_symbolic_selection_ignores_locked_labels(self):
        corpus = generate_compositional_corpus(
            family_count=5, input_dim=4, output_dim=2, seed=29
        )
        changed = copy.deepcopy(corpus)
        for row in changed["rows"]:
            if row["state_split"] == "locked":
                row["target"] = [1 - bit for bit in row["target"]]
        original = run_symbolic_baseline(corpus)
        mutated = run_symbolic_baseline(changed)
        self.assertEqual(
            [x["selected_rules"] for x in original["family_results"]],
            [x["selected_rules"] for x in mutated["family_results"]],
        )

    def test_three_way_benchmark_reports_operator_grammar_ood_boundary(self):
        report = run_compositional_ood_benchmark(
            seeds=(31, 47), family_count=5, input_dim=4,
            output_dim=2, max_epochs=4, patience=2,
        )
        self.assertEqual(report["dataset"]["total_teacher_families"], 10)
        self.assertEqual(report["dataset"]["total_rows"], 10 * 16)
        self.assertEqual(
            set(report["results"]),
            {"symbolic", "full_polynomial", "symbolic_support_hybrid"},
        )
        self.assertIn("not held-out-family zero-shot transfer", report["protocol"])

    def test_composed_teacher_functions_are_outside_single_operator_grammar(self):
        corpus = generate_compositional_corpus(
            family_count=5, input_dim=4, output_dim=2, seed=19
        )
        states = tuple(itertools.product((0, 1), repeat=4))
        grammar_functions = {
            tuple(evaluate_rule(state, rule) for state in states)
            for rule in enumerate_rule_hypotheses(4)
        }
        for teacher in corpus["teachers"]:
            for rule in teacher["rules"]:
                a, b = rule["left_support"]
                c, d = rule["right_support"]
                target = tuple(
                    (state[a] & state[b]) ^ (state[c] & state[d])
                    for state in states
                )
                self.assertNotIn(target, grammar_functions)


if __name__ == "__main__":
    unittest.main()
