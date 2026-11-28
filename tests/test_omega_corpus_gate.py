"""Fail-closed tests for reviewed classical-xiang corpus export."""
import unittest

from prototype.omega_corpus_gate import assess_record, export_corpus


def eligible_record():
    return {
        "record_id": "test-001",
        "record_version": "1",
        "work": {"title": "Test Classic"},
        "period": "pre_qin",
        "source_type": "classical_text",
        "witness": {"witness_id": "w1", "url": "https://example.org/w1"},
        "locator": {"chapter": "1", "section_or_line": "1"},
        "text": "方以类聚，物以群分。",
        "text_status": "verified_against_witness",
        "claims": [{"claim_id": "c1", "review_status": "reviewed"}],
        "review_status": "reviewed",
        "rights": {"text_license": "public_domain", "database_license": "CC0-1.0"},
    }


class OmegaCorpusGateTests(unittest.TestCase):
    def test_rejects_unreviewed_seed_records(self):
        record = eligible_record()
        record["review_status"] = "candidate"
        record["claims"][0]["review_status"] = "unreviewed"
        reasons = assess_record(record)
        self.assertIn("record_not_reviewed", reasons)
        self.assertIn("claims_not_all_reviewed", reasons)

    def test_rejects_unverified_text_and_uncleared_database_license(self):
        record = eligible_record()
        record["text_status"] = "quotation_fragment"
        record["rights"]["database_license"] = "未核验"
        reasons = assess_record(record)
        self.assertIn("text_not_verified_against_witness", reasons)
        self.assertIn("database_license_not_allowlisted", reasons)

    def test_exports_eligible_text_with_provenance_manifest(self):
        corpus, manifest = export_corpus([eligible_record()])
        self.assertEqual(corpus, "方以类聚，物以群分。")
        self.assertEqual(manifest["accepted_count"], 1)
        self.assertEqual(manifest["accepted"][0]["witness_id"], "w1")
        self.assertEqual(manifest["accepted"][0]["claim_ids"], ["c1"])

    def test_rejects_duplicate_normalized_text(self):
        first = eligible_record()
        second = eligible_record()
        second["record_id"] = "test-002"
        second["text"] = " 方以类聚，物以群分。 "
        _, manifest = export_corpus([first, second])
        self.assertEqual(manifest["accepted_count"], 1)
        self.assertIn("duplicate_text", manifest["rejected"][0]["reasons"])


if __name__ == "__main__":
    unittest.main()
