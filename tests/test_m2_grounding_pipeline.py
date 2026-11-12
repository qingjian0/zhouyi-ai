from __future__ import annotations

import unittest
from unittest.mock import Mock

from prototype.m2_grounding_pipeline import (
    GroundingError,
    GroundingResolution,
    SemanticUnitGroundingPipeline,
)
from prototype.m2_semantic_unit_store import SemanticUnitReceipt
from prototype.observation_contract import (
    EpistemicStatus,
    EvidenceRef,
    GroundingStatus,
    RecordEnvelope,
    SemanticUnitCandidate,
    TruthStatus,
    UnitKind,
)


def make_candidate(record_id: str = "candidate-1") -> SemanticUnitCandidate:
    ref = EvidenceRef(
        document_id="doc-1",
        chunk_id="chunk-1",
        content_sha256="a" * 64,
        byte_start=0,
        byte_end=16,
        source_version="v1",
    )
    envelope = RecordEnvelope(
        schema_version="m2-record-v1",
        record_id=record_id,
        record_kind="SemanticUnitCandidate",
        producer="test-extractor",
        producer_version="1",
        recorded_at="2026-11-12T00:00:00Z",
        scope="test-scope",
        source_refs=(ref,),
        derivation_refs=("m2:observation:obs-1",),
    )
    return SemanticUnitCandidate(
        envelope=envelope,
        kind=UnitKind.CONCEPT,
        surface_forms=("周易", "易学"),
        grounding_status=GroundingStatus.UNRESOLVED,
        epistemic_status=EpistemicStatus.UNKNOWN,
        truth_status=TruthStatus.UNKNOWN,
    )


def decision_for(candidate: SemanticUnitCandidate, **kwargs) -> GroundingResolution:
    values = {
        "candidate_record_id": candidate.envelope.record_id,
        "status": GroundingStatus.GROUNDED,
        "resolver_id": "registry-resolver",
        "resolver_version": "1",
        "source_refs": candidate.envelope.source_refs,
        "canonical_key": "concept:zhouyi",
        "matched_surface_form": "周易",
    }
    values.update(kwargs)
    return GroundingResolution(**values)


class _Resolver:
    def __init__(self, decisions):
        self.decisions = decisions

    def resolve(self, candidate):
        return self.decisions[candidate.envelope.record_id]


