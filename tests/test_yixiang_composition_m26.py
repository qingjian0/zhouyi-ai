import unittest

from prototype.yixiang_composition_m26 import (
    CompositionEdge, CompositionKind, CompositionNode, CompositionStatus,
    EmergentCategoryClaim, SymbolicElement, audit_compositions,
)


def element(element_id="a", **changes):
    data = dict(element_id=element_id, category_id=f"cat-{element_id}",
                context_id="ctx", context_version=1)
    data.update(changes)
    return SymbolicElement(**data)


def composition(**changes):
    data = dict(composition_id="cmp", member_ids=("a", "b"),
                kind=CompositionKind.PARALLEL, operation="combine side by side",
                scope="task-x", context_id="ctx", context_version=1,
                evidence_refs=("compose-evidence",), rationale="declared rule")
    data.update(changes)
    return CompositionNode(**data)


def emergence(**changes):
    data = dict(claim_id="claim", composition_id="cmp",
                proposed_category_id="new-category", candidate_properties=("p-new",),
                whole_level_evidence_refs=("whole-e",), member_evidence_refs=("member-e",),
                non_reducibility_argument="whole-level interaction not reducible to member union",
                scope="task-x", context_id="ctx", context_version=1,
                counterexample_refs=("counter-e",), rationale="bounded claim")
    data.update(changes)
    return EmergentCategoryClaim(**data)


