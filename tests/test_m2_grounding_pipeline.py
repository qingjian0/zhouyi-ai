from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from prototype.m2_grounding_pipeline import (
    GroundingError, GroundingResolution, SemanticUnitGroundingPipeline,
)
from prototype.m2_semantic_unit_store import (
    PersistentSemanticUnitCandidateStore, SemanticUnitReceipt,
)
from prototype.evidence_ref_resolver import SQLiteEvidenceRefResolver
from prototype.observation_contract import (
    EpistemicStatus, EvidenceRef, GroundingStatus, RecordEnvelope,
    SemanticUnitCandidate, TruthStatus, UnitKind,
)
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor
from prototype.zpcm_memory import ZPCMMemory


def make_candidate(record_id="candidate-1"):
    ref = EvidenceRef(
        document_id="doc-1", chunk_id="chunk-1", content_sha256="a" * 64,
        byte_start=0, byte_end=16, source_version="v1",
    )
    envelope = RecordEnvelope(
        schema_version="m2-record-v1", record_id=record_id,
        record_kind="SemanticUnitCandidate", producer="test-extractor",
        producer_version="1", recorded_at="2026-11-12T00:00:00Z",
        scope="test-scope", source_refs=(ref,),
        derivation_refs=("m2:observation:obs-1",),
    )
    return SemanticUnitCandidate(
        envelope=envelope, kind=UnitKind.CONCEPT, surface_forms=("周易", "易学"),
        grounding_status=GroundingStatus.UNRESOLVED,
        epistemic_status=EpistemicStatus.UNKNOWN, truth_status=TruthStatus.UNKNOWN,
    )


def decision_for(candidate, **kwargs):
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


class Resolver:
    def __init__(self, decisions):
        self.decisions = decisions

    def resolve(self, candidate):
        return self.decisions[candidate.envelope.record_id]


