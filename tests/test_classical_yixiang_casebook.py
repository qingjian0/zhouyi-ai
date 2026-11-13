import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ClassicalYixiangCasebookTests(unittest.TestCase):
    def setUp(self):
        self.book = json.loads(
            (ROOT / "data" / "classical_yixiang_casebook.v0.1.json").read_text(encoding="utf-8")
        )

    def test_casebook_has_unique_ids_and_resolvable_sources(self):
        cases = self.book["cases"]
        ids = [case["case_id"] for case in cases]
        self.assertEqual(len(ids), len(set(ids)))
        source_ids = {source["source_id"] for source in self.book["sources"]}
        self.assertTrue(all(case["source_id"] in source_ids for case in cases))

    def test_initial_coverage_contains_core_pre_qin_han_texts(self):
        works = {source["work"] for source in self.book["sources"]}
        self.assertTrue({"周易·系辞下传", "墨子", "荀子", "公孙龙子", "淮南子", "论衡"}.issubset(works))
        self.assertTrue(any(source["chapter"] == "要略" for source in self.book["sources"]))
        self.assertGreaterEqual(len(self.book["cases"]), 10)

    def test_no_candidate_excerpt_is_misrepresented_as_verified(self):
        for case in self.book["cases"]:
            self.assertEqual(case["evidence_status"], "digital_transcription_candidate")
            self.assertEqual(case["review_status"], "unreviewed")
        for source in self.book["sources"]:
            self.assertTrue(source["witness_limit"])

    def test_every_case_has_an_explicit_scope_and_boundary(self):
        for case in self.book["cases"]:
            self.assertTrue(case["conclusion_scope"].strip())
            self.assertTrue(case["counterexample_or_boundary"])
            self.assertTrue(case["premises"])
            self.assertTrue(case["operation"])


if __name__ == "__main__":
    unittest.main()
