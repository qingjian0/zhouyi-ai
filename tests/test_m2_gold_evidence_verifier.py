from __future__ import annotations

import hashlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from prototype.evidence_ref_resolver import (
    EvidenceResolutionError,
    SQLiteEvidenceRefResolver,
)
from prototype.m2_extraction_dataset import (
    AnnotationStatus,
    AnnotatedExtractionRecord,
    DatasetSplit,
    GoldUnitEvidenceSpan,
)
from prototype.m2_extraction_evaluation import ExtractionGoldCase, GoldSemanticUnit
from prototype.m2_gold_evidence_verifier import (
    GoldEvidenceVerificationError,
    verify_gold_evidence_spans,
)
from prototype.observation_contract import UnitKind
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor


class GoldEvidenceVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "m1.sqlite3"
        self.ingestor = SQLiteEvidenceIngestor(self.database)
        self.resolver = SQLiteEvidenceRefResolver(self.database)

    def make_record(self, text: bytes = b"alpha beta gamma"):
        result = self.ingestor.ingest(
            "doc-gold", "gold.txt", io.BytesIO(text), chunk_bytes=max(4, len(text)),
        )
        self.assertTrue(result.complete)
        chunk = self.ingestor.get_chunks("doc-gold", limit=10)[0]
        reference = self.resolver.make_reference("doc-gold", chunk.chunk_id)
        case = ExtractionGoldCase(
            "case-gold", "general",
            (GoldSemanticUnit(UnitKind.CONCEPT, "concept:alpha"),),
        )
        span = GoldUnitEvidenceSpan(
            unit_index=0, evidence_ref=reference, byte_start=0, byte_end=5,
            span_sha256=hashlib.sha256(b"alpha").hexdigest(),
        )
        record = AnnotatedExtractionRecord(
            case=case, split=DatasetSplit.TRAIN,
            source_lineage_ids=("lineage:gold",), evidence_refs=(reference,),
            annotation_status=AnnotationStatus.REVIEWED, gold_evidence_spans=(span,),
        )
        return record, reference, chunk

    def test_verifies_gold_span_against_real_m1_bytes(self):
        record, _, _ = self.make_record()
        receipt = verify_gold_evidence_spans(record, self.resolver)
        self.assertEqual(receipt.case_id, "case-gold")
        self.assertEqual(receipt.verified_span_count, 1)
        self.assertEqual(receipt.verified_unit_count, 1)
        self.assertEqual(len(receipt.verification_sha256), 64)

    def test_rejects_wrong_gold_span_digest(self):
        record, reference, _ = self.make_record()
        bad_span = GoldUnitEvidenceSpan(
            unit_index=0, evidence_ref=reference, byte_start=0, byte_end=5,
            span_sha256="0" * 64,
        )
        bad_record = AnnotatedExtractionRecord(
            case=record.case, split=record.split,
            source_lineage_ids=record.source_lineage_ids,
            evidence_refs=record.evidence_refs,
            annotation_status=record.annotation_status,
            gold_evidence_spans=(bad_span,),
        )
        with self.assertRaisesRegex(GoldEvidenceVerificationError, "span digest mismatch"):
            verify_gold_evidence_spans(bad_record, self.resolver)

    def test_rejects_m1_source_tampering_before_span_verification(self):
        record, reference, chunk = self.make_record()
        with sqlite3.connect(self.database) as db:
            db.execute(
                "UPDATE evidence_chunks SET text_utf8 = ? WHERE chunk_id = ?",
                (b"omega beta gamma", chunk.chunk_id),
            )
        with self.assertRaises(GoldEvidenceVerificationError):
            verify_gold_evidence_spans(record, self.resolver)

    def test_no_answer_case_still_resolves_its_source_context(self):
        self.ingestor.ingest(
            "doc-negative", "negative.txt", io.BytesIO(b"no matching fact"),
            chunk_bytes=64,
        )
        chunk = self.ingestor.get_chunks("doc-negative")[0]
        reference = self.resolver.make_reference("doc-negative", chunk.chunk_id)
        record = AnnotatedExtractionRecord(
            case=ExtractionGoldCase("negative", "general", ()),
            split=DatasetSplit.TRAIN, source_lineage_ids=("negative-lineage",),
            evidence_refs=(reference,), annotation_status=AnnotationStatus.REVIEWED,
        )
        receipt = verify_gold_evidence_spans(record, self.resolver)
        self.assertEqual(receipt.verified_span_count, 0)
        self.assertEqual(receipt.verified_unit_count, 0)
        self.assertEqual(receipt.resolved_evidence_refs, (reference,))

    def test_rejects_resolver_that_returns_different_reference(self):
        record, reference, _ = self.make_record()

        class WrongResolver:
            def resolve(self, _):
                class Result:
                    reference = None
                    text = "alpha beta gamma"
                return Result()

        with self.assertRaisesRegex(GoldEvidenceVerificationError, "different reference"):
            verify_gold_evidence_spans(record, WrongResolver())


if __name__ == "__main__":
    unittest.main()
