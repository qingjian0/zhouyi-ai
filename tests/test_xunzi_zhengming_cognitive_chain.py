import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class XunziZhengmingCognitiveChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads(
            (ROOT / "data" / "xunzi_zhengming_cognitive_chain.v0.1.json").read_text(encoding="utf-8")
        )

    def test_five_stages_are_ordered_and_distinct(self):
        stages = self.graph["stages"]
        self.assertEqual([item["order"] for item in stages], [1, 2, 3, 4, 5])
        self.assertEqual(len({item["stage_id"] for item in stages}), 5)
        self.assertEqual(
            [item["stage_id"] for item in stages],
            [
                "S1_SENSORY_DISCRIMINATION",
                "S2_EVIDENCE_GROUNDED_RECOGNITION",
                "S3_DIMENSIONAL_SAME_DIFFERENT",
                "S4_CLASS_AND_NAMING",
                "S5_OBJECT_CONTINUITY",
            ],
        )

    def test_each_stage_has_evidence_and_failure_modes(self):
        for stage in self.graph["stages"]:
            self.assertTrue(stage["required_evidence"])
            self.assertTrue(stage["failure_modes"])
            self.assertTrue(stage["textual_anchor"])

    def test_local_similarity_never_implies_global_identity(self):
        policy = self.graph["inference_policy"]
        self.assertTrue(policy["local_match_does_not_imply_global_identity"])
        self.assertTrue(policy["name_match_does_not_imply_referent_identity"])
        self.assertTrue(policy["appearance_change_does_not_imply_entity_change"])

    def test_adversarial_cases_cover_channel_name_and_continuity_errors(self):
        cases = {item["case_id"]: item for item in self.graph["adversarial_cases"]}
        self.assertEqual(len(cases), 5)
        self.assertIn("CHANNEL_MISMATCH", cases["XZ_AC5"]["expected"])
        self.assertIn("REFERENT_IDENTITY", cases["XZ_AC3"]["expected"])
        self.assertIn("NEW_ENTITY", cases["XZ_AC2"]["expected"])

    def test_evidence_status_remains_unreviewed(self):
        self.assertEqual(self.graph["source_ref"]["evidence_status"], "digital_transcription_candidate")
        self.assertEqual(self.graph["source_ref"]["review_status"], "unreviewed")

    def test_transfer_gates_are_explicit(self):
        self.assertGreaterEqual(len(self.graph["transfer_gates"]), 8)
        self.assertIn("counterexample_search", self.graph["transfer_gates"])
        self.assertIn("conclusion_scope", self.graph["transfer_gates"])


if __name__ == "__main__":
    unittest.main()
