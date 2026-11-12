import hashlib
import unittest

from prototype.m2_yixiang_grounding_adapter import (
    GroundedYixiangInputError,
    compose_grounded_yixiang_hypotheses,
    compose_trlw_grounded_yixiang_hypotheses,
    coordinate_trlw_grounded_yixiang_csg_gcr,
)
from prototype.observation_contract import (
    EpistemicStatus,
    EvidenceRef,
    GroundingStatus,
    RecordEnvelope,
    RoleBinding,
    SemanticUnitCandidate,
    TruthStatus,
    UnitKind,
)
from prototype.trlw_working_set import TRLWQuery, build_trlw_working_set
from prototype.yixiang_role_transform import RoleTransform
from prototype.yixiang_csg_gcr_adapter import compile_yixiang_typed_proposals


def evidence(record_id):
    return EvidenceRef(
        document_id="doc-" + record_id,
        chunk_id="chunk-" + record_id,
        content_sha256=hashlib.sha256(record_id.encode()).hexdigest(),
        byte_start=0,
        byte_end=1,
        source_version="m1-v1",
    )


def candidate(record_id, kind, *, roles=(), scope="world:test",
              grounding=GroundingStatus.GROUNDED, truth=TruthStatus.UNKNOWN):
    env = RecordEnvelope(
        schema_version="m2-record-v1",
        record_id=record_id,
        record_kind="SemanticUnitCandidate",
        producer="semantic-parser",
        producer_version="1.0",
        recorded_at="2026-11-12T00:00:00Z",
        scope=scope,
        source_refs=(evidence(record_id),),
    )
    return SemanticUnitCandidate(
        envelope=env,
        kind=kind,
        surface_forms=(record_id,),
        role_bindings=tuple(RoleBinding(name, target) for name, target in roles),
        grounding_status=grounding,
        epistemic_status=EpistemicStatus.ASSERTED,
        truth_status=truth,
    )


