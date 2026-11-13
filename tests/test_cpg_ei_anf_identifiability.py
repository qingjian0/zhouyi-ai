import copy
import json
import tempfile
import unittest
from pathlib import Path

from prototype.cpg_ei_anf_identifiability import (
    evaluate_anf,
    run_anf_identifiability_audit,
    solve_gf2_affine_system,
    truth_table_to_anf,
    write_json_report,
)
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_relation_operators import RelationRule, evaluate_rule


class TestAnfIdentifiability(unittest.TestCase):
    def _truth_coefficients(self, input_dim, rule):
        outputs = []
        for mask in range(1 << input_dim):
            state = tuple((mask >> index) & 1 for index in range(input_dim))
            outputs.append(evaluate_rule(state, rule))
        return truth_table_to_anf(input_dim, outputs)

    def test_round_trip_known_operators(self):
        rules = [
            RelationRule("xor", (0, 2)),
            RelationRule("and", (0, 1, 2)),
            RelationRule("or", (0, 1)),
            RelationRule("nand", (0, 1)),
            RelationRule("implies", (0, 2)),
            RelationRule("threshold", (0, 1, 2), threshold=2),
            RelationRule("conditional_xor", (0, 1), context_index=2, context_value=1),
        ]
        for rule in rules:
            with self.subTest(rule=rule):
                coefficients = self._truth_coefficients(3, rule)
                for mask in range(1 << 3):
                    state = tuple((mask >> index) & 1 for index in range(3))
                    self.assertEqual(
                        evaluate_anf(state, coefficients),
                        evaluate_rule(state, rule),
                    )

    def test_full_truth_table_produces_unique_system(self):
        input_dim = 3
        rule = RelationRule("conditional_xor", (0, 1), context_index=2)
        observations = []
        for mask in range(1 << input_dim):
            state = tuple((mask >> index) & 1 for index in range(input_dim))
            observations.append((state, evaluate_rule(state, rule)))
        system = solve_gf2_affine_system(input_dim, observations)
        self.assertTrue(system["consistent"])
        self.assertTrue(system["unique"])
        self.assertEqual(system["rank"], 1 << input_dim)
        self.assertEqual(system["nullity"], 0)

    def test_partial_observations_report_affine_ambiguity(self):
        observations = [
            ((0, 0, 0), 0),
            ((0, 1, 0), 0),
            ((0, 0, 1), 0),
            ((0, 1, 1), 0),
        ]
        system = solve_gf2_affine_system(3, observations)
        self.assertTrue(system["consistent"])
        self.assertFalse(system["unique"])
        self.assertEqual(system["nullity"], 4)
        self.assertEqual(len(system["nullspace_basis"]), 4)

    def test_inconsistent_observations_are_rejected_as_no_solution(self):
        observations = [((0, 0), 0), ((0, 0), 1)]
        system = solve_gf2_affine_system(2, observations)
        self.assertFalse(system["consistent"])
        self.assertIsNone(system["particular_solution"])

    def test_solver_is_invariant_to_observation_order(self):
        rows = [
            ((0, 0, 0), 0), ((1, 0, 0), 1),
            ((0, 1, 0), 1), ((1, 1, 0), 0),
            ((0, 0, 1), 1), ((1, 0, 1), 0),
        ]
        forward = solve_gf2_affine_system(3, rows)
        reverse = solve_gf2_affine_system(3, list(reversed(rows)))
        self.assertEqual(forward["rank"], reverse["rank"])
        self.assertEqual(forward["nullity"], reverse["nullity"])
        self.assertEqual(forward["coefficient_status"], reverse["coefficient_status"])

    def test_corpus_audit_separates_oracle_and_train_only_solver(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=3, output_dim=7, seed=711
        )
        report = run_anf_identifiability_audit(corpus)
        self.assertEqual(report["corpus_sha256"], corpus["manifest"]["corpus_sha256"])
        self.assertEqual(report["training_identifiability_summary"]["output_systems"], 35)
        self.assertEqual(report["training_identifiability_summary"]["unique_training_anf_rate"], 0.0)
        self.assertEqual(report["training_identifiability_summary"]["mean_nullity"], 4.0)
        self.assertTrue(all(
            output["oracle_support_is_contained_in_possible_support"]
            for family in report["family_results"]
            for output in family["output_results"]
        ))

    def test_locked_label_mutation_does_not_change_training_identifiability(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=4, output_dim=7, seed=711
        )
        changed = copy.deepcopy(corpus)
        for row in changed["rows"]:
            if row["state_split"] == "locked":
                row["target"] = [1 - value for value in row["target"]]
        left = run_anf_identifiability_audit(corpus)
        right = run_anf_identifiability_audit(changed)
        left_train = [
            (o["system_rank"], o["system_nullity"], o["training_identifiability"])
            for f in left["family_results"] for o in f["output_results"]
        ]
        right_train = [
            (o["system_rank"], o["system_nullity"], o["training_identifiability"])
            for f in right["family_results"] for o in f["output_results"]
        ]
        self.assertEqual(left_train, right_train)

    def test_report_is_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            write_json_report({"ok": True}, path)
            raw = path.read_text(encoding="utf-8")
            self.assertTrue(raw.endswith("\n"))
            self.assertEqual(json.loads(raw), {"ok": True})


if __name__ == "__main__":
    unittest.main()
