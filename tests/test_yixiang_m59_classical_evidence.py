import unittest

from prototype.yixiang_m59_classical_evidence import (
    SCHEMA_VERSION, audit_corpus, validate_record, validate_split_assignments,
)


def fixture(record_id="record-1", split="train", work_group="work-A",
            dependence_group="text-A", work_period="pre_qing",
            policy="core_pre_qing", source_kind="primary_text"):
    text = "天地定位，山泽通气。"
    quote = "天地定位"
    start = text.index(quote)
    return {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id,
        "source": {
            "work_id": "zhouyi-xici", "title": "周易·系辞传",
            "composition_period": "pre-Qin (traditional attribution; dating contested)",
            "work_period_class": work_period,
            "source_kind": source_kind,
            "evidence_policy": policy,
            "work_lineage_group": work_group,
            "text_dependence_group": dependence_group,
        },
        "witnesses": [{
            "witness_id": "witness-1", "edition": "test transcription",
            "witness_period_class": "uncertain", "locator": "chapter/test",
            "text": text,
        }],
        "evidence_spans": [{
            "span_id": "span-1", "witness_id": "witness-1",
            "start": start, "end": start + len(quote), "quote": quote,
        }],
        "claims": [{
            "claim_id": "claim-1", "subject_role": "heaven",
            "predicate": "orders_position_with", "object_role": "earth",
            "claim_status": "explicit", "evidence_span_ids": ["span-1"],
        }],
        "independent_annotations": [
            {"annotator_id": "a1", "decisions": {"claim-1": "accept"}},
            {"annotator_id": "a2", "decisions": {"claim-1": "accept"}},
        ],
        "adjudication": {"status": "pending", "decisions": {}},
        "split": split,
    }


class M59ClassicalEvidenceTests(unittest.TestCase):
    def test_valid_record_requires_exact_source_offsets_and_two_annotators(self):
        validate_record(fixture())

    def test_quote_must_match_witness_offsets_exactly(self):
        record = fixture()
        record["evidence_spans"][0]["quote"] = "山泽通气"
        with self.assertRaisesRegex(ValueError, "evidence_quote_offset_mismatch"):
            validate_record(record)

    def test_post_qing_material_cannot_be_core_primary_evidence(self):
        record = fixture(work_period="qing_and_after", policy="core_pre_qing")
        with self.assertRaisesRegex(ValueError, "post_qing_or_uncertain_source_cannot_be_core"):
            validate_record(record)

    def test_modern_commentary_is_secondary_only(self):
        record = fixture(source_kind="modern_commentary", policy="core_pre_qing")
        with self.assertRaisesRegex(ValueError, "commentary_cannot_be_core_primary_evidence"):
            validate_record(record)

    def test_independent_annotators_must_be_distinct(self):
        record = fixture()
        record["independent_annotations"][1]["annotator_id"] = "a1"
        with self.assertRaisesRegex(ValueError, "annotators_must_be_distinct"):
            validate_record(record)

    def test_work_and_text_lineage_must_not_cross_splits(self):
        records = [
            fixture(record_id="r1", split="train"),
            fixture(record_id="r2", split="test"),
        ]
        with self.assertRaisesRegex(ValueError, "crosses_splits"):
            validate_split_assignments(records)

    def test_audit_reports_source_policy_and_split_counts(self):
        records = [fixture()]
        report = audit_corpus(records)
        self.assertEqual(report["records"], 1)
        self.assertEqual(report["work_period_counts"]["pre_qing"], 1)
        self.assertTrue(report["all_evidence_spans_exact"])


if __name__ == "__main__":
    unittest.main()