class M2YixiangGroundingAdapterTests(unittest.TestCase):
    def setUp(self):
        self.relation = candidate(
            "relation:causes:1", UnitKind.EVENT,
            roles=(("cause", "actor:a"), ("effect", "state:a")),
        )
        self.workspace = (
            candidate("actor:a", UnitKind.ENTITY),
            candidate("actor:b", UnitKind.ENTITY),
            candidate("state:a", UnitKind.STATE),
            candidate("state:b", UnitKind.STATE),
        )
        self.e09 = {
            "relation:causes:1": ("e09:observation:relation-1",),
            "actor:a": ("e09:observation:actor-a",),
            "actor:b": ("e09:observation:actor-b",),
            "state:a": ("e09:observation:state-a",),
            "state:b": ("e09:observation:state-b",),
        }
        self.transform = RoleTransform(
            "cause-effect-role-view", "1.0.0", "causes", "effect_of", (1, 0),
            evidence_refs=("xsl-prior:causal-role-view",),
        )

    def compose(self, **changes):
        args = dict(
            relation_candidate=self.relation,
            relation_type="causes",
            workspace_candidates=self.workspace,
            e09_event_refs_by_record=self.e09,
            transform=self.transform,
            limit=16,
        )
        args.update(changes)
        return compose_grounded_yixiang_hypotheses(**args)

    def test_grounded_role_bindings_compile_to_hypotheses_with_separate_provenance(self):
        grounded = self.compose()
        self.assertEqual(grounded.composition.application.transformed_relation.relation_type,
                         "effect_of")
        self.assertEqual(grounded.semantic_status, "HYPOTHESIS_ONLY")
        self.assertEqual(len(grounded.m1_source_ref_digests), 5)
        self.assertEqual(
            grounded.composition.source_relation_evidence_refs,
            ("e09:observation:relation-1",),
        )
        proposals = compile_yixiang_typed_proposals(
            grounded.composition, parent_state_ref="state:0", branch_id="branch:yx",
        )
        self.assertTrue(proposals)
        for proposal in proposals:
            self.assertEqual(proposal.semantic_status, "HYPOTHESIS_ONLY")
            self.assertIn("e09:observation:relation-1", proposal.proposal.evidence_refs)
            self.assertTrue(set(proposal.proposal.evidence_refs).issubset(
                set(grounded.e09_observation_event_refs)
            ))
            self.assertNotIn("xsl-prior:causal-role-view", proposal.proposal.evidence_refs)

    def test_trlw_bounded_packet_flows_into_grounded_yixiang_srok(self):
        records = (self.relation, *self.workspace)
        packet = build_trlw_working_set(
            records,
            TRLWQuery(
                query_goal="compose grounded causal relation",
                scope="world:test",
                max_records=8,
                byte_budget=100_000,
            ),
            source_complete=True,
        )
        result = compose_trlw_grounded_yixiang_hypotheses(
            packet,
            relation_record_id="relation:causes:1",
            relation_type="causes",
            e09_event_refs_by_record=self.e09,
            transform=self.transform,
        )
        self.assertTrue(result.search_exhaustive)
        self.assertEqual(result.working_set_status, "COMPLETE")
        self.assertEqual(
            result.grounded.semantic_status,
            "HYPOTHESIS_ONLY",
        )
        self.assertTrue(result.grounded.composition.search.candidates)

    def test_trlw_yixiang_srok_candidates_reach_typed_csg_gcr_without_lifecycle_advance(self):
        packet = build_trlw_working_set(
            (self.relation, *self.workspace),
            TRLWQuery(
                query_goal="compose grounded causal relation",
                scope="world:test",
                max_records=8,
                byte_budget=100_000,
            ),
            source_complete=True,
        )
        result = coordinate_trlw_grounded_yixiang_csg_gcr(
            packet,
            relation_record_id="relation:causes:1",
            relation_type="causes",
            e09_event_refs_by_record=self.e09,
            transform=self.transform,
            parent_state_ref="state:root",
            branch_id="branch:yixiang-test",
        )
        self.assertFalse(result.lifecycle_advanced)
        self.assertTrue(result.working_set.search_exhaustive)
        self.assertTrue(result.csg_gcr.proposals)
        for proposal in result.csg_gcr.proposals:
            self.assertEqual(proposal.semantic_status, "HYPOTHESIS_ONLY")
            self.assertIn(
                "e09:observation:relation-1",
                proposal.proposal.evidence_refs,
            )
            self.assertNotIn(
                "xsl-prior:causal-role-view",
                proposal.proposal.evidence_refs,
            )

    def test_incomplete_trlw_packet_never_claims_exhaustive_search(self):
        records = (self.relation, *self.workspace)
        packet = build_trlw_working_set(
            records,
            TRLWQuery(
                query_goal="compose grounded causal relation",
                scope="world:test",
                max_records=8,
                byte_budget=100_000,
            ),
            source_complete=False,
        )
        result = compose_trlw_grounded_yixiang_hypotheses(
            packet,
            relation_record_id="relation:causes:1",
            relation_type="causes",
            e09_event_refs_by_record=self.e09,
            transform=self.transform,
        )
        self.assertFalse(result.search_exhaustive)
        self.assertFalse(result.working_set_source_complete)

    def test_grounded_does_not_mean_true(self):
        grounded = self.compose()
        self.assertEqual(self.relation.grounding_status, GroundingStatus.GROUNDED)
        self.assertEqual(self.relation.truth_status, TruthStatus.UNKNOWN)
        self.assertEqual(grounded.semantic_status, "HYPOTHESIS_ONLY")

    def test_unresolved_source_candidate_is_rejected(self):
        rows = list(self.workspace)
        rows[0] = candidate("actor:a", UnitKind.ENTITY,
                           grounding=GroundingStatus.UNRESOLVED)
        with self.assertRaisesRegex(GroundedYixiangInputError, "not GROUNDED"):
            self.compose(workspace_candidates=tuple(rows))

    def test_cross_scope_candidates_are_rejected(self):
        rows = list(self.workspace)
        rows[0] = candidate("actor:a", UnitKind.ENTITY, scope="world:other")
        with self.assertRaisesRegex(GroundedYixiangInputError, "share one scope"):
            self.compose(workspace_candidates=tuple(rows))

    def test_missing_e09_authority_event_is_rejected(self):
        refs = dict(self.e09)
        refs.pop("state:b")
        with self.assertRaisesRegex(GroundedYixiangInputError, "cover exactly"):
            self.compose(e09_event_refs_by_record=refs)

    def test_missing_role_target_is_rejected(self):
        rows = tuple(item for item in self.workspace if item.envelope.record_id != "state:a")
        refs = {key: value for key, value in self.e09.items() if key != "state:a"}
        with self.assertRaisesRegex(GroundedYixiangInputError, "missing workspace"):
            self.compose(workspace_candidates=rows, e09_event_refs_by_record=refs)

    def test_relation_role_order_is_not_sorted_or_lost(self):
        grounded = self.compose()
        self.assertEqual(
            grounded.composition.application.source_relation.arguments,
            ("actor:a", "state:a"),
        )
        self.assertEqual(
            grounded.composition.application.transformed_relation.arguments,
            ("state:a", "actor:a"),
        )

    def test_refuted_or_unknown_truth_is_not_rewritten_by_grounding_adapter(self):
        relation = candidate(
            "relation:causes:1", UnitKind.EVENT,
            roles=(("cause", "actor:a"), ("effect", "state:a")),
            truth=TruthStatus.CONFLICTED,
        )
        grounded = self.compose(relation_candidate=relation)
        self.assertEqual(relation.truth_status, TruthStatus.CONFLICTED)
        self.assertEqual(grounded.semantic_status, "HYPOTHESIS_ONLY")


if __name__ == "__main__":
    unittest.main()
