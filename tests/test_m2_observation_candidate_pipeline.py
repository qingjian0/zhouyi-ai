from __future__ import annotations

import unittest
from dataclasses import replace
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


def make_observation(*, parse_status=ParseStatus.PARSED):
    ref = EvidenceRef(
        document_id="doc-1", chunk_id="chunk-1",
        content_sha256="a" * 64, byte_start=0, byte_end=12,
        source_version="v1",
    )
    return Observation(
        envelope=RecordEnvelope(
            schema_version="m2-record-v1", record_id="obs-1",
            record_kind="Observation", producer="test-parser",
            producer_version="1", recorded_at="2026-11-12T00:00:00Z",
            scope="test-scope", source_refs=(ref,),
        ),
        modality=Modality.TEXT,
        source_locator=SourceLocator(
            modality=Modality.TEXT, payload_version="v1",
            byte_start=0, byte_end=12,
        ),
        extractor_id="test-parser", extractor_version="1",
        extraction_method=ExtractionMethod.RULE, parse_status=parse_status,
    )


def receipt_for(observation, *, sequence=1, payload_digest="b" * 64):
    return ObservationReceipt(
        event_id=f"m2:observation:{observation.envelope.record_id}",
        sequence=sequence, payload_digest=payload_digest,
        record_digest=record_digest(observation),
    )


def make_candidate(observation, *, record_id="candidate-1",
                   grounding=GroundingStatus.UNRESOLVED,
                   truth=TruthStatus.UNKNOWN, derivation_refs=None):
    return SemanticUnitCandidate(
        envelope=RecordEnvelope(
            schema_version="m2-record-v1", record_id=record_id,
            record_kind="SemanticUnitCandidate", producer="fixture-extractor",
            producer_version="1", recorded_at="2026-11-12T00:00:01Z",
            scope=observation.envelope.scope,
            source_refs=observation.envelope.source_refs,
            derivation_refs=derivation_refs or (
                f"m2:observation:{observation.envelope.record_id}",
            ),
        ),
        kind=UnitKind.CONCEPT, surface_forms=("example concept",),
        grounding_status=grounding, epistemic_status=EpistemicStatus.UNKNOWN,
        truth_status=truth,
    )


class Extractor:
    def __init__(self, candidates):
        self.candidates = candidates
        self.calls = 0

    def extract(self, observation):
        self.calls += 1
        return iter(self.candidates)


