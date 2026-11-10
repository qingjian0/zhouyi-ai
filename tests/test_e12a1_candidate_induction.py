import unittest

from prototype.e12a1_candidate_induction import (
    Example,
    induce,
    make_benchmark,
    propose_candidates,
    run_demo,
)


class E12A1CandidateInductionTests(unittest.TestCase):
    def test_proposals_depend_on_observed_values_not_labels(self):
        a = (Example((0, 1), 0), Example((2, 3), 1))
        b = (Example((0, 1), 1), Example((2, 3), 0))
        self.assertEqual(propose_candidates(a), propose_candidates(b))

    def test_atoms_precede_conjunctions_under_budget(self):
        support, _, _ = make_benchmark()
        candidates = propose_candidates(support, candidate_budget=23)
        self.assertTrue(all(c.op != "and" for c in candidates))

    def test_budget_is_bounded(self):
        support, _, _ = make_benchmark()
        self.assertEqual(len(propose_candidates(support, 10)), 10)

    def test_induction_uses_support_and_gate_only(self):
        support, gate, _locked_test = make_benchmark()
        result = induce(support, gate)
        self.assertEqual(result["status"], "CANDIDATE_SELECTED")
        self.assertIsNotNone(result["selected"])
        self.assertEqual(result["support_accuracy"], 1.0)
        self.assertEqual(result["gate_accuracy"], 1.0)

    def test_benchmark_splits_are_disjoint(self):
        support, gate, locked_test = make_benchmark()
        support_values = {row.values for row in support}
        gate_values = {row.values for row in gate}
        test_values = {row.values for row in locked_test}
        self.assertTrue(support_values.isdisjoint(gate_values))
        self.assertTrue(support_values.isdisjoint(test_values))
        self.assertTrue(gate_values.isdisjoint(test_values))

    def test_selected_expression_is_human_readable(self):
        support, gate, _ = make_benchmark()
        result = induce(support, gate)
        self.assertIn("AND", result["selected"])
        self.assertIn("x0", result["selected"])
        self.assertIn("x1", result["selected"])

    def test_empty_support_is_rejected(self):
        with self.assertRaises(ValueError):
            propose_candidates(())

    def test_feature_width_must_be_consistent(self):
        with self.assertRaises(ValueError):
            propose_candidates((Example((1, 2), 0), Example((1,), 1)))

    def test_demo_scores_locked_test_after_selection(self):
        result = run_demo()
        self.assertEqual(result["learner_result"]["status"], "CANDIDATE_SELECTED")
        self.assertIsNotNone(result["locked_test_accuracy"])
        self.assertEqual(result["locked_test_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
