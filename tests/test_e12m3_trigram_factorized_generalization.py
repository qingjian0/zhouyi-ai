import unittest

from prototype.e12m3_trigram_factorized_generalization import (
    FAMILY_SIZE, AffineRule, PairObservation, _gf2_rank, affine_rules,
    evaluate_episode, infer_affine_rule, lookup_predict, make_episode, run_benchmark,
)


class TrigramFactorizedGeneralizationTests(unittest.TestCase):
    def test_affine_rule_family_size(self):
        rules = affine_rules()
        self.assertEqual(len(rules), FAMILY_SIZE)
        self.assertEqual(len({rule.rows for rule in rules}), 168)

    def test_affine_basis_identifies_and_generalizes(self):
        rule = AffineRule((0b001, 0b010, 0b100), 0b101)
        support = tuple(PairObservation(x, rule.apply(x)) for x in (0, 1, 2, 4))
        gate = tuple(PairObservation(x, rule.apply(x)) for x in (3, 5))
        result = infer_affine_rule(support, gate)
        self.assertEqual(result.status, "IDENTIFIABLE_WITHIN_AFFINE_GF2")
        self.assertEqual(result.survivors, (rule,))
        self.assertEqual([result.survivors[0].apply(x) for x in (6, 7)],
                         [rule.apply(x) for x in (6, 7)])

    def test_insufficient_evidence_preserves_ambiguity(self):
        support = (PairObservation(0, 3),)
        gate = (PairObservation(1, 2),)
        result = infer_affine_rule(support, gate)
        self.assertEqual(result.status, "AMBIGUOUS")
        self.assertGreater(len(result.survivors), 1)

    def test_budget_exhaustion_never_selects_truncated_prefix(self):
        result = infer_affine_rule(
            (PairObservation(0, 0),), (PairObservation(1, 1),),
            max_candidates=FAMILY_SIZE - 1,
        )
        self.assertEqual(result.status, "BUDGET_EXHAUSTED")
        self.assertEqual(result.survivors, ())
        self.assertEqual(result.candidates_considered, 0)

    def test_support_and_gate_must_be_disjoint(self):
        with self.assertRaises(ValueError):
            infer_affine_rule((PairObservation(0, 0),), (PairObservation(0, 0),))

    def test_boolean_is_not_a_valid_state(self):
        with self.assertRaises(ValueError):
            infer_affine_rule((PairObservation(True, 0),), (PairObservation(1, 0),))

    def test_lookup_control_abstains_on_unseen_inputs(self):
        visible = (PairObservation(0, 1), PairObservation(1, 0))
        self.assertIsNone(lookup_predict(visible, 7))
        self.assertEqual(lookup_predict(visible, 0), 1)

    def test_permuted_code_control_is_not_affine_over_observed_codes(self):
        episode = make_episode(19, "permuted_code")
        all_rows = episode.support + episode.gate + episode.test
        for rule in affine_rules():
            self.assertFalse(all(rule.apply(row.lower) == row.upper for row in all_rows))

    def test_episode_generation_is_deterministic_and_splits_are_disjoint(self):
        first = make_episode(23, "affine")
        second = make_episode(23, "affine")
        self.assertEqual(first, second)
        groups = [
            {row.lower for row in first.support},
            {row.lower for row in first.gate},
            {row.lower for row in first.test},
        ]
        self.assertEqual(len(set.union(*groups)), 8)
        self.assertEqual(sum(len(group) for group in groups), 8)

    def test_benchmark_is_reproducible_and_reports_all_controls(self):
        first = run_benchmark(seeds=3, seed_start=40)
        second = run_benchmark(seeds=3, seed_start=40)
        self.assertEqual(first, second)
        self.assertEqual(first["episodes"], 9)
        self.assertEqual(set(first["summary"]), {"affine", "nonlinear", "permuted_code"})
        self.assertEqual(first["summary"]["affine"]["factorized_coverage"], 1.0)
        self.assertEqual(first["summary"]["affine"]["factorized_strict_accuracy"], 1.0)
        self.assertEqual(first["summary"]["affine"]["lookup_coverage"], 0.0)
        self.assertEqual(first["summary"]["affine"]["factorized_selective_accuracy"], 1.0)
        self.assertAlmostEqual(first["summary"]["affine"]["factorized_coverage_95ci"][0], 0.6096657121)
        self.assertEqual(first["summary"]["affine"]["factorized_coverage_95ci"][1], 1.0)
        self.assertEqual(first["summary"]["affine"]["candidate_evaluations"], FAMILY_SIZE * 3)


if __name__ == "__main__":
    unittest.main()
