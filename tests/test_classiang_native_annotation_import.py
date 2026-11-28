from __future__ import annotations

from dataclasses import asdict, replace
import json
import tempfile
import unittest
from pathlib import Path

from prototype.classiang_native import EvidenceRef, Relation, Symbol, SymbolGraph
from prototype.classiang_native_review_queue import build_native_relation_review_queue
from prototype.classiang_native_annotation_import import (
    NativeAnnotationImportError, _canonical_digest, import_adjudicated_rows,
)
from prototype.yixiang_annotation_adjudication import (
    FinalAdjudication, IndependentAnnotation, ReviewPacket, SourceVerification,
)


class NativeAnnotationImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        evidence = (
            EvidenceRef("e1", "source", "family", "loc:1", "license", True),
            EvidenceRef("e2", "source", "family", "loc:2", "license", True),
        )
        symbols = (
            Symbol("s1", "classical", "entity", (), ("e1",)),
            Symbol("s2", "classical", "entity", (), ("e1",)),
            Symbol("s3", "classical", "entity", (), ("e2",)),
        )
        relations = (
            Relation("r1", "structural", (("left", "s1"), ("right", "s2")), ("e1",)),
            Relation("r2", "functional", (("agent", "s2"), ("patient", "s3")), ("e2",)),
        )
        self.graph = SymbolGraph(evidence, symbols, relations)
        self.queue = build_native_relation_review_queue(self.graph)
        self.queue_path = self.root / "queue.json"
        self.queue_path.write_text(json.dumps(self.queue), encoding="utf-8")
        self.item = self.queue["items"][0]

    def packet(self):
        source = SourceVerification(
            "critical_edition", "work", "edition", "witness", "卷一/段一",
            "经核验的原文", ("scan:1",), ("collator",), "已逐字核验",
        )
        def annotation(reviewer):
            return IndependentAnnotation(
                reviewer, "accept", "两项关系在指定范围内可组合。", "main_text",
                ("shared invariant",), (), (), ("role preservation",), (),
                "unknown", ("passage:1",), "独立审阅并记录依据。",
            )
        final = FinalAdjudication(
            "accept", "adjudicator", "两份独立审阅一致，来源与适用范围满足要求。",
            ("decision:1",), "两项关系在指定范围内可组合。", "main_text",
            ("structural",), ("shared invariant",), (), ("specified domain",),
            ("role preservation",), (), "unknown",
        )
        return ReviewPacket(
            "case", "structural_similarity", "group:work", source,
            (annotation("reviewer-a"), annotation("reviewer-b")), final,
        )

    def row(self, packet=None):
        return {
            "review_item_id": self.item["review_item_id"],
            "m19": asdict(packet or self.packet()),
            "m19_reference_map": {"scan:1": {}, "passage:1": {}, "decision:1": {}},
            "native_evidence_map": {"e1": [{}], "e2": [{}]},
            "m2": {"case": {}, "split": "train"},
        }

    def write_rows(self, rows):
        path = self.root / "adjudications.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_imports_adjudicated_pair_and_preserves_admission_bundle(self):
        path = self.write_rows([self.row()])
        labels, admissions = import_adjudicated_rows(
            graph=self.graph, queue_path=self.queue_path, adjudications_path=path,
        )
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0]["label"], 1)
        self.assertEqual(labels[0]["label_basis"], "human_reviewed_pair")
        self.assertEqual(labels[0]["reviewer_id"], "reviewer-a")
        self.assertEqual(labels[0]["adjudication_id"], "adjudicator")
        self.assertEqual(admissions[0]["m2"], self.row()["m2"])

    def test_rejects_non_adjudicated_packet(self):
        packet = replace(self.packet(), adjudication=None)
        path = self.write_rows([self.row(packet)])
        with self.assertRaisesRegex(NativeAnnotationImportError, "not Gold-eligible"):
            import_adjudicated_rows(
                graph=self.graph, queue_path=self.queue_path, adjudications_path=path,
            )

    def test_rejects_unknown_queue_item(self):
        row = self.row()
        row["review_item_id"] = "not-in-queue"
        path = self.write_rows([row])
        with self.assertRaisesRegex(NativeAnnotationImportError, "unknown queue item"):
            import_adjudicated_rows(
                graph=self.graph, queue_path=self.queue_path, adjudications_path=path,
            )

    def test_rejects_tampered_queue_digest(self):
        queue = dict(self.queue)
        queue["items"] = []
        self.queue_path.write_text(json.dumps(queue), encoding="utf-8")
        path = self.write_rows([])
        with self.assertRaisesRegex(NativeAnnotationImportError, "digest mismatch"):
            import_adjudicated_rows(
                graph=self.graph, queue_path=self.queue_path, adjudications_path=path,
            )


if __name__ == "__main__":
    unittest.main()
