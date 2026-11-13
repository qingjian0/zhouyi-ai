import unittest

from prototype.yixiang_multiview_composition import (
    AxisEvidence, CompositionBridge, EvidenceKind, ProposalStatus,
    ViewCandidate, XiangAxis, compose_views, group_competing_views,
    revalidate_composite, revalidate_view,
)


def view(candidate_id, axis, scope=("same task",), source="obs-a", target="obs-b"):
    return ViewCandidate(
        candidate_id, source, target, axis,
        AxisEvidence(axis, "pattern-a", "pattern-b", "role-preserving mapping",
                     f"src:{candidate_id}", f"tgt:{candidate_id}",
                     EvidenceKind.DIRECT_OBSERVATION, EvidenceKind.DIRECT_OBSERVATION),
        scope, ("different material",),
    )


def bridge(ids, scope=("same task",)):
    return CompositionBridge(
        "bridge-1", tuple(ids), "complementary_constraints",
        scope, ("bridge:evidence-1",), "The two views constrain different aspects of one task",
    )


class MultiViewCompositionTests(unittest.TestCase):
    def test_axes_remain_separate_competing_views(self):
        candidates = (
            view("morph", XiangAxis.MORPHOLOGICAL),
            view("function", XiangAxis.FUNCTIONAL),
        )
        self.assertEqual(group_competing_views(candidates), (("function", "morph"),))

    def test_composition_requires_explicit_bridge_and_stays_review_only(self):
        candidates = (
            view("structure", XiangAxis.STRUCTURAL),
            view("function", XiangAxis.FUNCTIONAL),
        )
        result = compose_views(candidates, bridge(("structure", "function")))
        self.assertEqual(result.status, ProposalStatus.HUMAN_REVIEW)
        self.assertEqual(result.claim_ceiling, "composed_hypothesis_for_human_review_only")
        self.assertIn("not_proof_of_shared_mechanism", result.non_claims)

    def test_rejects_missing_member(self):
        candidates = (view("a", XiangAxis.STRUCTURAL), view("b", XiangAxis.FUNCTIONAL))
        with self.assertRaisesRegex(ValueError, "exactly match"):
            compose_views(candidates, bridge(("a",)))

    def test_rejects_cross_observation_pair(self):
        candidates = (
            view("a", XiangAxis.STRUCTURAL),
            view("b", XiangAxis.FUNCTIONAL, source="other-source"),
        )
        with self.assertRaisesRegex(ValueError, "same ordered observation pair"):
            compose_views(candidates, bridge(("a", "b")))

    def test_rejects_duplicate_axis(self):
        candidates = (
            view("a", XiangAxis.STRUCTURAL),
            view("b", XiangAxis.STRUCTURAL),
        )
        with self.assertRaisesRegex(ValueError, "distinct axes"):
            compose_views(candidates, bridge(("a", "b")))

    def test_rejects_non_overlapping_scope(self):
        candidates = (
            view("a", XiangAxis.STRUCTURAL, scope=("same task",)),
            view("b", XiangAxis.FUNCTIONAL, scope=("different task",)),
        )
        with self.assertRaisesRegex(ValueError, "scope must overlap"):
            compose_views(candidates, bridge(("a", "b"), scope=("same task",)))

    def test_rejects_empty_bridge_evidence(self):
        candidates = (view("a", XiangAxis.STRUCTURAL), view("b", XiangAxis.FUNCTIONAL))
        bad = CompositionBridge("b", ("a", "b"), "join", ("same task",), (), "rationale")
        with self.assertRaisesRegex(ValueError, "evidence_refs"):
            compose_views(candidates, bad)

    def test_bridge_evidence_cannot_reuse_member_view_evidence(self):
        candidates = (view("a", XiangAxis.STRUCTURAL), view("b", XiangAxis.FUNCTIONAL))
        bad = CompositionBridge(
            "b", ("a", "b"), "join", ("same task",),
            ("src:a", "bridge:independent"), "rationale",
        )
        with self.assertRaisesRegex(ValueError, "distinct from member-view"):
            compose_views(candidates, bad)

    def test_rejects_evidence_axis_mismatch(self):
        candidate = ViewCandidate(
            "bad", "obs-a", "obs-b", XiangAxis.STRUCTURAL,
            AxisEvidence(XiangAxis.FUNCTIONAL, "x", "y", "mapping", "s", "t",
                         EvidenceKind.DIRECT_OBSERVATION, EvidenceKind.DIRECT_OBSERVATION),
            ("same task",), ("difference",),
        )
        with self.assertRaisesRegex(ValueError, "axis must match"):
            group_competing_views((candidate,))


    def test_view_is_blocked_when_scope_condition_disappears(self):
        candidate = view("a", XiangAxis.STRUCTURAL, scope=("same task", "same season"))
        result = revalidate_view(candidate, ("same task",))
        self.assertEqual(result.status, ProposalStatus.BLOCKED)
        self.assertEqual(result.missing_conditions, ("same season",))

    def test_composite_is_invalidated_when_bridge_context_changes(self):
        candidates = (view("a", XiangAxis.STRUCTURAL), view("b", XiangAxis.FUNCTIONAL))
        proposal = compose_views(candidates, bridge(("a", "b")))
        result = revalidate_composite(proposal, candidates, ())
        self.assertEqual(result.status, ProposalStatus.BLOCKED)
        self.assertIn("same task", result.missing_conditions)

    def test_composite_remains_review_only_when_all_conditions_hold(self):
        candidates = (view("a", XiangAxis.STRUCTURAL), view("b", XiangAxis.FUNCTIONAL))
        proposal = compose_views(candidates, bridge(("a", "b")))
        result = revalidate_composite(proposal, candidates, ("same task",))
        self.assertEqual(result.status, ProposalStatus.HUMAN_REVIEW)
        self.assertEqual(result.missing_conditions, ())


if __name__ == "__main__":
    unittest.main()
