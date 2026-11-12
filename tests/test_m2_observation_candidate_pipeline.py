from __future__ import annotations

import unittest
from unittest.mock import Mock

from prototype.m2_observation_candidate_pipeline import (
    ObservationCandidatePipeline,
    SemanticExtractionError,
)
from prototype.m2_observation_store import ObservationReceipt
from prototype.observation_contract import (
    EpistemicStatus,
    EvidenceRef,
    ExtractionMethod,
    GroundingStatus,
    Modality,
    Observation,
    ParseStatus,
    RecordEnvelope,
    SemanticUnitCandidate,
    SourceLocator,
    TruthStatus,
    UnitKind,
    record_digest,
)


def make_observation(*, parse_status: ParseStatus = ParseStatus.PARSED) -> Observation:
    ref = EvidenceRef(
        document_id="doc-1",
        chunk_id="chunk-1",
        content_sha256="a" * 64,
        byte_start=0,
        byte_end=12,
        source_version="v1",
    )
    envelope = RecordEnvelope(
        schema_version="m2-record-v1",
        record_id="obs-1",
        record_kind="Observation",
        producer="test-parser",
        producer_version="1",
        recorded_at="2026-11-12T00:00:00Z",
        scope="test-scope",
        source_refs=(ref,),
    )
    return Observation(
        envelope=envelope,
        modality=Modality.TEXT,
        source_locator=SourceLocator(
            modality=Modality.TEXT, payload_version="v1", byte_start=0, byte_end=12,
        ),
        extractor_id="test-parser",
        extractor_version="1",
        extraction_method=ExtractionMethod.RULE,
        parse_status=parse_status,
    )


def receipt_for(observation: Observation) -> ObservationReceipt:
    return ObservationReceipt(
        event_id=f"m2:observation:{observation.envelope.record_id}",
        sequence=1,
        payload_digest="b" * 64,
        record_digest=record_digest(observation),
    )


def make_candidate(observation: Observation, *, record_id: str = "candidate-1",
                   grounding: GroundingStatus = GroundingStatus.UNRESOLVED,
                   truth: TruthStatus = TruthStatus.UNKNOWN,
                   derivation_refs: tuple[str, ...] | None = None) -> SemanticUnitCandidate:
    envelope = RecordEnvelope(
        schema_version="m2-record-v1",
        record_id=record_id,
        record_kind="SemanticUnitCandidate",
        producer="fixture-extractor",
        producer_version="1",
        recorded_at="2026-11-12T00:00:01Z",
        scope=observation.envelope.scope,
        source_refs=observation.envelope.source_refs,
        derivation_refs=derivation_refs or (f"m2:observation:{observation.envelope.record_id}",),
    )
    return SemanticUnitCandidate(
        envelope=envelope,
        kind=UnitKind.CONCEPT,
        surface_forms=("example concept",),
        grounding_status=grounding,
        epistemic_status=EpistemicStatus.UNKNOWN,
        truth_status=truth,
    )


class _Extractor:
    def __init__(self, candidates):
        self.candidates = candidates

    def extract(self, observation):
        return iter(self.candidates)


class ObservationCandidatePipelineTests(unittest.TestCase):
    def setUp(self):
        self.observation = make_observation()
        self.receipt = receipt_for(self.observation)
        self.store = Mock()
        self.store.scope = "test-scope"
        self.store.record_candidate.side_effect = lambda candidate: candidate.envelope.record_id
        self.pipeline = ObservationCandidatePipeline(_Extractor([]), self.store)

    def run_pipeline(self, pipeline=None, observation=None, receipt=None):
        return (pipeline or self.pipeline).extract_and_persist(
            observation or self.observation,
            observation_receipt=receipt or self.receipt,
        )

    def test_valid_batch_preserves_observation_provenance(self):
        candidate = make_candidate(self.observation)
        pipeline = ObservationCandidatePipeline(_Extractor([candidate]), self.store)
        result = self.run_pipeline(pipeline)
        self.assertEqual(result.candidate_count, 1)
        self.assertEqual(result.observation_event_ref, "m2:observation:obs-1")
        self.assertEqual(result.candidate_receipts, ("candidate-1",))
        self.store.record_candidate.assert_called_once_with(candidate)

    def test_rejects_wrong_observation_receipt(self):
        wrong = ObservationReceipt(
            event_id="m2:observation:other",
            sequence=1,
            payload_digest="b" * 64,
            record_digest=record_digest(self.observation),
        )
        with self.assertRaisesRegex(SemanticExtractionError, "does not identify"):
            self.run_pipeline(receipt=wrong)
        self.store.record_candidate.assert_not_called()

    def test_rejects_receipt_digest_mismatch(self):
        wrong = ObservationReceipt(
            event_id="m2:observation:obs-1",
            sequence=1,
            payload_digest="b" * 64,
            record_digest="c" * 64,
        )
        with self.assertRaisesRegex(SemanticExtractionError, "digest"):
            self.run_pipeline(receipt=wrong)
        self.store.record_candidate.assert_not_called()

    def test_rejects_missing_observation_derivation_reference(self):
        candidate = make_candidate(self.observation, derivation_refs=("other-event",))
        pipeline = ObservationCandidatePipeline(_Extractor([candidate]), self.store)
        with self.assertRaisesRegex(SemanticExtractionError, "derivation_refs"):
            self.run_pipeline(pipeline)
        self.store.record_candidate.assert_not_called()

    def test_rejects_extractor_claiming_grounding_or_truth(self):
        for kwargs in (
            {"grounding": GroundingStatus.GROUNDED},
            {"truth": TruthStatus.SUPPORTED},
        ):
            with self.subTest(kwargs=kwargs):
                candidate = make_candidate(self.observation, **kwargs)
                pipeline = ObservationCandidatePipeline(_Extractor([candidate]), self.store)
                with self.assertRaises(SemanticExtractionError):
                    self.run_pipeline(pipeline)
        self.store.record_candidate.assert_not_called()

    def test_rejects_duplicate_ids_before_any_append(self):
        candidate = make_candidate(self.observation)
        pipeline = ObservationCandidatePipeline(_Extractor([candidate, candidate]), self.store)
        with self.assertRaisesRegex(SemanticExtractionError, "duplicate"):
            self.run_pipeline(pipeline)
        self.store.record_candidate.assert_not_called()

    def test_rejects_batch_over_limit_before_any_append(self):
        candidate = make_candidate(self.observation)
        pipeline = ObservationCandidatePipeline(
            _Extractor([candidate, make_candidate(self.observation, record_id="candidate-2")]),
            self.store, max_candidates_per_observation=1,
        )
        with self.assertRaisesRegex(SemanticExtractionError, "limit"):
            self.run_pipeline(pipeline)
        self.store.record_candidate.assert_not_called()

    def test_rejects_unparseable_observation(self):
        observation = make_observation(parse_status=ParseStatus.UNPARSEABLE)
        with self.assertRaisesRegex(SemanticExtractionError, "not extractable"):
            self.run_pipeline(observation=observation, receipt=receipt_for(observation))
        self.store.record_candidate.assert_not_called()

    def test_marks_partial_parse_without_promoting_it(self):
        observation = make_observation(parse_status=ParseStatus.PARTIAL)
        candidate = make_candidate(observation)
        pipeline = ObservationCandidatePipeline(_Extractor([candidate]), self.store)
        result = self.run_pipeline(pipeline, observation, receipt_for(observation))
        self.assertTrue(result.partial_observation)


if __name__ == "__main__":
    unittest.main()
