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

    def test_degree_limited_basis_recovers_representable_functions(self):
        input_dim = 3
        rule = RelationRule("xor", (0, 2))
        observations = []
        for mask in range(1 << input_dim):
            state = tuple((mask >> index) & 1 for index in range(input_dim))
            observations.append((state, evaluate_rule(state, rule)))
        linear = solve_gf2_affine_system(input_dim, observations, max_degree=1)
        constant = solve_gf2_affine_system(input_dim, observations, max_degree=0)
        self.assertTrue(linear["consistent"])
        self.assertTrue(linear["unique"])
        self.assertEqual(linear["coefficient_count"], 4)
        self.assertFalse(constant["consistent"])

    def test_degree_sweep_reports_basis_rank_and_oracle_coverage(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=3, output_dim=7, seed=711
        )
        report = run_anf_identifiability_audit(corpus)
        sweep = report["degree_sweep"]["degree_results"]
        self.assertEqual(
            [item["basis_coefficient_count"] for item in sweep],
            [1, 4, 7, 8],
        )
        self.assertEqual(sweep[-1]["oracle_representability_rate"], 1.0)
        self.assertEqual(sweep[-1]["mean_training_rank"], 4.0)
        self.assertEqual(sweep[-1]["mean_training_nullity"], 4.0)
        self.assertEqual(sweep[-1]["output_system_count"], 35)
        self.assertLessEqual(
            sweep[0]["oracle_representability_rate"],
            sweep[-1]["oracle_representability_rate"],
        )
        for degree_result in sweep:
            consistent_nullities = [
                item["nullity"] for item in degree_result["per_output"]
                if item["training_system_consistent"]
            ]
            expected_mean = (
                sum(consistent_nullities) / len(consistent_nullities)
                if consistent_nullities else None
            )
            self.assertEqual(degree_result["mean_training_nullity"], expected_mean)
            self.assertEqual(
                degree_result["consistent_system_count"]
                + degree_result["inconsistent_system_count"],
                degree_result["output_system_count"],
            )

    def test_invalid_degree_bound_is_rejected(self):
        with self.assertRaises(ValueError):
            solve_gf2_affine_system(3, [((0, 0, 0), 0)], max_degree=4)

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
        left_sweep = left["degree_sweep"]["degree_results"]
        right_sweep = right["degree_sweep"]["degree_results"]
        for left_degree, right_degree in zip(left_sweep, right_sweep):
            left_training = [
                (item["training_system_consistent"], item["rank"], item["nullity"],
                 item["unique"], item["possible_support"])
                for item in left_degree["per_output"]
            ]
            right_training = [
                (item["training_system_consistent"], item["rank"], item["nullity"],
                 item["unique"], item["possible_support"])
                for item in right_degree["per_output"]
            ]
            self.assertEqual(left_training, right_training)

    def test_report_is_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            write_json_report({"ok": True}, path)
            raw = path.read_text(encoding="utf-8")
            self.assertTrue(raw.endswith("\n"))
            self.assertEqual(json.loads(raw), {"ok": True})


if __name__ == "__main__":
    unittest.main()
