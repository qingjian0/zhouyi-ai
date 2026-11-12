import unittest
from dataclasses import replace

from prototype.csg_gcr_e12a6_adapter import adapt_typed_candidate
from prototype.srok0_kernel import Node as SrokNode
from prototype.yixiang_analogy import Relation
from prototype.yixiang_role_transform import RoleTransform
from prototype.yixiang_srok_adapter import propose_yixiang_compositions
from prototype.yixiang_csg_gcr_adapter import coordinate_yixiang_compositions


class YixiangHypothesisLifecycleGuardTests(unittest.TestCase):
    def test_hypothesis_only_candidate_cannot_be_projected_as_observed(self):
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
        composed = propose_yixiang_compositions(relation, transform, nodes, limit=4)
        coordinated = coordinate_yixiang_compositions(
            composed, parent_state_ref="world:0", branch_id="branch:yx",
        )
        self.assertTrue(coordinated.coordination.candidates)
        with self.assertRaisesRegex(ValueError, "hypothesis-only candidates"):
            adapt_typed_candidate(
                coordinated.coordination.candidates[0],
                scope="world/test",
                grammar_version="csg-gcr-v1",
            )
        # Typed epistemic status remains authoritative even if a display label changes.
        candidate = coordinated.coordination.candidates[0]
        relabeled = replace(
            candidate,
            coordinated=replace(candidate.coordinated, candidate_kinds=("generic",)),
        )
        self.assertEqual(relabeled.semantic_status, "HYPOTHESIS_ONLY")
        with self.assertRaisesRegex(ValueError, "hypothesis-only candidates"):
            adapt_typed_candidate(
                relabeled, scope="world/test", grammar_version="csg-gcr-v1",
            )


if __name__ == "__main__":
    unittest.main()
