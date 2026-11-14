import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ClassicalYixiangCatalogTests(unittest.TestCase):
    def test_catalog_is_valid_json_with_unique_canonical_ids(self):
        catalog = json.loads(
            (ROOT / "data" / "classical_yixiang_source_catalog.json").read_text(encoding="utf-8")
        )
        works = catalog["works"]
        ids = [work["work_id"] for work in works]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(re.fullmatch(r"[a-z0-9_]+", item) for item in ids))

    def test_schema_is_valid_json_and_documents_canonical_ids(self):
        schema = json.loads(
            (ROOT / "schemas" / "classical-yixiang-source-catalog.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(
            schema["properties"]["works"]["items"]["properties"]["work_id"]["pattern"],
            "^[a-z0-9_]+$",
        )

    def test_catalog_preserves_pre_qing_primary_policy(self):
        catalog = json.loads(
            (ROOT / "data" / "classical_yixiang_source_catalog.json").read_text(encoding="utf-8")
        )
        self.assertEqual(catalog["policy"]["primary_period"], "pre-Qing")
        self.assertTrue(catalog["policy"]["do_not_back_project_later_interpretations"])
        self.assertTrue(catalog["policy"]["textual_claims_require_exact_edition_and_locator"])

    def test_catalog_covers_classical_and_excavated_source_families(self):
        catalog = json.loads(
            (ROOT / "data" / "classical_yixiang_source_catalog.json").read_text(encoding="utf-8")
        )
        self.assertGreaterEqual(len(catalog["works"]), 140)
        ids = {work["work_id"] for work in catalog["works"]}
        self.assertTrue({"jiagu_jinwen", "jiandu_boshu", "dunhuang_tushu", "chuci", "wenxin_diaolong"}.issubset(ids))

    def test_candidate_sources_are_not_misrepresented_as_ingested(self):
        catalog = json.loads(
            (ROOT / "data" / "classical_yixiang_source_catalog.json").read_text(encoding="utf-8")
        )
        for work in catalog["works"]:
            if work["edition"] is None:
                self.assertEqual(work["ingestion_status"], "candidate_not_ingested")


if __name__ == "__main__":
    unittest.main()
