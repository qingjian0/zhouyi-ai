import unittest

from prototype.yijing_operator_induction import (
    CandidateStatus, DiscoveryError, EvidenceKind, ExperimentQuery, Node,
    Relation, RelationalOperatorInducer, RelationalState,
    TransitionObservation, rank_experiments, validate_candidate,
)


def state(extra=(), phase="growth"):
    nodes = (Node("a", "agent", "actor"), Node("b", "resource", "target"))
    relations = (Relation("a", "b", "supports"),) + tuple(extra)
    return RelationalState(nodes, tuple(sorted(relations)), (("phase", phase),))


class RelationalInductionTests(unittest.TestCase):
    def row(self, before, after, evidence, kind=EvidenceKind.INTERVENTIONAL, domain="d1"):
        return TransitionObservation(before, after, "allocate", evidence, kind, domain)

    def test_induces_role_bound_relation_delta(self):
        before = state()
        after = state((Relation("b", "a", "constrains"),))
        report = RelationalOperatorInducer(min_support=2).discover([
            self.row(before, after, "e1"),
            self.row(before, after, "e2", domain="d2"),
        ])
        self.assertEqual(len(report.candidates), 1)
        candidate = report.candidates[0]
        self.assertEqual(candidate.status, CandidateStatus.INTERVENTION_SUPPORTED)
        self.assertEqual(candidate.domains, ("d1", "d2"))
        self.assertEqual(candidate.predict(before, "allocate", domain="d1"), after)

    def test_concrete_entity_ids_are_alpha_renamed_by_roles(self):
        before1 = state()
        after1 = state((Relation("b", "a", "constrains"),))
        before2 = RelationalState(
            (Node("x", "agent", "actor"), Node("y", "resource", "target")),
            (Relation("x", "y", "supports"),), (("phase", "growth"),),
        )
        after2 = RelationalState(
            before2.nodes,
            tuple(sorted((Relation("x", "y", "supports"), Relation("y", "x", "constrains")))),
            before2.context,
        )
        report = RelationalOperatorInducer().discover([
            self.row(before1, after1, "e1"), self.row(before2, after2, "e2")
        ])
        self.assertEqual(len(report.candidates), 1)
        self.assertEqual(report.candidates[0].evidence_ids, ("e1", "e2"))

    def test_observation_only_is_not_intervention_supported(self):
        report = RelationalOperatorInducer().discover([
            self.row(state(), state((Relation("b", "a", "constrains"),)),
                     "e1", EvidenceKind.OBSERVATIONAL)
        ])
        self.assertEqual(report.candidates[0].status, CandidateStatus.PROPOSED)

    def test_context_is_intersected_not_overgeneralized(self):
        a = state(phase="growth")
        b = state(phase="decline")
        out_a = state((Relation("b", "a", "constrains"),), phase="growth")
        out_b = state((Relation("b", "a", "constrains"),), phase="decline")
        report = RelationalOperatorInducer().discover([
            self.row(a, out_a, "e1"), self.row(b, out_b, "e2")
        ])
        self.assertEqual(report.candidates[0].required_context, ())

    def test_missing_precondition_abstains(self):
        report = RelationalOperatorInducer(min_support=1).discover([
            self.row(state(), state((Relation("b", "a", "constrains"),)), "e1")
        ])
        candidate = report.candidates[0]
        no_support = RelationalState(
            (Node("a", "agent", "actor"), Node("b", "resource", "target")),
            (), (("phase", "growth"),),
        )
        self.assertIsNone(candidate.predict(no_support, "allocate", domain="d1"))
        self.assertIsNone(candidate.predict(state(), "allocate", domain="unseen-domain"))

    def test_held_out_counterexample_fails(self):
        before = state()
        after = state((Relation("b", "a", "constrains"),))
        candidate = RelationalOperatorInducer(min_support=1).discover([
            self.row(before, after, "train")
        ]).candidates[0]
        wrong = state((Relation("a", "b", "blocks"),))
        result = validate_candidate(candidate, [self.row(before, wrong, "heldout")])
        self.assertFalse(result.passed)
        self.assertEqual(result.mismatched_evidence_ids, ("heldout",))

    def test_active_query_prefers_candidate_disagreement(self):
        before = state()
        after_a = state((Relation("b", "a", "constrains"),))
        after_b = state((Relation("b", "a", "enables"),))
        inducer = RelationalOperatorInducer(min_support=1)
        candidates = inducer.discover([
            self.row(before, after_a, "e1"),
            self.row(before, after_b, "e2"),
        ]).candidates
        ranked = rank_experiments(candidates, [
            ExperimentQuery(before, "allocate", "d1", "q1"),
            ExperimentQuery(state(phase="other"), "allocate", "d1", "q2"),
        ])
        self.assertEqual(ranked[0].query_id, "q1")
        self.assertGreater(ranked[0].disagreement_bits, 0)

    def test_search_budget_is_reported(self):
        rows = [
            self.row(state(), state((Relation("b", "a", "constrains"),)), "e1"),
            self.row(state(), state((Relation("b", "a", "enables"),)), "e2"),
        ]
        report = RelationalOperatorInducer(max_candidates=1).discover(rows)
        self.assertTrue(report.budget_exhausted)

    def test_invalid_role_binding_rejected(self):
        with self.assertRaises(DiscoveryError):
            RelationalState(
                (Node("a", "agent", "same"), Node("b", "resource", "same")),
                (), (),
            )


if __name__ == "__main__":
    unittest.main()
