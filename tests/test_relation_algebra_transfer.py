import unittest

from prototype.relation_algebra import RelationOntology, RelationType
from prototype.relation_algebra_transfer import assess_relation_transfer_with_algebra
from prototype.yixiang_relation_invariants import (
    InvariantCheck,
    RelationEdge,
    RelationFrame,
    RelationTransferContract,
    InvariantDecision,
)


class RelationAlgebraTransferIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.ontology = RelationOntology({
            "contains": RelationType("contains", inverse_of="inside"),
            "inside": RelationType("inside", inverse_of="contains"),
            "adjacent": RelationType("adjacent", symmetric=True),
            "supports": RelationType("supports"),
        })

    def contract(self, *, target_edge, conditions=(), checks=()):
        source = RelationFrame(
            frame_id="source", domain="source-domain",
            roles=("container", "item"),
            edges=(RelationEdge("contains", "container", "item"),),
            conditions=(("phase", "stable"),),
            evidence_refs=("src:1",),
        )
        target = RelationFrame(
            frame_id="target", domain="target-domain",
            roles=("outer", "inner"),
            edges=(target_edge,),
            conditions=conditions or (("phase", "stable"),),
            evidence_refs=("tgt:1",),
        )
        return RelationTransferContract(
            transfer_id="transfer-1", source=source, target=target,
            role_mapping=(("container", "outer"), ("item", "inner")),
            required_context_axes=("phase",),
            required_invariants=("boundary",) if checks else (),
            invariant_checks=checks,
        )

    def test_declared_inverse_is_accepted_without_weakening_other_gates(self):
        result = assess_relation_transfer_with_algebra(
            self.contract(target_edge=RelationEdge("inside", "inner", "outer")),
            self.ontology,
        )
        self.assertEqual(result.relation_score.f1, 1.0)
        self.assertEqual(result.assessment.decision, InvariantDecision.ACCEPT_SCOPED)
        self.assertNotIn(
            "RELATION_TOPOLOGY_OR_DIRECTION_MISMATCH",
            result.assessment.reason_codes,
        )

    def test_undeclared_direction_reversal_remains_rejected(self):
        result = assess_relation_transfer_with_algebra(
            self.contract(target_edge=RelationEdge("supports", "inner", "outer")),
            self.ontology,
        )
        self.assertEqual(result.relation_score.f1, 0.0)
        self.assertEqual(result.assessment.decision, InvariantDecision.REJECT)
        self.assertIn(
            "RELATION_TOPOLOGY_OR_DIRECTION_MISMATCH",
            result.assessment.reason_codes,
        )

    def test_context_mismatch_still_abstains_after_relation_match(self):
        result = assess_relation_transfer_with_algebra(
            self.contract(
                target_edge=RelationEdge("inside", "inner", "outer"),
                conditions=(("phase", "unstable"),),
            ),
            self.ontology,
        )
        self.assertEqual(result.relation_score.f1, 1.0)
        self.assertEqual(result.assessment.decision, InvariantDecision.ABSTAIN)
        self.assertIn("REQUIRED_CONTEXT_AXIS_MISMATCH", result.assessment.reason_codes)

    def test_critical_invariant_failure_still_rejects_after_relation_match(self):
        check = InvariantCheck(
            name="boundary", source_value="closed", target_value="open",
            source_evidence_ref="src:1", target_evidence_ref="tgt:1",
            critical=True,
        )
        result = assess_relation_transfer_with_algebra(
            self.contract(
                target_edge=RelationEdge("inside", "inner", "outer"),
                checks=(check,),
            ),
            self.ontology,
        )
        self.assertEqual(result.relation_score.f1, 1.0)
        self.assertEqual(result.assessment.decision, InvariantDecision.REJECT)
        self.assertIn("CRITICAL_INVARIANT_NOT_PRESERVED", result.assessment.reason_codes)


if __name__ == "__main__":
    unittest.main()