class SemanticUnitGroundingPipelineTests(unittest.TestCase):
    def setUp(self):
        self.candidate = make_candidate()
        self.persisted = {self.candidate.envelope.record_id: self.candidate}
        self.store = Mock()
        self.store.scope = "test-scope"
        self.store.get_candidate.side_effect = lambda record_id: self.persisted.get(record_id)
        self.store.record_candidate.side_effect = lambda item: SemanticUnitReceipt(
            event_id=f"m2:semantic-unit:{item.envelope.record_id}",
            sequence=2, payload_digest="b" * 64, record_digest="c" * 64,
        )

    def run_pipeline(self, decision):
        pipeline = SemanticUnitGroundingPipeline(
            Resolver({self.candidate.envelope.record_id: decision}), self.store,
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
            self.candidate, status=GroundingStatus.UNRESOLVED,
            canonical_key=None, matched_surface_form=None,
        ))
        self.assertEqual(result.unresolved_count, 1)
        self.assertEqual(result.persisted_count, 0)
        self.store.record_candidate.assert_not_called()

    def test_partial_grounding_is_persisted_but_not_promoted_to_grounded(self):
        result = self.run_pipeline(decision_for(
            self.candidate, status=GroundingStatus.PARTIALLY_GROUNDED,
            canonical_key=None, matched_surface_form=None,
        ))
        written = self.store.record_candidate.call_args.args[0]
        self.assertEqual(result.grounded_count, 0)
        self.assertEqual(written.grounding_status, GroundingStatus.PARTIALLY_GROUNDED)
        self.assertIsNone(written.canonical_key)

    def test_rejects_surface_form_not_in_source_before_any_append(self):
        with self.assertRaisesRegex(GroundingError, "surface_form"):
            self.run_pipeline(decision_for(self.candidate, matched_surface_form="不存在"))
        self.store.record_candidate.assert_not_called()

    def test_rejects_foreign_evidence_reference_before_any_append(self):
        foreign = EvidenceRef(
            document_id="other", chunk_id="other", content_sha256="d" * 64,
            byte_start=0, byte_end=4, source_version="v1",
        )
        with self.assertRaisesRegex(GroundingError, "exact M1 source_refs"):
            self.run_pipeline(decision_for(self.candidate, source_refs=(foreign,)))
        self.store.record_candidate.assert_not_called()

    def test_rejects_decision_for_different_candidate(self):
        with self.assertRaisesRegex(GroundingError, "different candidate"):
            self.run_pipeline(decision_for(self.candidate, candidate_record_id="other"))
        self.store.record_candidate.assert_not_called()

    def test_rejects_duplicate_input_ids_before_any_append(self):
        pipeline = SemanticUnitGroundingPipeline(
            Resolver({self.candidate.envelope.record_id: decision_for(self.candidate)}),
            self.store,
        )
        with self.assertRaisesRegex(GroundingError, "duplicate"):
            pipeline.ground_and_persist([self.candidate, self.candidate])
        self.store.record_candidate.assert_not_called()

    def test_rejects_batch_over_limit_before_any_append(self):
        second = make_candidate("candidate-2")
        self.persisted[second.envelope.record_id] = second
        pipeline = SemanticUnitGroundingPipeline(
            Resolver({
                self.candidate.envelope.record_id: decision_for(self.candidate),
                second.envelope.record_id: decision_for(second),
            }),
            self.store, max_candidates_per_batch=1,
        )
        with self.assertRaisesRegex(GroundingError, "limit"):
            pipeline.ground_and_persist([self.candidate, second])
        self.store.record_candidate.assert_not_called()

    def test_validates_all_decisions_before_first_append(self):
        second = make_candidate("candidate-2")
        self.persisted[second.envelope.record_id] = second
        resolver = Resolver({
            self.candidate.envelope.record_id: decision_for(self.candidate),
            second.envelope.record_id: decision_for(second, matched_surface_form="not-present"),
        })
        pipeline = SemanticUnitGroundingPipeline(resolver, self.store)
        with self.assertRaises(GroundingError):
            pipeline.ground_and_persist([self.candidate, second])
        self.store.record_candidate.assert_not_called()

    def test_grounding_never_changes_truth_status(self):
        self.run_pipeline(decision_for(self.candidate))
        written = self.store.record_candidate.call_args.args[0]
        self.assertEqual(written.truth_status, TruthStatus.UNKNOWN)
        self.assertEqual(written.epistemic_status, EpistemicStatus.UNKNOWN)

    def test_rejects_unpersisted_or_modified_candidates_before_resolver(self):
        self.store.get_candidate.side_effect = lambda record_id: None
        pipeline = SemanticUnitGroundingPipeline(
            Resolver({self.candidate.envelope.record_id: decision_for(self.candidate)}),
            self.store,
        )
        with self.assertRaisesRegex(GroundingError, "not present"):
            pipeline.ground_and_persist([self.candidate])
        self.store.record_candidate.assert_not_called()

        self.store.get_candidate.side_effect = None
        self.store.get_candidate.return_value = make_candidate("candidate-1")
        altered = make_candidate("candidate-1")
        object.__setattr__(altered, "surface_forms", ("altered",))
        with self.assertRaisesRegex(GroundingError, "differs from the persisted"):
            pipeline.ground_and_persist([altered])
        self.store.record_candidate.assert_not_called()

    def test_real_zpcm_grounding_reads_persisted_candidate_and_appends_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence_db = root / "evidence.sqlite3"
            memory_db = root / "memory.sqlite3"
            ingestor = SQLiteEvidenceIngestor(evidence_db)
            result = ingestor.ingest(
                "doc-1", "fixture.txt", io.BytesIO("周易".encode("utf-8")),
                chunk_bytes=128,
            )
            self.assertTrue(result.complete)
            chunk = ingestor.get_chunks("doc-1")[0]
            resolver = SQLiteEvidenceRefResolver(evidence_db)
            reference = resolver.make_reference("doc-1", chunk.chunk_id)
            memory = ZPCMMemory(memory_db)
            self.addCleanup(memory.close)
            store = PersistentSemanticUnitCandidateStore(
                memory, resolver, scope="test-scope",
            )
            candidate = SemanticUnitCandidate(
                envelope=RecordEnvelope(
                    schema_version="m2-record-v1", record_id="stored-candidate",
                    record_kind="SemanticUnitCandidate", producer="extractor",
                    producer_version="1", recorded_at="2026-11-19T00:00:00Z",
                    scope="test-scope", source_refs=(reference,),
                    derivation_refs=("m2:observation:obs-1",),
                ),
                kind=UnitKind.CONCEPT, surface_forms=("周易",),
                grounding_status=GroundingStatus.UNRESOLVED,
                epistemic_status=EpistemicStatus.UNKNOWN,
                truth_status=TruthStatus.UNKNOWN,
            )
            store.record_candidate(candidate)

            class RealResolver:
                def resolve(self, item):
                    return GroundingResolution(
                        candidate_record_id=item.envelope.record_id,
                        status=GroundingStatus.GROUNDED,
                        resolver_id="fixture-registry", resolver_version="1",
                        source_refs=item.envelope.source_refs,
                        canonical_key="concept:zhouyi", matched_surface_form="周易",
                    )

            pipeline = SemanticUnitGroundingPipeline(RealResolver(), store)
            batch = pipeline.ground_and_persist([candidate])
            grounded_id = batch.items[0].output_record_id
            grounded = store.get_candidate(grounded_id)
            self.assertEqual(grounded.grounding_status, GroundingStatus.GROUNDED)
            self.assertEqual(grounded.canonical_key, "concept:zhouyi")
            self.assertEqual(grounded.truth_status, TruthStatus.UNKNOWN)
            self.assertEqual(store.get_candidate("stored-candidate"), candidate)


if __name__ == "__main__":
    unittest.main()