class SemanticUnitGroundingPipelineTests(unittest.TestCase):
    def setUp(self):
        self.candidate = make_candidate()
        self.store = Mock()
        self.store.scope = "test-scope"
        self.store.record_candidate.side_effect = lambda item: SemanticUnitReceipt(
            event_id=f"m2:semantic-unit:{item.envelope.record_id}",
            sequence=2,
            payload_digest="b" * 64,
            record_digest="c" * 64,
        )

    def run_pipeline(self, decision):
        pipeline = SemanticUnitGroundingPipeline(
            _Resolver({self.candidate.envelope.record_id: decision}),
            self.store,
        )
        return pipeline.ground_and_persist([self.candidate])

    def test_grounded_decision_persists_immutable_revision(self):
        result = self.run_pipeline(decision_for(self.candidate))
        self.assertEqual(result.input_count, 1)
        self.assertEqual(result.grounded_count, 1)
        self.assertEqual(result.persisted_count, 1)
        written = self.store.record_candidate.call_args.args[0]
        self.assertEqual(written.grounding_status, GroundingStatus.GROUNDED)
        self.assertEqual(written.canonical_key, "concept:zhouyi")
        self.assertEqual(written.truth_status, TruthStatus.UNKNOWN)
        self.assertEqual(written.envelope.source_refs, self.candidate.envelope.source_refs)
        self.assertEqual(written.envelope.scope, self.candidate.envelope.scope)
        self.assertIn(
            f"m2:semantic-unit:{self.candidate.envelope.record_id}",
            written.envelope.derivation_refs,
        )
        self.assertNotEqual(written.envelope.record_id, self.candidate.envelope.record_id)

    def test_unresolved_decision_does_not_append_duplicate_revision(self):
        result = self.run_pipeline(decision_for(
            self.candidate,
            status=GroundingStatus.UNRESOLVED,
            canonical_key=None,
            matched_surface_form=None,
        ))
        self.assertEqual(result.unresolved_count, 1)
        self.assertEqual(result.persisted_count, 0)
        self.store.record_candidate.assert_not_called()

    def test_partial_grounding_is_persisted_but_not_promoted_to_grounded(self):
        result = self.run_pipeline(decision_for(
            self.candidate,
            status=GroundingStatus.PARTIALLY_GROUNDED,
            canonical_key=None,
            matched_surface_form=None,
        ))
        written = self.store.record_candidate.call_args.args[0]
        self.assertEqual(result.grounded_count, 0)
        self.assertEqual(written.grounding_status, GroundingStatus.PARTIALLY_GROUNDED)
        self.assertIsNone(written.canonical_key)

    def test_rejects_surface_form_not_in_source_before_any_append(self):
        bad = decision_for(self.candidate, matched_surface_form="不存在")
        with self.assertRaisesRegex(GroundingError, "surface_form"):
            self.run_pipeline(bad)
        self.store.record_candidate.assert_not_called()

    def test_rejects_foreign_evidence_reference_before_any_append(self):
        foreign = EvidenceRef(
            document_id="other",
            chunk_id="other",
            content_sha256="d" * 64,
            byte_start=0,
            byte_end=4,
            source_version="v1",
        )
        bad = decision_for(self.candidate, source_refs=(foreign,))
        with self.assertRaisesRegex(GroundingError, "exact M1 source_refs"):
            self.run_pipeline(bad)
        self.store.record_candidate.assert_not_called()

    def test_rejects_decision_for_different_candidate(self):
        bad = decision_for(self.candidate, candidate_record_id="other")
        with self.assertRaisesRegex(GroundingError, "different candidate"):
            self.run_pipeline(bad)
        self.store.record_candidate.assert_not_called()

    def test_rejects_duplicate_input_ids_before_any_append(self):
        pipeline = SemanticUnitGroundingPipeline(
            _Resolver({self.candidate.envelope.record_id: decision_for(self.candidate)}),
            self.store,
        )
        with self.assertRaisesRegex(GroundingError, "duplicate"):
            pipeline.ground_and_persist([self.candidate, self.candidate])
        self.store.record_candidate.assert_not_called()

    def test_rejects_batch_over_limit_before_any_append(self):
        pipeline = SemanticUnitGroundingPipeline(
            _Resolver({self.candidate.envelope.record_id: decision_for(self.candidate)}),
            self.store,
            max_candidates_per_batch=1,
        )
        second = make_candidate("candidate-2")
        with self.assertRaisesRegex(GroundingError, "limit"):
            pipeline.ground_and_persist([self.candidate, second])
        self.store.record_candidate.assert_not_called()

    def test_validates_all_decisions_before_first_append(self):
        second = make_candidate("candidate-2")
        resolver = _Resolver({
            self.candidate.envelope.record_id: decision_for(self.candidate),
            second.envelope.record_id: decision_for(second, matched_surface_form="not-present"),
        })
        pipeline = SemanticUnitGroundingPipeline(resolver, self.store)
        with self.assertRaises(GroundingError):
            pipeline.ground_and_persist([self.candidate, second])
        self.store.record_candidate.assert_not_called()

    def test_grounding_never_changes_truth_status(self):
        result = self.run_pipeline(decision_for(self.candidate))
        written = self.store.record_candidate.call_args.args[0]
        self.assertEqual(written.truth_status, TruthStatus.UNKNOWN)
        self.assertEqual(result.items[0].status, GroundingStatus.GROUNDED)


if __name__ == "__main__":
    unittest.main()
