import unittest

from prototype.yixiang_m59_classical_evidence import (
    SCHEMA_VERSION, audit_corpus, validate_record, validate_split_assignments,
)


def fixture(record_id="record-1", split="train", work_group="work-A",
            dependence_group="text-A", work_period="pre_qing",
            policy="core_pre_qing", source_kind="primary_text"):
    text = "甲乙相应，丙丁相制。"
    quote = "甲乙相应"
    start = text.index(quote)
    return {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id,
        "source": {
            "work_id": "synthetic-fixture", "title": "Synthetic test fixture",
            "composition_period": "synthetic; no historical dating claim",
            "attribution": "synthetic fixture generator",
            "attribution_status": "unknown",
            "work_period_class": work_period,
            "source_kind": source_kind,
            "evidence_policy": policy,
            "work_lineage_group": work_group,
            "text_dependence_group": dependence_group,
        },
        "witnesses": [{
            "witness_id": "witness-1", "edition": "synthetic fixture transcription",
            "publisher": "test fixture", "publication_date": "not applicable",
            "digitization_source": "generated test string", "source_uri": "urn:synthetic:test-fixture",
            "access_date": "2026-11-14", "witness_period_class": "pre_qing",
            "locator": "synthetic/test",
            "transcription_method": "generated_test_fixture",
            "transcription_review_status": "unreviewed",
            "variants": [], "text": text,
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

    def test_pre_qing_work_with_only_late_witness_cannot_enter_core(self):
        record = fixture()
        record["witnesses"][0]["witness_period_class"] = "qing_and_after"
        with self.assertRaisesRegex(ValueError, "core_primary_text_requires_pre_qing_witness"):
            validate_record(record)

    def test_unresolvable_witness_identifier_is_rejected(self):
        record = fixture()
        record["witnesses"][0]["source_uri"] = "not-a-source"
        with self.assertRaisesRegex(ValueError, "invalid_witness_source_uri"):
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

    def test_invalid_admission_stage_is_rejected(self):
        record = fixture()
        record["admission_status"] = "almost_gold"
        with self.assertRaisesRegex(ValueError, "invalid_admission_status"):
            validate_record(record)

    def test_adjudicated_stage_requires_final_adjudication(self):
        record = fixture()
        record["admission_status"] = "adjudicated"
        with self.assertRaisesRegex(ValueError, "adjudicated_stage_requires_final_adjudication"):
            validate_record(record)

    def test_pending_adjudication_never_counts_as_gold(self):
        record = fixture()
        record["admission_status"] = "review_pending"
        report = audit_corpus([record])
        self.assertEqual(report["gold_records"], 0)
        self.assertEqual(report["review_pending_records"], 1)
        self.assertEqual(report["split_counts"]["train"], 0)

    def test_gold_requires_final_unanimous_adjudication(self):
        record = fixture()
        record["admission_status"] = "gold"
        with self.assertRaisesRegex(ValueError, "gold_record_requires_unanimous_adjudication"):
            validate_record(record)
        record["adjudication"] = {
            "status": "adjudicated", "adjudicator_id": "senior-1",
            "decisions": {"claim-1": "accept"},
        }
        record["witnesses"][0]["transcription_review_status"] = "verified_against_scan"
        record["witnesses"][0]["scan_uri"] = "https://example.org/scan/page-1"
        validate_record(record)
        report = audit_corpus([record])
        self.assertEqual(report["gold_records"], 1)
        self.assertEqual(report["split_counts"]["train"], 1)

    def test_gold_requires_transcription_verified_against_scan(self):
        record = fixture()
        record["admission_status"] = "gold"
        record["adjudication"] = {
            "status": "adjudicated", "adjudicator_id": "senior-1",
            "decisions": {"claim-1": "accept"},
        }
        with self.assertRaisesRegex(ValueError, "gold_record_requires_scan_verified_transcription"):
            validate_record(record)

    def test_invalid_scan_uri_is_rejected(self):
        record = fixture()
        record["witnesses"][0]["scan_uri"] = "javascript:alert(1)"
        with self.assertRaisesRegex(ValueError, "invalid_witness_scan_uri"):
            validate_record(record)

    def test_invalid_transcription_review_state_is_rejected(self):
        record = fixture()
        record["witnesses"][0]["transcription_review_status"] = "looks_ok"
        with self.assertRaisesRegex(ValueError, "invalid_transcription_review_status"):
            validate_record(record)

    def test_secondary_or_collation_record_cannot_be_gold(self):
        record = fixture(policy="variant_collation")
        record["admission_status"] = "gold"
        record["adjudication"] = {
            "status": "adjudicated", "adjudicator_id": "senior-1",
            "decisions": {"claim-1": "accept"},
        }
        with self.assertRaisesRegex(ValueError, "gold_record_requires_core_primary_evidence"):
            validate_record(record)

    def test_audit_reports_source_policy_and_split_counts(self):
        records = [fixture()]
        report = audit_corpus(records)
        self.assertEqual(report["records"], 1)
        self.assertEqual(report["work_period_counts_all_records"]["pre_qing"], 1)
        self.assertEqual(report["gold_records"], 0)
        self.assertEqual(report["review_pending_records"], 1)
        self.assertEqual(report["split_counts"]["train"], 0)
        self.assertEqual(report["all_record_split_counts"]["train"], 1)
        self.assertTrue(report["gold_admission_requires_adjudication"])
        self.assertTrue(report["all_evidence_spans_exact"])


if __name__ == "__main__":
    unittest.main()
