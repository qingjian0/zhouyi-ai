import unittest

from prototype.csg_gcr_coordinator import GlobalConstraints
from prototype.srok0_kernel import Node as SrokNode
from prototype.yixiang_analogy import Relation
from prototype.yixiang_role_transform import RoleTransform
from prototype.yixiang_srok_adapter import propose_yixiang_compositions
from prototype.yixiang_csg_gcr_adapter import (
    compile_yixiang_typed_proposals,
    coordinate_yixiang_compositions,
)


class YixiangCsgGcrBridgeTests(unittest.TestCase):
    def setUp(self):
        relation = Relation("causes", ("actor-a", "state-a"))
        transform = RoleTransform(
            "cause-effect-role-view", "1.0.0", "causes", "effect_of",
            (1, 0), scope_conditions=("domain:causal-relations",),
            evidence_refs=("prior:role-transform-v1",),
        )
        nodes = (
            SrokNode("actor-a", "actor", evidence_ids=("obs:actor-a",)),
            SrokNode("actor-b", "actor", evidence_ids=("obs:actor-b",)),
            SrokNode("state-a", "state", evidence_ids=("obs:state-a",)),
            SrokNode("state-b", "state", evidence_ids=("obs:state-b",)),
        )
        self.result = propose_yixiang_compositions(
            relation, transform, nodes, limit=8,
        )

    def test_candidates_compile_to_typed_hyperedges(self):
        rows = compile_yixiang_typed_proposals(
            self.result, parent_state_ref="world:0", branch_id="branch:yx",
        )
        self.assertGreaterEqual(len(rows), 1)
        for row in rows:
            self.assertEqual(row.semantic_status, "HYPOTHESIS_ONLY")
            self.assertEqual(row.proposal.bindings, ())
            self.assertEqual(row.proposal.parent_state_ref, "world:0")
            self.assertEqual(row.hyperedge.relation_type, "effect_of")
            self.assertEqual(row.proposal.evidence_refs, row.hyperedge.evidence_refs)
            self.assertTrue(row.proposal.candidate_kind.startswith("YIXIANG_HYPOTHESIS_ONLY:"))
            self.assertTrue(row.hyperedge.evidence_refs)

    def test_alternatives_are_mutually_exclusive_not_joint_facts(self):
        rows = compile_yixiang_typed_proposals(
            self.result, parent_state_ref="world:0", branch_id="branch:yx",
        )
        if len(rows) > 1:
            ids = {row.proposal.proposal_id for row in rows}
            for row in rows:
                self.assertEqual(set(row.proposal.excludes), ids - {row.proposal.proposal_id})

    def test_typed_csg_gcr_selects_one_hypothesis_from_search_batch(self):
        result = coordinate_yixiang_compositions(
            self.result, parent_state_ref="world:0", branch_id="branch:yx",
            constraints=GlobalConstraints(result_limit=8),
        )
        self.assertEqual(result.semantic_status, "HYPOTHESIS_ONLY")
        self.assertEqual(len(result.coordination.candidates), min(8, len(result.proposals)))
        if result.coordination.candidates:
            for candidate in result.coordination.candidates:
                self.assertEqual(candidate.semantic_status, "HYPOTHESIS_ONLY")
                self.assertEqual(len(candidate.coordinated.proposal_ids), 1)
                self.assertEqual(candidate.coordinated.candidate_kinds[0].split(":")[0],
                                 "YIXIANG_HYPOTHESIS_ONLY")
                self.assertEqual(candidate.unification.evidence_refs,
                                 candidate.coordinated.evidence_refs)

    def test_transform_prior_is_not_observational_evidence(self):
        result = coordinate_yixiang_compositions(
            self.result, parent_state_ref="world:0", branch_id="branch:yx",
        )
        self.assertEqual(result.transform_evidence_refs, ("prior:role-transform-v1",))
        for row in result.proposals:
            self.assertNotIn("prior:role-transform-v1", row.proposal.evidence_refs)

    def test_invalid_context_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "parent_state_ref"):
            compile_yixiang_typed_proposals(
                self.result, parent_state_ref="", branch_id="branch:yx",
            )


if __name__ == "__main__":
    unittest.main()
