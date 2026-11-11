import unittest

from prototype.cpg_interop import InferenceStatus
from prototype.e12a20_factor_graph import Hypothesis, InferenceResult as ExactResult
from prototype.e12a20_interop_adapter import adapt_bp_result, adapt_exact_result
from prototype.e12a20a1_belief_propagation import BPResult, Marginal


class E12A20InteropAdapterTests(unittest.TestCase):
    def test_exact_unique_assignment_maps_to_identified(self):
        source = ExactResult(
            status="CONVERGED",
            hypotheses=(Hypothesis(
                assignment=(("x", "yes"),),
                energy=0.0,
                evaluated_factor_ids=("f",),
                evidence_refs=("ev-1",),
                factor_costs=(("f", 0.0),),
            ),),
            assignments_examined=2,
            feasible_assignments=1,
            rejected_assignments=1,
            hard_conflict_counts=(("f", 1),),
            state_space_size=2,
            budget_limit=10,
        )
        adapted = adapt_exact_result(source, query_id="q-1", scope="task/a")
        self.assertEqual(adapted.inference.status, InferenceStatus.IDENTIFIED)
        self.assertEqual(len(adapted.inference.ranked_hypothesis_refs), 1)
        self.assertEqual(adapted.inference.evidence_refs, ("ev-1",))
        self.assertEqual(dict(adapted.inference.budget_used)["assignments_examined"], 2)

    def test_exact_multiple_assignments_remain_ambiguous(self):
        source = ExactResult(
            status="CONVERGED",
            hypotheses=(
                Hypothesis((("x", "a"),), 0.0, (), (), ()),
                Hypothesis((("x", "b"),), 0.0, (), (), ()),
            ),
            assignments_examined=2,
            feasible_assignments=2,
            rejected_assignments=0,
            hard_conflict_counts=(),
            state_space_size=2,
            budget_limit=10,
        )
        adapted = adapt_exact_result(source, query_id="q", scope="s")
        self.assertEqual(adapted.inference.status, InferenceStatus.AMBIGUOUS)
        self.assertEqual(len(adapted.inference.ranked_hypothesis_refs), 2)

    def test_exact_budget_exhaustion_is_not_convergence(self):
        source = ExactResult(
            status="BUDGET_EXHAUSTED",
            hypotheses=(Hypothesis((("x", "a"),), 0.0, (), (), ()),),
            assignments_examined=1,
            feasible_assignments=1,
            rejected_assignments=0,
            hard_conflict_counts=(),
            state_space_size=4,
            budget_limit=1,
        )
        adapted = adapt_exact_result(source, query_id="q", scope="s")
        self.assertEqual(adapted.inference.status, InferenceStatus.BUDGET_EXHAUSTED)

    def test_exact_no_feasible_assignment_is_inconsistent(self):
        source = ExactResult(
            status="NO_FEASIBLE_ASSIGNMENT",
            hypotheses=(),
            assignments_examined=2,
            feasible_assignments=0,
            rejected_assignments=2,
            hard_conflict_counts=(("f", 2),),
            state_space_size=2,
            budget_limit=10,
        )
        adapted = adapt_exact_result(source, query_id="q", scope="s")
        self.assertEqual(adapted.inference.status, InferenceStatus.INCONSISTENT)
        self.assertEqual(adapted.inference.ranked_hypothesis_refs, ())

    def test_bp_marginals_are_not_fabricated_into_joint_hypotheses(self):
        source = BPResult(
            status="CONVERGED",
            marginals=(Marginal("x", (("a", 0.7), ("b", 0.3))),),
            iterations=5,
            message_updates=20,
            factor_entries=4,
            factor_evaluations=40,
            max_message_delta=1e-12,
            evidence_refs=("ev-1",),
        )
        adapted = adapt_bp_result(source, query_id="q", scope="s")
        self.assertEqual(adapted.inference.status, InferenceStatus.AMBIGUOUS)
        self.assertEqual(adapted.inference.ranked_hypothesis_refs, ())
        self.assertEqual(adapted.inference.evidence_refs, ("ev-1",))
        self.assertEqual(adapted.marginals, source.marginals)
        self.assertEqual(adapted.marginals[0].probabilities[0], ("a", 0.7))

    def test_bp_budget_and_inconsistency_statuses_are_preserved(self):
        exhausted = BPResult("BUDGET_EXHAUSTED", (), 0, 0, 100, 0, float("inf"), ())
        inconsistent = BPResult("INCONSISTENT_MESSAGES", (), 1, 4, 2, 8, 0.0, ())
        self.assertEqual(
            adapt_bp_result(exhausted, query_id="q", scope="s").inference.status,
            InferenceStatus.BUDGET_EXHAUSTED,
        )
        self.assertEqual(
            adapt_bp_result(inconsistent, query_id="q", scope="s").inference.status,
            InferenceStatus.INCONSISTENT,
        )


if __name__ == "__main__":
    unittest.main()
