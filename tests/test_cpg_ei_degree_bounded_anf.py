import copy
import json
import tempfile
import unittest
from pathlib import Path

from prototype.cpg_ei_anf_identifiability import truth_table_to_anf
from prototype.cpg_ei_degree_bounded_anf import (
    degree_bounded_basis, run_degree_bounded_identifiability,
    solve_gf2_restricted_basis, write_json_report,
)
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


class TestDegreeBoundedAnfIdentifiability(unittest.TestCase):
    def test_basis_cardinality_matches_binomial_sum(self):
        self.assertEqual(len(degree_bounded_basis(8, 0)), 1)
        self.assertEqual(len(degree_bounded_basis(8, 1)), 9)
        self.assertEqual(len(degree_bounded_basis(8, 2)), 37)
        self.assertEqual(len(degree_bounded_basis(8, 3)), 93)
        self.assertEqual(len(degree_bounded_basis(8, 4)), 163)
        self.assertEqual(len(degree_bounded_basis(8, 8)), 256)

    def test_degree_two_rule_is_uniquely_recovered_from_full_table(self):
        observations = []
        for mask in range(8):
            state = tuple((mask >> bit) & 1 for bit in range(3))
            target = state[0] ^ (state[1] & state[2])
            observations.append((state, target))
        basis = degree_bounded_basis(3, 2)
        system = solve_gf2_restricted_basis(3, observations, basis)
        self.assertTrue(system["consistent"])
        self.assertTrue(system["unique"])
        self.assertEqual(system["nullity"], 0)

    def test_lower_degree_basis_can_be_inconsistent(self):
        observations = []
        for mask in range(8):
            state = tuple((mask >> bit) & 1 for bit in range(3))
            observations.append((state, state[0] & state[1]))
        system = solve_gf2_restricted_basis(
            3, observations, degree_bounded_basis(3, 1)
        )
        self.assertFalse(system["consistent"])
        self.assertFalse(system["unique"])

    def test_duplicate_or_invalid_basis_is_rejected(self):
        rows = [((0, 0), 0), ((1, 1), 1)]
        with self.assertRaises(ValueError):
            solve_gf2_restricted_basis(2, rows, [0, 0])
        with self.assertRaises(ValueError):
            solve_gf2_restricted_basis(2, rows, [4])

    def test_locked_labels_do_not_change_training_identifiability(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=4, output_dim=3, seed=713
        )
        changed = copy.deepcopy(corpus)
        for row in changed["rows"]:
            if row["state_split"] == "locked":
                row["target"] = [1 - bit for bit in row["target"]]
        left = run_degree_bounded_identifiability(corpus)
        right = run_degree_bounded_identifiability(changed)
        for a, b in zip(left["degree_summaries"], right["degree_summaries"]):
            for key in ("max_degree", "basis_size", "output_systems", "mean_rank", "mean_nullity", "consistent_rate", "unique_rate"):
                self.assertEqual(a[key], b[key])

    def test_report_contains_fixed_corpus_digest(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=3, output_dim=2, seed=714
        )
        report = run_degree_bounded_identifiability(corpus)
        self.assertEqual(report["corpus_sha256"], corpus["manifest"]["corpus_sha256"])
        self.assertEqual(len(report["degree_summaries"]), 4)
        self.assertEqual(report["degree_summaries"][-1]["basis_size"], 8)
        self.assertEqual(report["degree_summaries"][-1]["consistent_rate"], 1.0)

    def test_report_is_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            write_json_report({"ok": True}, path)
            raw = path.read_text(encoding="utf-8")
            self.assertTrue(raw.endswith("\n"))
            self.assertEqual(json.loads(raw), {"ok": True})


if __name__ == "__main__":
    unittest.main()
