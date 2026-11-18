import unittest

from prototype.observation_contract import (
    ContractError,
    EpistemicStatus,
    EvidenceRef,
    ExtractionMethod,
    GroundingStatus,
    Modality,
    Observation,
    ParseStatus,
    RecordEnvelope,
    RoleBinding,
    Score,
    SemanticUnitCandidate,
    SourceLocator,
    TruthStatus,
    TypedAttribute,
    UnitKind,
    canonical_json,
    record_digest,
)


def evidence(start=0, end=12):
    return EvidenceRef(
        document_id="doc-1",
        chunk_id="chunk-1",
        content_sha256="a" * 64,
        byte_start=start,
        byte_end=end,
        source_version="sha256:source-v1",
    )


def envelope(kind):
    return RecordEnvelope(
        schema_version="m2-record-v1",
        record_id=f"{kind.lower()}-1",
        record_kind=kind,
        producer="test-extractor",
        producer_version="1.0",
        recorded_at="2026-11-12T00:00:00Z",
        scope="test-scope",
        source_refs=(evidence(),),
    )


class EvidenceRefTests(unittest.TestCase):
    def test_rejects_bad_hash_and_empty_or_reversed_spans(self):
        with self.assertRaises(ContractError):
            EvidenceRef("doc", "chunk", "not-a-hash", 0, 1, "v1")
        with self.assertRaises(ContractError):
            evidence(4, 4)
        with self.assertRaises(ContractError):
            evidence(True, 4)

    def test_half_open_span_and_source_version_are_preserved(self):
        item = evidence(3, 9)
        self.assertEqual((item.byte_start, item.byte_end), (3, 9))
        self.assertEqual(item.source_version, "sha256:source-v1")


class SourceLocatorTests(unittest.TestCase):
    def test_text_requires_exact_byte_span(self):
        with self.assertRaises(ContractError):
            SourceLocator(Modality.TEXT, "v1")
        locator = SourceLocator(Modality.TEXT, "v1", byte_start=0, byte_end=5)
        self.assertEqual(locator.byte_end, 5)

    def test_modality_specific_locators_are_validated(self):
        with self.assertRaises(ContractError):
            SourceLocator(Modality.PDF, "pdf-v1")
        with self.assertRaises(ContractError):
            SourceLocator(Modality.IMAGE, "img-v1")
        with self.assertRaises(ContractError):
            SourceLocator(Modality.AUDIO, "audio-v1")
        pdf = SourceLocator(Modality.PDF, "pdf-v1", page_number=1)
        image = SourceLocator(Modality.IMAGE, "img-v1", region_xywh=(0, 0, 10, 20))
        audio = SourceLocator(Modality.AUDIO, "audio-v1", time_start_ms=0, time_end_ms=500)
        self.assertEqual(pdf.page_number, 1)
        self.assertEqual(image.region_xywh[2], 10)
        self.assertEqual(audio.time_end_ms, 500)

    def test_rejects_non_finite_or_invalid_media_ranges(self):
        with self.assertRaises(ContractError):
            SourceLocator(Modality.IMAGE, "v1", region_xywh=(0, 0, float("nan"), 1))
        with self.assertRaises(ContractError):
            SourceLocator(Modality.VIDEO, "v1", time_start_ms=4, time_end_ms=4)


class ObservationTests(unittest.TestCase):
    def test_valid_observation_keeps_extraction_score_semantics_explicit(self):
        locator = SourceLocator(Modality.TEXT, "source-v1", byte_start=0, byte_end=12)
        item = Observation(
            envelope("Observation"),
            Modality.TEXT,
            locator,
            "ocr-v2",
            "2.1",
            ExtractionMethod.MODEL,
            ParseStatus.PARSED,
            extraction_score=Score(0.91, "extractor-confidence"),
        )
        self.assertEqual(item.extraction_score.semantics, "extractor-confidence")

    def test_rejects_locator_modality_mismatch_and_envelope_kind(self):
        with self.assertRaises(ContractError):
            Observation(
                envelope("Observation"),
                Modality.TEXT,
                SourceLocator(Modality.PDF, "pdf-v1", page_number=1),
                "parser", "1", ExtractionMethod.RULE, ParseStatus.PARSED,
            )
        with self.assertRaises(ContractError):
            Observation(
                envelope("SemanticUnitCandidate"),
                Modality.TEXT,
                SourceLocator(Modality.TEXT, "v1", byte_start=0, byte_end=1),
                "parser", "1", ExtractionMethod.RULE, ParseStatus.PARSED,
            )


class SemanticCandidateTests(unittest.TestCase):
    def make_candidate(self, **changes):
        values = dict(
            envelope=envelope("SemanticUnitCandidate"),
            kind=UnitKind.EVENT,
            surface_forms=("甲使用工具处理乙",),
            typed_attributes=(
                TypedAttribute("temperature", "number", 38.0, "C", (evidence(),)),
            ),
            role_bindings=(
                RoleBinding("agent", "entity:甲"),
                RoleBinding("instrument", "entity:工具"),
                RoleBinding("patient", "entity:乙"),
            ),
            grounding_status=GroundingStatus.GROUNDED,
            epistemic_status=EpistemicStatus.ASSERTED,
            truth_status=TruthStatus.UNKNOWN,
            extractor_confidence=0.8,
        )
        values.update(changes)
        return SemanticUnitCandidate(**values)

    def test_grounding_is_not_truth(self):
        candidate = self.make_candidate()
        self.assertEqual(candidate.grounding_status, GroundingStatus.GROUNDED)
        self.assertEqual(candidate.truth_status, TruthStatus.UNKNOWN)

    def test_truth_status_is_explicit_and_independent_of_grounding(self):
        candidate = self.make_candidate(truth_status=TruthStatus.SUPPORTED)
        self.assertEqual(candidate.grounding_status, GroundingStatus.GROUNDED)
        self.assertEqual(candidate.truth_status, TruthStatus.SUPPORTED)

    def test_role_bindings_preserve_order_and_named_roles(self):
        candidate = self.make_candidate()
        self.assertEqual(
            [(x.role_name, x.target_ref) for x in candidate.role_bindings],
            [("agent", "entity:甲"), ("instrument", "entity:工具"), ("patient", "entity:乙")],
        )

    def test_score_fields_are_not_interchangeable(self):
        with self.assertRaises(ContractError):
            self.make_candidate(extractor_confidence=1.1)
        with self.assertRaises(ContractError):
            self.make_candidate(ranking_score=0.7)

    def test_attributes_require_source_references(self):
        with self.assertRaises(ContractError):
            TypedAttribute("age", "integer", 18)


class SerializationTests(unittest.TestCase):
    def test_digest_is_stable_and_sensitive_to_content(self):
        one = self.make_envelope()
        two = self.make_envelope()
        self.assertEqual(canonical_json(one), canonical_json(two))
        self.assertEqual(record_digest(one), record_digest(two))
        changed = RecordEnvelope(
            schema_version=one.schema_version,
            record_id=one.record_id,
            record_kind=one.record_kind,
            producer=one.producer,
            producer_version="2.0",
            recorded_at=one.recorded_at,
            scope=one.scope,
            source_refs=one.source_refs,
        )
        self.assertNotEqual(record_digest(one), record_digest(changed))

    @staticmethod
    def make_envelope():
        return envelope("Observation")


if __name__ == "__main__":
    unittest.main()