class ObservationCandidatePipelineTests(unittest.TestCase):
    def setUp(self):
        self.observation = make_observation()
        self.receipt = receipt_for(self.observation)
        self.observation_store = Mock()
        self.observation_store.scope = "test-scope"
        self.observation_store.get_observation.return_value = self.observation
        self.observation_store.get_receipt.return_value = self.receipt
        self.candidate_store = Mock()
        self.candidate_store.scope = "test-scope"
        self.candidate_store.record_candidate.side_effect = (
            lambda candidate: candidate.envelope.record_id
        )
        self.extractor = Extractor([])
        self.pipeline = ObservationCandidatePipeline(
            self.extractor, self.observation_store, self.candidate_store,
        )

    def run_pipeline(self, pipeline=None, observation=None, receipt=None):
        return (pipeline or self.pipeline).extract_and_persist(
            observation or self.observation,
            observation_receipt=receipt or self.receipt,
        )

    def test_valid_batch_rechecks_authoritative_observation_and_receipt(self):
        candidate = make_candidate(self.observation)
        extractor = Extractor([candidate])
        pipeline = ObservationCandidatePipeline(
            extractor, self.observation_store, self.candidate_store,
        )
        result = self.run_pipeline(pipeline)
        self.assertEqual(result.candidate_count, 1)
        self.assertEqual(result.observation_event_ref, "m2:observation:obs-1")
        self.assertEqual(result.candidate_receipts, ("candidate-1",))
        self.observation_store.get_observation.assert_called_once_with("obs-1")
        self.observation_store.get_receipt.assert_called_once_with("obs-1")
        self.candidate_store.record_candidate.assert_called_once_with(candidate)

    def test_rejects_forged_receipt_even_when_record_digest_matches(self):
        forged = replace(self.receipt, payload_digest="c" * 64)
        with self.assertRaisesRegex(SemanticExtractionError, "persisted receipt"):
            self.run_pipeline(receipt=forged)
        self.extractor.calls == 0
        self.candidate_store.record_candidate.assert_not_called()

    def test_rejects_observation_that_is_not_persisted(self):
        self.observation_store.get_observation.return_value = None
        with self.assertRaisesRegex(SemanticExtractionError, "not present"):
            self.run_pipeline()
        self.candidate_store.record_candidate.assert_not_called()

    def test_rejects_observation_different_from_persisted_record(self):
        changed = replace(self.observation, extractor_version="2")
        with self.assertRaisesRegex(SemanticExtractionError, "differs from the persisted"):
            self.run_pipeline(observation=changed, receipt=receipt_for(changed))
        self.candidate_store.record_candidate.assert_not_called()

    def test_rejects_wrong_event_identity_and_invalid_sequence(self):
        wrong = replace(self.receipt, event_id="m2:observation:other")
        with self.assertRaisesRegex(SemanticExtractionError, "does not identify"):
            self.run_pipeline(receipt=wrong)
        invalid = replace(self.receipt, sequence=True)
        with self.assertRaisesRegex(SemanticExtractionError, "positive integer"):
            self.run_pipeline(receipt=invalid)
        self.candidate_store.record_candidate.assert_not_called()

    def test_rejects_malformed_receipt_digest(self):
        invalid = replace(self.receipt, payload_digest="not-a-digest")
        with self.assertRaisesRegex(SemanticExtractionError, "SHA-256"):
            self.run_pipeline(receipt=invalid)
        self.candidate_store.record_candidate.assert_not_called()

    def test_rejects_missing_observation_derivation_reference(self):
        candidate = make_candidate(self.observation, derivation_refs=("other-event",))
        pipeline = ObservationCandidatePipeline(
            Extractor([candidate]), self.observation_store, self.candidate_store,
        )
        with self.assertRaisesRegex(SemanticExtractionError, "derivation_refs"):
            self.run_pipeline(pipeline)
        self.candidate_store.record_candidate.assert_not_called()

    def test_rejects_extractor_claiming_grounding_or_truth(self):
        for kwargs in (
            {"grounding": GroundingStatus.GROUNDED},
            {"truth": TruthStatus.SUPPORTED},
        ):
            with self.subTest(kwargs=kwargs):
                candidate = make_candidate(self.observation, **kwargs)
                pipeline = ObservationCandidatePipeline(
                    Extractor([candidate]), self.observation_store, self.candidate_store,
                )
                with self.assertRaises(SemanticExtractionError):
                    self.run_pipeline(pipeline)
        self.candidate_store.record_candidate.assert_not_called()

    def test_rejects_duplicate_ids_before_any_append(self):
        candidate = make_candidate(self.observation)
        pipeline = ObservationCandidatePipeline(
            Extractor([candidate, candidate]), self.observation_store, self.candidate_store,
        )
        with self.assertRaisesRegex(SemanticExtractionError, "duplicate"):
            self.run_pipeline(pipeline)
        self.candidate_store.record_candidate.assert_not_called()

    def test_rejects_batch_over_limit_before_any_append(self):
        candidates = [
            make_candidate(self.observation, record_id="candidate-1"),
            make_candidate(self.observation, record_id="candidate-2"),
        ]
        pipeline = ObservationCandidatePipeline(
            Extractor(candidates), self.observation_store, self.candidate_store,
            max_candidates_per_observation=1,
        )
        with self.assertRaisesRegex(SemanticExtractionError, "limit"):
            self.run_pipeline(pipeline)
        self.candidate_store.record_candidate.assert_not_called()

    def test_rejects_unparseable_observation(self):
        observation = make_observation(parse_status=ParseStatus.UNPARSEABLE)
        receipt = receipt_for(observation)
        self.observation_store.get_observation.return_value = observation
        self.observation_store.get_receipt.return_value = receipt
        with self.assertRaisesRegex(SemanticExtractionError, "not extractable"):
            self.run_pipeline(observation=observation, receipt=receipt)
        self.candidate_store.record_candidate.assert_not_called()

    def test_marks_partial_parse_without_promoting_it(self):
        observation = make_observation(parse_status=ParseStatus.PARTIAL)
        receipt = receipt_for(observation)
        self.observation_store.get_observation.return_value = observation
        self.observation_store.get_receipt.return_value = receipt
        candidate = make_candidate(observation)
        pipeline = ObservationCandidatePipeline(
            Extractor([candidate]), self.observation_store, self.candidate_store,
        )
        result = self.run_pipeline(pipeline, observation, receipt)
        self.assertTrue(result.partial_observation)


if __name__ == "__main__":
    unittest.main()
