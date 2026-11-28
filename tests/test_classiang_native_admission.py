from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from prototype.classiang_native import EvidenceRef as NativeEvidenceRef, Relation, Symbol, SymbolGraph
from prototype.classiang_native_admission import (
    NativeGoldAdmissionError, verify_native_gold_admission,
)
from prototype.classiang_native_learning import CompositionLabel
from prototype.evidence_ref_resolver import SQLiteEvidenceRefResolver
from prototype.m2_extraction_dataset import (
    AnnotationStatus, AnnotatedExtractionRecord, DatasetSplit, GoldUnitEvidenceSpan,
)
from prototype.m2_extraction_evaluation import ExtractionGoldCase, GoldSemanticUnit
from prototype.observation_contract import UnitKind
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor
from prototype.yixiang_annotation_adjudication import (
    FinalAdjudication, IndependentAnnotation, ReviewPacket, SourceVerification,
)


class NativeGoldAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "m1.sqlite3"
        self.ingestor = SQLiteEvidenceIngestor(self.database)
        self.resolver = SQLiteEvidenceRefResolver(self.database)
        source = "白马，马也。".encode("utf-8")
        result = self.ingestor.ingest(
            "work-mozi", "mozi.txt", io.BytesIO(source), chunk_bytes=64,
        )
        self.assertTrue(result.complete)
        chunk = self.ingestor.get_chunks("work-mozi")[0]
        self.m1_ref = self.resolver.make_reference("work-mozi", chunk.chunk_id)

    def packet(self):
        source = SourceVerification(
            "critical_edition", "mozi-xiaoqu", "critical-edition-1",
            "witness-a", "卷十一/小取/段3", "白马，马也。",
            ("scan:page-11",), ("collator-1",), "影印页与转录逐字核对",
        )
        def annotation(reviewer):
            return IndependentAnnotation(
                reviewer, "accept", "白马属于马类。", "main_text",
                ("category-membership",), (), (), ("predicate-preservation",),
                (), "unknown", ("passage:3",), "依据所引文本与上下文作出标注。",
            )
        final = FinalAdjudication(
            "accept", "adjudicator-c", "经复核原文、异文与两份独立标注，形成最终裁决。",
            ("adjudication:record-1",), "白马属于马类。", "main_text",
            ("structural",), ("category-membership",), (), (), ("predicate-preservation",),
            (), "unknown",
        )
        return ReviewPacket(
            "case-1", "taxonomic_similarity", "work:mozi-xiaoqu",
            source, (annotation("reviewer-a"), annotation("reviewer-b")), final,
        )

    def graph_and_label(self):
        evidence = (
            NativeEvidenceRef("native-e1", "source-1", "family-1", "span:0", "license-1", True),
            NativeEvidenceRef("native-e2", "source-1", "family-1", "span:1", "license-1", True),
        )
        symbols = (
            Symbol("subject", "classical", "entity", (("name", "白马"),), ("native-e1", "native-e2")),
            Symbol("aspect-a", "classical", "concept", (("name", "马"),), ("native-e1",)),
            Symbol("aspect-b", "classical", "concept", (("name", "白"),), ("native-e2",)),
        )
        relations = (
            Relation("relation-1", "has_aspect", (("subject", "subject"), ("aspect", "aspect-a")), ("native-e1",)),
            Relation("relation-2", "has_aspect", (("subject", "subject"), ("aspect", "aspect-b")), ("native-e2",)),
        )
        graph = SymbolGraph(evidence, symbols, relations)
        label = CompositionLabel(
            example_id="example-1", group_id="group-1", source_family="family-1",
            relation_ids=("relation-1", "relation-2"),
            evidence_ids=("native-e1", "native-e2"), label=1, reviewed=True,
            label_basis="human_reviewed_pair", reviewer_id="reviewer-a",
            adjudication_id="adjudicator-c", scope="taxonomic",
            conditions=("unconditional",),
        )
        return graph, label

    def record(self):
        span = GoldUnitEvidenceSpan(
            0, self.m1_ref, 0, len("白马".encode("utf-8")),
            hashlib.sha256("白马".encode("utf-8")).hexdigest(),
        )
        return AnnotatedExtractionRecord(
            ExtractionGoldCase(
                "case-1", "classical", (GoldSemanticUnit(UnitKind.CONCEPT, "concept:horse"),),
            ),
            DatasetSplit.TRAIN,
            ("mozi-xiaoqu", "critical-edition-1", "witness-a"),
            (self.m1_ref,), AnnotationStatus.ADJUDICATED, (span,),
        )

    def test_accepts_only_when_m19_native_and_m1_m2_evidence_converge(self):
        graph, label = self.graph_and_label()
        m19_map = {
            key: self.m1_ref
            for key in ("scan:page-11", "passage:3", "adjudication:record-1")
        }
        native_map = {"native-e1": (self.m1_ref,), "native-e2": (self.m1_ref,)}
        receipt = verify_native_gold_admission(
            packet=self.packet(), record=self.record(), graph=graph, label=label,
            resolver=self.resolver, m19_reference_map=m19_map,
            native_evidence_map=native_map, expected_split=DatasetSplit.TRAIN,
        )
        self.assertEqual(receipt.case_id, "case-1")
        self.assertEqual(receipt.verified_span_count, 1)
        self.assertEqual(receipt.m1_reference_count, 1)
        self.assertEqual(len(receipt.m2_verification_sha256), 64)

    def test_rejects_missing_m19_to_m1_mapping(self):
        graph, label = self.graph_and_label()
        with self.assertRaisesRegex(NativeGoldAdmissionError, "M19 evidence references"):
            verify_native_gold_admission(
                packet=self.packet(), record=self.record(), graph=graph, label=label,
                resolver=self.resolver, m19_reference_map={},
                native_evidence_map={"native-e1": (self.m1_ref,), "native-e2": (self.m1_ref,)},
                expected_split=DatasetSplit.TRAIN,
            )

    def test_rejects_missing_native_evidence_mapping(self):
        graph, label = self.graph_and_label()
        with self.assertRaisesRegex(NativeGoldAdmissionError, "native graph evidence"):
            verify_native_gold_admission(
                packet=self.packet(), record=self.record(), graph=graph, label=label,
                resolver=self.resolver,
                m19_reference_map={
                    key: self.m1_ref
                    for key in ("scan:page-11", "passage:3", "adjudication:record-1")
                },
                native_evidence_map={"native-e1": (self.m1_ref,)},
                expected_split=DatasetSplit.TRAIN,
            )

    def test_rejects_m1_ref_not_bound_to_an_m2_span(self):
        graph, label = self.graph_and_label()
        m19_map = {
            key: self.m1_ref
            for key in ("scan:page-11", "passage:3", "adjudication:record-1")
        }
        native_map = {"native-e1": (self.m1_ref,), "native-e2": (self.m1_ref,)}
        # The exact M1 bytes are checked by the real SQLite resolver in the
        # successful test; this case removes all span anchors at DTO creation.
        with self.assertRaises(ValueError):
            AnnotatedExtractionRecord(
                self.record().case, DatasetSplit.TRAIN,
                self.record().source_lineage_ids, (self.m1_ref,),
                AnnotationStatus.ADJUDICATED, (),
            )

    def test_rejects_label_conflicting_with_final_adjudication(self):
        graph, label = self.graph_and_label()
        rejected = CompositionLabel(
            **{**label.__dict__, "label": 0},
        )
        with self.assertRaisesRegex(NativeGoldAdmissionError, "conflicts"):
            verify_native_gold_admission(
                packet=self.packet(), record=self.record(), graph=graph, label=rejected,
                resolver=self.resolver,
                m19_reference_map={
                    key: self.m1_ref
                    for key in ("scan:page-11", "passage:3", "adjudication:record-1")
                },
                native_evidence_map={"native-e1": (self.m1_ref,), "native-e2": (self.m1_ref,)},
                expected_split=DatasetSplit.TRAIN,
            )


if __name__ == "__main__":
    unittest.main()