class CompositionM26Tests(unittest.TestCase):
    def setUp(self):
        self.elements = [element("a"), element("b")]

    def test_basic_parallel_composition_is_provisional(self):
        result = audit_compositions(self.elements, [composition()])
        self.assertTrue(result.valid)
        self.assertEqual(result.status, CompositionStatus.PROVISIONAL)

    def test_ordered_composition_requires_order_flag(self):
        result = audit_compositions(self.elements, [composition(kind=CompositionKind.ORDERED)])
        self.assertIn("ordered_composition_requires_order:cmp", result.issues)

    def test_ordered_composition_with_order_is_valid(self):
        result = audit_compositions(self.elements, [composition(kind=CompositionKind.ORDERED, ordered=True)])
        self.assertTrue(result.valid)

    def test_non_ordered_operation_with_order_is_reviewed(self):
        result = audit_compositions(self.elements, [composition(ordered=True)])
        self.assertTrue(result.valid)
        self.assertEqual(result.status, CompositionStatus.HUMAN_REVIEW)

    def test_composition_needs_two_members(self):
        result = audit_compositions(self.elements, [composition(member_ids=("a",))])
        self.assertIn("composition_requires_two_members:cmp", result.issues)

    def test_duplicate_members_rejected(self):
        result = audit_compositions(self.elements, [composition(member_ids=("a", "a"))])
        self.assertIn("duplicate_composition_member:cmp", result.issues)

    def test_unknown_member_rejected(self):
        result = audit_compositions(self.elements, [composition(member_ids=("a", "missing"))])
        self.assertIn("unknown_composition_member:cmp:missing", result.issues)

    def test_member_context_mismatch_rejected(self):
        result = audit_compositions([element("a"), element("b", context_version=2)], [composition()])
        self.assertIn("composition_context_mismatch:cmp:b", result.issues)

    def test_missing_operation_rejected(self):
        result = audit_compositions(self.elements, [composition(operation="")])
        self.assertIn("incomplete_composition_rule:cmp", result.issues)

    def test_missing_evidence_rejected(self):
        result = audit_compositions(self.elements, [composition(evidence_refs=())])
        self.assertIn("missing_composition_evidence:cmp", result.issues)

    def test_edge_requires_known_endpoints(self):
        edge = CompositionEdge("e", "a", "missing", CompositionKind.INTERACTION,
                               "interact", "task-x", "ctx", 1, ("ev",), "why", composition_id="cmp")
        result = audit_compositions(self.elements, [composition()], [edge])
        self.assertIn("unknown_edge_endpoint:e", result.issues)

    def test_self_edge_rejected(self):
        edge = CompositionEdge("e", "a", "a", CompositionKind.INTERACTION,
                               "interact", "task-x", "ctx", 1, ("ev",), "why")
        result = audit_compositions(self.elements, [composition()], [edge])
        self.assertIn("self_edge:e", result.issues)

    def test_edge_endpoint_outside_composition_rejected(self):
        edge = CompositionEdge("e", "a", "c", CompositionKind.INTERACTION,
                               "interact", "task-x", "ctx", 1, ("ev",), "why", composition_id="cmp")
        result = audit_compositions(self.elements + [element("c")], [composition()], [edge])
        self.assertIn("edge_endpoint_outside_composition:e", result.issues)

    def test_edge_context_mismatch_rejected(self):
        edge = CompositionEdge("e", "a", "b", CompositionKind.INTERACTION,
                               "interact", "task-x", "ctx", 2, ("ev",), "why")
        result = audit_compositions(self.elements, [composition()], [edge])
        self.assertIn("edge_context_mismatch:e:a", result.issues)

    def test_transformation_cycle_requires_review(self):
        edges = [
            CompositionEdge("e1", "a", "b", CompositionKind.TRANSFORMATION,
                            "state transition", "task-x", "ctx", 1, ("ev1",), "why"),
            CompositionEdge("e2", "b", "a", CompositionKind.TRANSFORMATION,
                            "state transition", "task-x", "ctx", 1, ("ev2",), "why"),
        ]
        result = audit_compositions(self.elements, [composition()], edges)
        self.assertTrue(result.valid)
        self.assertEqual(result.status, CompositionStatus.HUMAN_REVIEW)

    def test_emergence_claim_is_always_human_review(self):
        result = audit_compositions(self.elements, [composition()], emergence_claims=[emergence()])
        self.assertTrue(result.valid)
        self.assertEqual(result.status, CompositionStatus.HUMAN_REVIEW)

    def test_emergence_requires_whole_level_evidence(self):
        result = audit_compositions(self.elements, [composition()],
                                    emergence_claims=[emergence(whole_level_evidence_refs=())])
        self.assertIn("missing_whole_level_evidence:claim", result.issues)

    def test_whole_and_member_evidence_must_not_overlap(self):
        result = audit_compositions(self.elements, [composition()],
                                    emergence_claims=[emergence(member_evidence_refs=("whole-e",))])
        self.assertIn("whole_and_member_evidence_not_independent:claim", result.issues)

    def test_emergence_requires_non_reducibility_argument(self):
        result = audit_compositions(self.elements, [composition()],
                                    emergence_claims=[emergence(non_reducibility_argument="")])
        self.assertIn("missing_non_reducibility_argument:claim", result.issues)

    def test_emergence_requires_counterexample_refs(self):
        result = audit_compositions(self.elements, [composition()],
                                    emergence_claims=[emergence(counterexample_refs=())])
        self.assertIn("missing_emergence_counterexamples:claim", result.issues)

    def test_emergence_context_must_match_composition(self):
        result = audit_compositions(self.elements, [composition()],
                                    emergence_claims=[emergence(context_version=2)])
        self.assertIn("emergence_context_mismatch:claim", result.issues)

    def test_emergence_scope_must_match_composition(self):
        result = audit_compositions(self.elements, [composition()],
                                    emergence_claims=[emergence(scope="unbounded")])
        self.assertIn("emergence_scope_mismatch:claim", result.issues)

    def test_unknown_composition_claim_rejected(self):
        result = audit_compositions(self.elements, [composition()],
                                    emergence_claims=[emergence(composition_id="missing")])
        self.assertIn("unknown_claim_composition:claim", result.issues)

    def test_duplicate_composition_id_rejected(self):
        result = audit_compositions(self.elements, [composition(), composition()])
        self.assertIn("duplicate_composition_id:cmp", result.issues)

    def test_duplicate_edge_id_rejected(self):
        edge = CompositionEdge("e", "a", "b", CompositionKind.INTERACTION,
                               "interact", "task-x", "ctx", 1, ("ev",), "why")
        result = audit_compositions(self.elements, [composition()], [edge, edge])
        self.assertIn("duplicate_edge_id:e", result.issues)


if __name__ == "__main__":
    unittest.main()
