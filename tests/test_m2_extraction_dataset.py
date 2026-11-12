from __future__ import annotations

import unittest

from prototype.m2_extraction_dataset import (
    AnnotationStatus,
    AnnotatedExtractionRecord,
    DatasetSplit,
    ExtractionDatasetManifest,
    GoldUnitEvidenceSpan,
)
from prototype.m2_extraction_evaluation import ExtractionGoldCase, GoldSemanticUnit
from prototype.observation_contract import EvidenceRef, UnitKind


def ref(document_id: str, chunk_id: str = "chunk") -> EvidenceRef:
    return EvidenceRef(
        document_id=document_id, chunk_id=chunk_id, content_sha256="a" * 64,
        byte_start=0, byte_end=10, source_version="v1",
    )


def record(
    case_id: str,
    split: DatasetSplit,
    *,
    domain: str = "general",
    document_id: str | None = None,
    lineage: str | None = None,
    status: AnnotationStatus | None = None,
) -> AnnotatedExtractionRecord:
    case = ExtractionGoldCase(
        case_id, domain, (GoldSemanticUnit(UnitKind.CONCEPT, f"concept:{case_id}"),),
    )
    evidence_ref = ref(document_id or f"doc:{case_id}")
    return AnnotatedExtractionRecord(
        case=case,
        split=split,
        source_lineage_ids=(lineage or f"lineage:{case_id}",),
        evidence_refs=(evidence_ref,),
        annotation_status=status or (
            AnnotationStatus.REVIEWED if split is DatasetSplit.TRAIN
            else AnnotationStatus.ADJUDICATED
        ),
        gold_evidence_spans=(GoldUnitEvidenceSpan(
            unit_index=0, evidence_ref=evidence_ref, byte_start=0, byte_end=4,
            span_sha256="b" * 64,
        ),),
    )


class ExtractionDatasetManifestTests(unittest.TestCase):
    def manifest(self, records):
        return ExtractionDatasetManifest(
            dataset_id="m2-gold", dataset_version="1.0.0",
            annotation_schema_version="m2-gold-v1", records=tuple(records),
        )

    def test_accepts_isolated_train_validation_test_splits(self):
        manifest = self.manifest([
            record("train-1", DatasetSplit.TRAIN),
            record("valid-1", DatasetSplit.VALIDATION),
            record("test-1", DatasetSplit.TEST),
        ])
        summary = manifest.split_summary()
        self.assertEqual(summary["case_count"], 3)
        self.assertEqual(summary["split_case_counts"]["train"], 1)
        self.assertEqual(summary["split_case_counts"]["validation"], 1)
        self.assertEqual(summary["split_case_counts"]["test"], 1)
        self.assertEqual(summary["annotated_unit_count"], 3)
        self.assertEqual(summary["gold_evidence_span_count"], 3)
        self.assertEqual(len(summary["manifest_sha256"]), 64)
        self.assertIn('"dataset_id":"m2-gold"', manifest.to_canonical_json())

    def test_rejects_source_lineage_leakage(self):
        with self.assertRaisesRegex(ValueError, "source lineage leakage"):
            self.manifest([
                record("train-1", DatasetSplit.TRAIN, lineage="same-source"),
                record("test-1", DatasetSplit.TEST, lineage="same-source"),
            ])

    def test_rejects_document_leakage_even_with_different_lineage(self):
        with self.assertRaisesRegex(ValueError, "document leakage"):
            self.manifest([
                record("train-1", DatasetSplit.TRAIN, document_id="same-doc", lineage="lineage-a"),
                record("test-1", DatasetSplit.TEST, document_id="same-doc", lineage="lineage-b"),
            ])

    def test_rejects_unevaluated_gold_annotations(self):
        with self.assertRaisesRegex(ValueError, "must be adjudicated"):
            record("test-1", DatasetSplit.TEST, status=AnnotationStatus.REVIEWED)

    def test_ood_domain_must_not_appear_in_other_splits(self):
        with self.assertRaisesRegex(ValueError, "OOD domain leakage"):
            self.manifest([
                record("train-1", DatasetSplit.TRAIN, domain="finance"),
                record("ood-1", DatasetSplit.OOD_TEST, domain="finance"),
            ])

    def test_ood_domain_is_allowed_when_held_out(self):
        manifest = self.manifest([
            record("train-1", DatasetSplit.TRAIN, domain="general"),
            record("ood-1", DatasetSplit.OOD_TEST, domain="biomedical"),
        ])
        self.assertEqual(manifest.split_summary()["split_case_counts"]["ood_test"], 1)

    def test_case_ids_must_be_unique(self):
        with self.assertRaisesRegex(ValueError, "globally unique"):
            self.manifest([
                record("same", DatasetSplit.TRAIN),
                record("same", DatasetSplit.TEST, document_id="other-doc"),
            ])

    def test_record_requires_source_lineage_and_evidence(self):
        with self.assertRaisesRegex(ValueError, "lineage IDs"):
            AnnotatedExtractionRecord(
                case=ExtractionGoldCase("x", "general", ()),
                split=DatasetSplit.TRAIN, source_lineage_ids=(), evidence_refs=(ref("doc"),),
                annotation_status=AnnotationStatus.REVIEWED,
            )

    def test_every_positive_gold_unit_requires_a_source_span(self):
        evidence_ref = ref("doc")
        with self.assertRaisesRegex(ValueError, "requires at least one source evidence span"):
            AnnotatedExtractionRecord(
                case=ExtractionGoldCase(
                    "x", "general", (GoldSemanticUnit(UnitKind.CONCEPT, "x"),),
                ),
                split=DatasetSplit.TRAIN, source_lineage_ids=("lineage",),
                evidence_refs=(evidence_ref,), annotation_status=AnnotationStatus.REVIEWED,
            )

    def test_gold_span_must_be_inside_evidence_ref(self):
        evidence_ref = ref("doc")
        with self.assertRaisesRegex(ValueError, "inside its EvidenceRef"):
            GoldUnitEvidenceSpan(
                unit_index=0, evidence_ref=evidence_ref, byte_start=0, byte_end=11,
                span_sha256="b" * 64,
            )

    def test_gold_span_must_reference_record_evidence(self):
        with self.assertRaisesRegex(ValueError, "outside the record"):
            case = ExtractionGoldCase(
                "x", "general", (GoldSemanticUnit(UnitKind.CONCEPT, "x"),),
            )
            AnnotatedExtractionRecord(
                case=case, split=DatasetSplit.TRAIN, source_lineage_ids=("lineage",),
                evidence_refs=(ref("doc-a"),), annotation_status=AnnotationStatus.REVIEWED,
                gold_evidence_spans=(GoldUnitEvidenceSpan(
                    unit_index=0, evidence_ref=ref("doc-b"), byte_start=0, byte_end=4,
                    span_sha256="b" * 64,
                ),),
            )

    def test_gold_span_unit_index_must_be_in_range(self):
        with self.assertRaisesRegex(ValueError, "outside expected_units"):
            AnnotatedExtractionRecord(
                case=ExtractionGoldCase(
                    "x", "general", (GoldSemanticUnit(UnitKind.CONCEPT, "x"),),
                ),
                split=DatasetSplit.TRAIN, source_lineage_ids=("lineage",),
                evidence_refs=(ref("doc"),), annotation_status=AnnotationStatus.REVIEWED,
                gold_evidence_spans=(GoldUnitEvidenceSpan(
                    unit_index=1, evidence_ref=ref("doc"), byte_start=0, byte_end=4,
                    span_sha256="b" * 64,
                ),),
            )


if __name__ == "__main__":
    unittest.main()
