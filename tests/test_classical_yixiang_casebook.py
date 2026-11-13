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
        self.assertGreaterEqual(len(self.book["cases"]), 11)
        self.assertEqual(len(self.book["cases"]), 22)
        self.assertTrue({"吕氏春秋", "淮南子"}.issubset(works))
        self.assertTrue(any(source["chapter"] == "恃君览·别类" for source in self.book["sources"]))
        self.assertTrue(any(source["chapter"] == "说山训" for source in self.book["sources"]))
        self.assertTrue(any(source["chapter"] == "孟冬纪·安死" for source in self.book["sources"]))

    def test_non_aggression_case_separates_harm_progression_and_quantity_scaling(self):
        case = next(item for item in self.book["cases"] if item["case_id"] == "xy_011")
        self.assertEqual(case["source_id"], "src_feigong")
        self.assertTrue(any("第一条论证链" in premise for premise in case["premises"]))
        self.assertTrue(any("第二条论证" in premise for premise in case["premises"]))
        self.assertTrue(any("防御" in boundary for boundary in case["counterexample_or_boundary"]))
        self.assertIn("normative_argument", case["operation"])

    def test_xunzi_zhengming_case_separates_observation_naming_and_identity(self):
        case = next(item for item in self.book["cases"] if item["case_id"] == "xy_012")
        self.assertEqual(case["source_id"], "src_xunzi")
        self.assertIn("perception_grounding", case["operation"])
        self.assertIn("identity_tracking", case["operation"])
        self.assertTrue(any("天官" in premise for premise in case["premises"]))
        self.assertTrue(any("颜色和轮廓上相同" in boundary and "不同个体" in boundary for boundary in case["counterexample_or_boundary"]))
        self.assertIn("外观或名称", case["conclusion_scope"])

    def test_bielei_and_shuoshan_cases_preserve_transfer_boundaries(self):
        by_id = {case["case_id"]: case for case in self.book["cases"]}
        self.assertEqual(by_id["xy_013"]["source_id"], "src_lushi_bielei")
        self.assertTrue(any("组合" in item for item in by_id["xy_013"]["counterexample_or_boundary"]))
        self.assertEqual(by_id["xy_014"]["source_id"], "src_huainan_shuoshan")
        self.assertTrue(any("局部" in item for item in by_id["xy_014"]["counterexample_or_boundary"]))
        self.assertEqual(by_id["xy_015"]["source_id"], "src_huainan_shuoshan")
        self.assertTrue(any("顺序" in item for item in by_id["xy_015"]["counterexample_or_boundary"]))
        self.assertEqual(by_id["xy_016"]["source_id"], "src_huainan_shuoshan")
        self.assertIn("现代医学", by_id["xy_016"]["conclusion_scope"])

    def test_lushi_action_outcome_and_delayed_effect_cases(self):
        by_id = {case["case_id"]: case for case in self.book["cases"]}
        neighbor = by_id["xy_017"]
        self.assertEqual(neighbor["source_id"], "src_lushi_ansi")
        self.assertIn("causal_critique", neighbor["operation"])
        self.assertTrue(any("意图" in item for item in neighbor["counterexample_or_boundary"]))
        delayed = by_id["xy_018"]
        self.assertEqual(delayed["source_id"], "src_lushi_bielei")
        self.assertTrue(any("长期稳定" in item for item in delayed["counterexample_or_boundary"]))
        self.assertTrue(any("延迟结果" in item for item in delayed["counterexample_or_boundary"]))

    def test_yingtong_case_separates_symbolic_correspondence_from_causality(self):
        case = next(item for item in self.book["cases"] if item["case_id"] == "xy_019")
        self.assertEqual(case["source_id"], "src_lushi_yingtong")
        self.assertIn("correspondence", case["operation"])
        self.assertIn("现代经验意义", case["conclusion_scope"])
        yingtong_source = next(source for source in self.book["sources"] if source["source_id"] == "src_lushi_yingtong")
        self.assertIn("不作为现代自然因果事实", yingtong_source["witness_limit"])
        self.assertTrue(any("后期墨家" in item for item in case["alternative_readings"]))

    def test_mojing_jingxia_preserves_taxonomic_transfer_difficulty(self):
        case = next(item for item in self.book["cases"] if item["case_id"] == "xy_022")
        self.assertEqual(case["source_id"], "src_mojing_jingxia")
        self.assertIn("推类之难", case["excerpt"])
        self.assertIn("classification", case["operation"])
        self.assertTrue(any("总名" in item or "种别名" in item
                            for item in case["alternative_readings"]))
        self.assertEqual(case["evidence_status"], "digital_transcription_candidate")
        self.assertEqual(case["review_status"], "unreviewed")

    def test_mozi_xiaoqu_separates_same_result_from_same_reason(self):
        case = next(item for item in self.book["cases"] if item["case_id"] == "xy_021")
        self.assertEqual(case["source_id"], "src_mozi")
        self.assertIn("其所以然不必同", case["excerpt"])
        self.assertTrue(any("原因相同" in item for item in case["premises"]))
        self.assertTrue(any("同果异因" in item for item in case["counterexample_or_boundary"]))

    def test_chunqiu_fanlu_case_does_not_transfer_physical_resonance_as_proof_of_political_sense(self):
        case = next(item for item in self.book["cases"] if item["case_id"] == "xy_020")
        self.assertEqual(case["source_id"], "src_chunqiu_fanlu")
        self.assertIn("causal_critique", case["operation"])
        self.assertTrue(any("琴瑟共鸣" in item and "祥瑞" in item for item in case["counterexample_or_boundary"]))
        fanlu_source = next(source for source in self.book["sources"] if source["source_id"] == "src_chunqiu_fanlu")
        self.assertIn("未必全出董仲舒", fanlu_source["witness_limit"])
        self.assertIn("楼钥", fanlu_source["witness_limit"])
        self.assertIn("篇章形成", self.book["sources"][-1]["witness_limit"])

    def test_all_case_operations_are_allowed_by_schema(self):
        schema = json.loads(
            (ROOT / "schemas" / "classical-yixiang-casebook.schema.json").read_text(encoding="utf-8")
        )
        allowed = set(schema["properties"]["cases"]["items"]["properties"]["operation"]["items"]["enum"])
        for case in self.book["cases"]:
            self.assertTrue(set(case["operation"]).issubset(allowed), case["case_id"])

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
