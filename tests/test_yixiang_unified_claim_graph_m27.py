import unittest

from prototype.yixiang_unified_claim_graph_m27 import (
    ClaimNode, ContextChange, Dependency, DependencyStrength, NodeDisposition,
    NodeKind, RevisionEvent, audit_dependency_graph,
)


def node(node_id, kind=NodeKind.CLAIM, evidence=(), context_id="", context_version=0):
    return ClaimNode(node_id, kind, tuple(evidence), context_id, context_version)


def edge(edge_id, source, target, strength=DependencyStrength.HARD):
    return Dependency(edge_id, source, target, strength, "depends_on")


def event(**changes):
    data = dict(event_id="rev-1", changed_node_ids=("obs",),
                revoked_evidence_refs=(), context_changes=(),
                revalidated_node_ids=(), reason="source correction")
    data.update(changes)
    return RevisionEvent(**data)


class UnifiedClaimGraphM27Tests(unittest.TestCase):
    def setUp(self):
        self.nodes = (
            node("obs", NodeKind.OBSERVATION),
            node("feature", NodeKind.FEATURE),
            node("category", NodeKind.CATEGORY),
            node("relation", NodeKind.RELATION),
            node("composition", NodeKind.COMPOSITION),
            node("claim", NodeKind.CLAIM),
            node("independent", NodeKind.CLAIM),
        )
        self.edges = (
            edge("d1", "obs", "feature"),
            edge("d2", "feature", "category"),
            edge("d3", "category", "relation"),
            edge("d4", "relation", "composition"),
            edge("d5", "composition", "claim"),
        )

    def test_hard_dependency_propagates_transitively(self):
        result = audit_dependency_graph(self.nodes, self.edges, event())
        self.assertTrue(result.valid_graph)
        self.assertEqual(result.stale_node_ids, ("category", "claim", "composition", "feature", "obs", "relation"))
        self.assertEqual(result.unaffected_node_ids, ("independent",))

    def test_independent_branch_is_preserved(self):
        result = audit_dependency_graph(self.nodes, self.edges, event())
        self.assertIn("independent", result.unaffected_node_ids)

    def test_soft_dependency_marks_review_only(self):
        edges = (edge("soft", "obs", "feature", DependencyStrength.SOFT),
                 edge("hard", "feature", "claim"))
        result = audit_dependency_graph(self.nodes, edges, event())
        self.assertEqual(result.review_node_ids, ("feature",))
        self.assertNotIn("claim", result.stale_node_ids)

    def test_hard_path_dominates_soft_path(self):
        edges = (edge("soft", "obs", "feature", DependencyStrength.SOFT),
                 edge("hard", "obs", "feature", DependencyStrength.HARD))
        result = audit_dependency_graph(self.nodes, edges, event())
        self.assertIn("feature", result.stale_node_ids)
        self.assertNotIn("feature", result.review_node_ids)

    def test_revoked_evidence_seeds_nodes(self):
        nodes = (node("a", evidence=("w1",)), node("b"))
        result = audit_dependency_graph(nodes, (), event(changed_node_ids=(), revoked_evidence_refs=("w1",)))
        self.assertEqual(result.stale_node_ids, ("a",))
        self.assertEqual(result.seed_reasons, (("a", "evidence_revoked"),))

    def test_context_revision_seeds_old_version_nodes(self):
        nodes = (node("a", context_id="ctx", context_version=1),
                 node("b", context_id="ctx", context_version=2))
        change = ContextChange("ctx", 1, 2)
        result = audit_dependency_graph(nodes, (), event(changed_node_ids=(), context_changes=(change,)))
        self.assertEqual(result.stale_node_ids, ("a",))
        self.assertEqual(result.unaffected_node_ids, ("b",))

    def test_revalidated_node_is_a_propagation_barrier(self):
        result = audit_dependency_graph(self.nodes, self.edges,
                                        event(revalidated_node_ids=("category",)))
        self.assertNotIn("category", result.stale_node_ids)
        self.assertNotIn("relation", result.stale_node_ids)
        self.assertIn("category", result.unaffected_node_ids)

    def test_changed_and_revalidated_source_is_barrier(self):
        result = audit_dependency_graph(self.nodes, self.edges,
                                        event(revalidated_node_ids=("obs",)))
        self.assertEqual(result.stale_node_ids, ())
        self.assertEqual(result.unaffected_node_ids, tuple(sorted(n.node_id for n in self.nodes)))

    def test_unknown_changed_node_invalidates_graph(self):
        result = audit_dependency_graph(self.nodes, self.edges,
                                        event(changed_node_ids=("missing",)))
        self.assertFalse(result.valid_graph)
        self.assertIn("unknown_event_node:missing", result.issues)

    def test_unknown_edge_endpoint_invalidates_graph(self):
        result = audit_dependency_graph(self.nodes, (edge("bad", "obs", "missing"),), event())
        self.assertFalse(result.valid_graph)
        self.assertIn("unknown_dependency_endpoint:bad", result.issues)

    def test_cycle_rejected(self):
        edges = (edge("a", "obs", "feature"), edge("b", "feature", "obs"))
        result = audit_dependency_graph(self.nodes, edges, event())
        self.assertFalse(result.valid_graph)
        self.assertIn("dependency_cycle", result.issues)

    def test_self_dependency_rejected(self):
        result = audit_dependency_graph(self.nodes, (edge("self", "obs", "obs"),), event())
        self.assertIn("self_dependency:self", result.issues)

    def test_duplicate_node_id_rejected(self):
        result = audit_dependency_graph(self.nodes + (self.nodes[0],), self.edges, event())
        self.assertIn("duplicate_node_id", result.issues)

    def test_duplicate_dependency_id_rejected(self):
        result = audit_dependency_graph(self.nodes, self.edges + (self.edges[0],), event())
        self.assertIn("duplicate_dependency_id:d1", result.issues)

    def test_duplicate_evidence_reference_rejected(self):
        result = audit_dependency_graph((node("a", evidence=("x", "x")),), (), event(changed_node_ids=()))
        self.assertIn("duplicate_node_evidence:a", result.issues)

    def test_invalid_context_shape_rejected(self):
        result = audit_dependency_graph((node("a", context_id="ctx", context_version=0),), (),
                                        event(changed_node_ids=()))
        self.assertIn("incomplete_node_context:a", result.issues)

    def test_invalid_context_change_rejected(self):
        change = ContextChange("ctx", 2, 2)
        result = audit_dependency_graph(self.nodes, self.edges,
                                        event(context_changes=(change,)))
        self.assertIn("invalid_context_change:ctx", result.issues)

    def test_multiple_seed_reasons_preserved(self):
        nodes = (node("a", evidence=("w1",)), node("b"))
        result = audit_dependency_graph(nodes, (), event(changed_node_ids=("a",),
                                        revoked_evidence_refs=("w1",)))
        self.assertEqual(result.stale_node_ids, ("a",))
        self.assertEqual(result.seed_reasons, (("a", "evidence_revoked"),))

    def test_review_node_can_be_upgraded_to_stale(self):
        nodes = (node("a"), node("b"), node("c"))
        edges = (edge("soft", "a", "c", DependencyStrength.SOFT),
                 edge("hard", "b", "c", DependencyStrength.HARD))
        result = audit_dependency_graph(nodes, edges,
                                        event(changed_node_ids=("a", "b")))
        self.assertIn("c", result.stale_node_ids)
        self.assertNotIn("c", result.review_node_ids)

    def test_event_requires_reason(self):
        result = audit_dependency_graph(self.nodes, self.edges, event(reason=""))
        self.assertIn("invalid_revision_event", result.issues)

    def test_context_retirement_propagates(self):
        nodes = (node("a", NodeKind.OBSERVATION, context_id="ctx", context_version=1),
                 node("b", NodeKind.CLAIM))
        result = audit_dependency_graph(nodes, (edge("d", "a", "b"),),
                                        event(changed_node_ids=(), context_changes=(ContextChange("ctx", 1, 2),)))
        self.assertEqual(result.stale_node_ids, ("a", "b"))


if __name__ == "__main__":
    unittest.main()
