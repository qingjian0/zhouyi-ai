import unittest

from prototype.relation_algebra import RelationOntology, RelationType
from prototype.relation_algebra_transfer import assess_relation_transfer_with_algebra
from prototype.yixiang_relation_invariants import (
    InvariantCheck,
    InvariantDecision,
    RelationEdge,
    RelationFrame,
    RelationTransferContract,
)


class RelationAlgebraTransferTests(unittest.TestCase):
    def setUp(self):
        self.ontology = RelationOntology({
            "contains": RelationType("contains", inverse_of="inside"),
            "inside": RelationType("inside", inverse_of="contains"),
            "adjacent": RelationType("adjacent", symmetric=True),
            "supports": RelationType("supports"),
        })

    def contract(self, source_edge, target_edge, *, target_conditions=None, checks=()):
        source = RelationFrame(
            "source", "source-domain", ("a", "b"), (source_edge,),
            (("phase", "stable"),), ("source:evidence",),
        )
        target = RelationFrame(
            "target", "target-domain", ("x", "y"), (target_edge,),
            target_conditions or (("phase", "stable"),), ("target:evidence",),
        )
        return RelationTransferContract(
            transfer_id="transfer-1",
            source=source,
            target=target,
            role_mapping=(("a", "x"), ("b", "y")),
            required_context_axes=("phase",),
            required_invariants=("boundary",) if checks else (),
            invariant_checks=checks,
        )

    def test_declared_inverse_relation_is_accepted_scoped(self):
        contract = self.contract(
            RelationEdge("contains", "a", "b"),
            RelationEdge("inside", "y", "x"),
        )
        result = assess_relation_transfer_with_algebra(contract, self.ontology)
        self.assertEqual(result.relation_score.f1, 1.0)
        self.assertEqual(result.assessment.decision, InvariantDecision.ACCEPT_SCOPED)
        self.assertNotIn(
            "RELATION_TOPOLOGY_OR_DIRECTION_MISMATCH",
            result.assessment.reason_codes,
        )

    def test_declared_symmetric_relation_is_accepted_scoped(self):
        contract = self.contract(
            RelationEdge("adjacent", "a", "b"),
            RelationEdge("adjacent", "y", "x"),
        )
        result = assess_relation_transfer_with_algebra(contract, self.ontology)
        self.assertEqual(result.relation_score.f1, 1.0)
        self.assertEqual(result.assessment.decision, InvariantDecision.ACCEPT_SCOPED)

    def test_undeclared_direction_reversal_is_rejected(self):
        contract = self.contract(
            RelationEdge("supports", "a", "b"),
            RelationEdge("supports", "y", "x"),
        )
        result = assess_relation_transfer_with_algebra(contract, self.ontology)
        self.assertEqual(result.relation_score.f1, 0.0)
        self.assertEqual(result.assessment.decision, InvariantDecision.REJECT)
        self.assertIn(
            "RELATION_TOPOLOGY_OR_DIRECTION_MISMATCH",
            result.assessment.reason_codes,
        )

    def test_edge_polarity_mismatch_is_not_erased_by_relation_algebra(self):
        contract = self.contract(
            RelationEdge("supports", "a", "b", polarity="positive"),
            RelationEdge("supports", "x", "y", polarity="negative"),
        )
        result = assess_relation_transfer_with_algebra(contract, self.ontology)
        self.assertEqual(result.relation_score.f1, 1.0)
        self.assertEqual(result.assessment.decision, InvariantDecision.REJECT)
        self.assertIn("RELATION_EDGE_METADATA_MISMATCH", result.assessment.reason_codes)

    def test_context_mismatch_still_abstains_after_inverse_match(self):
        contract = self.contract(
            RelationEdge("contains", "a", "b"),
            RelationEdge("inside", "y", "x"),
            target_conditions=(("phase", "unstable"),),
        )
        result = assess_relation_transfer_with_algebra(contract, self.ontology)
        self.assertEqual(result.relation_score.f1, 1.0)
        self.assertEqual(result.assessment.decision, InvariantDecision.ABSTAIN)
        self.assertIn("REQUIRED_CONTEXT_AXIS_MISMATCH", result.assessment.reason_codes)

    def test_critical_invariant_failure_still_rejects(self):
        check = InvariantCheck(
            "boundary", "closed", "open",
            "source:evidence", "target:evidence", critical=True,
        )
        contract = self.contract(
            RelationEdge("contains", "a", "b"),
            RelationEdge("inside", "y", "x"),
            checks=(check,),
        )
        result = assess_relation_transfer_with_algebra(contract, self.ontology)
        self.assertEqual(result.relation_score.f1, 1.0)
        self.assertEqual(result.assessment.decision, InvariantDecision.REJECT)
        self.assertIn(
            "CRITICAL_INVARIANT_NOT_PRESERVED",
            result.assessment.reason_codes,
        )

    def test_unknown_predicate_fails_closed_with_abstention(self):
        contract = self.contract(
            RelationEdge("unregistered", "a", "b"),
            RelationEdge("supports", "x", "y"),
        )
        result = assess_relation_transfer_with_algebra(contract, self.ontology)
        self.assertIsNone(result.relation_score)
        self.assertEqual(result.assessment.decision, InvariantDecision.ABSTAIN)
        self.assertIn(
            "RELATION_ONTOLOGY_EVALUATION_FAILED",
            result.assessment.reason_codes,
        )


if __name__ == "__main__":
    unittest.main()
