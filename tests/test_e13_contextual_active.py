import unittest
from fractions import Fraction

from prototype.e13_contextual_stochastic import (
    ContextualTransitionRule, ContextualProbabilisticTransitionSystem,
)
from prototype.e13_contextual_active import (
    ContextualMechanismCandidate, ContextualSequenceQuery,
    select_contextual_discriminating_sequence,
)


def system(name, first, second):
    return ContextualProbabilisticTransitionSystem(name, ("x",), ("mode",),
        ("a", "b"), (
            ContextualTransitionRule((("mode", "fixed"),), "a", (("x", "s"),),
                (((("x", first),), Fraction(1)),)),
            ContextualTransitionRule((("mode", "fixed"),), "b", (("x", "s"),),
                (((("x", second),), Fraction(1)),)),
        ))


class E13ContextualActiveTests(unittest.TestCase):
    def setUp(self):
        self.candidates = (
            ContextualMechanismCandidate("c1", system("c1", "u", "u")),
            ContextualMechanismCandidate("c2", system("c2", "u", "v")),
        )
        self.initial = (("x", "s"),)
        self.context = (("mode", "fixed"),)

    def test_selects_action_sequence_with_greatest_disagreement(self):
        queries = (
            ContextualSequenceQuery("q-a", ("a",), True, Fraction(0), Fraction(1)),
            ContextualSequenceQuery("q-b", ("b",), True, Fraction(0), Fraction(1)),
        )
        result = select_contextual_discriminating_sequence(
            self.candidates, queries, self.initial, self.context)
        self.assertEqual(result.status, "SELECTED")
        self.assertEqual(result.selected.query_id, "q-b")
        self.assertEqual(result.selected.pairwise_tv_disagreement, Fraction(1, 2))

    def test_unauthorized_and_risky_queries_are_hard_rejected(self):
        queries = (
            ContextualSequenceQuery("blocked", ("b",), False, Fraction(0), Fraction(0)),
            ContextualSequenceQuery("risky", ("b",), True, Fraction(1), Fraction(0)),
        )
        result = select_contextual_discriminating_sequence(
            self.candidates, queries, self.initial, self.context,
            max_risk=Fraction(1, 2))
        self.assertEqual(result.status, "NO_SAFE_COMPLETE_QUERY")
        self.assertEqual(result.rejected, (("blocked", "UNAUTHORIZED"),
                                          ("risky", "RISK_LIMIT_EXCEEDED")))

    def test_missing_candidate_support_makes_query_unknown(self):
        incomplete = ContextualProbabilisticTransitionSystem(
            "incomplete", ("x",), ("mode",), ("a", "b"), ())
        candidates = self.candidates + (ContextualMechanismCandidate("c3", incomplete),)
        query = ContextualSequenceQuery("q", ("b",), True, Fraction(0), Fraction(0))
        result = select_contextual_discriminating_sequence(
            candidates, (query,), self.initial, self.context)
        self.assertEqual(result.status, "NO_SAFE_COMPLETE_QUERY")
        self.assertEqual(result.rejected[0][1], "UNKNOWN_INCOMPLETE_CANDIDATE_FORECAST")

    def test_deterministic_tie_break_uses_query_id(self):
        queries = (
            ContextualSequenceQuery("z", ("a",), True, Fraction(0), Fraction(0)),
            ContextualSequenceQuery("a", ("a",), True, Fraction(0), Fraction(0)),
        )
        result = select_contextual_discriminating_sequence(
            self.candidates, queries, self.initial, self.context)
        self.assertEqual(result.status, "NO_DISAGREEMENT")
        self.assertEqual(result.selected.query_id, "a")

    def test_risk_cost_weights_only_rank_after_hard_gates(self):
        queries = (
            ContextualSequenceQuery("high", ("b",), True, Fraction(1, 2), Fraction(0)),
            ContextualSequenceQuery("low", ("b",), True, Fraction(0), Fraction(1)),
        )
        result = select_contextual_discriminating_sequence(
            self.candidates, queries, self.initial, self.context,
            risk_weight=Fraction(1), cost_weight=Fraction(0))
        self.assertEqual(result.selected.query_id, "low")


if __name__ == "__main__":
    unittest.main()
