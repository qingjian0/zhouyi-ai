import unittest

from prototype.classiang_native import (
    Decision, EvidenceRef, Relation, Symbol, SymbolGraph,
    assess_relation_mapping, compose_relations,
)


def graph(*, reviewed=True):
    evidence = (
        EvidenceRef("e1", "source-1", "family-1", "p.1", "CC-BY-4.0", reviewed),
        EvidenceRef("e2", "source-2", "family-2", "p.2", "CC-BY-4.0", reviewed),
    )
    symbols = (
        Symbol("a", "mechanics", "object", (("kind", "lever"),), ("e1",)),
        Symbol("b", "mechanics", "object", (("kind", "load"),), ("e1",)),
        Symbol("c", "mechanics", "object", (("kind", "fulcrum"),), ("e2",)),
    )
    relations = (
        Relation("r1", "supports", (("agent", "a"), ("patient", "b")), ("e1",)),
        Relation("r2", "balances", (("left", "b"), ("right", "c")), ("e2",)),
    )
    return SymbolGraph(evidence, symbols, relations)


class NativeClassiangTests(unittest.TestCase):
    def test_graph_validates_evidence_and_role_references(self):
        graph().validate()
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            graph(reviewed=False).validate()

    def test_bounded_composition_preserves_lineage_and_shared_symbols(self):
        result = compose_relations(graph(), max_depth=2, max_candidates=10)
        self.assertFalse(result.truncated)
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual(candidate.relation_ids, ("r1", "r2"))
        self.assertEqual(candidate.shared_symbols, ("b",))
        self.assertEqual(candidate.evidence_ids, ("e1", "e2"))

    def test_composition_reports_budget_exhaustion(self):
        result = compose_relations(graph(), max_depth=2, max_candidates=1)
        self.assertTrue(result.truncated)
        self.assertEqual(result.reason, "BUDGET_EXHAUSTED")

    def test_composition_rejects_invalid_budget(self):
        with self.assertRaises(ValueError):
            compose_relations(graph(), max_depth=1)
        with self.assertRaises(ValueError):
            compose_relations(graph(), max_candidates=0)

    def test_explicit_role_mapping_is_checked(self):
        source, target = graph().relations
        result = assess_relation_mapping(
            source, source,
            role_mapping=(("agent", "agent"), ("patient", "patient")),
            evidence_ids=("e1",),
        )
        self.assertEqual(result.decision, Decision.ACCEPT)
        self.assertIn("EXPLICIT_ROLE_STRUCTURE_PRESERVED_ONLY", result.reason_codes)

    def test_role_mismatch_abstains_and_missing_evidence_fails_closed(self):
        source, target = graph().relations
        result = assess_relation_mapping(
            source, target,
            role_mapping=(("agent", "left"), ("patient", "right")),
            evidence_ids=("e1", "e2"),
        )
        self.assertEqual(result.decision, Decision.ABSTAIN)
        with self.assertRaisesRegex(ValueError, "minimum 1"):
            assess_relation_mapping(
                source, source,
                role_mapping=(("agent", "agent"), ("patient", "patient")),
                evidence_ids=(),
            )

    def test_mapping_rejects_non_injective_role_assignment(self):
        source, _ = graph().relations
        with self.assertRaisesRegex(ValueError, "injective"):
            assess_relation_mapping(
                source, source,
                role_mapping=(("agent", "same"), ("patient", "same")),
                evidence_ids=("e1",),
            )


if __name__ == "__main__":
    unittest.main()
