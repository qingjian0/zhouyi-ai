import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MoziFeigongArgumentGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads(
            (ROOT / "data" / "mozi_feigong_argument_graph.v0.1.json").read_text(encoding="utf-8")
        )

    def test_two_distinct_chains_share_one_normative_basis(self):
        chains = {item["chain_id"]: item for item in self.graph["chains"]}
        self.assertEqual(set(chains), {"A_HARM_PROGRESSION", "B_QUANTITY_SCALING"})
        self.assertEqual(
            self.graph["cross_chain_relation"]["relation"],
            "shared_normative_basis_but_distinct_inference_structure",
        )
        self.assertNotEqual(chains["A_HARM_PROGRESSION"]["chain_kind"],
                            chains["B_QUANTITY_SCALING"]["chain_kind"])

    def test_harm_progression_and_quantity_scaling_are_not_collapsed(self):
        chains = {item["chain_id"]: item for item in self.graph["chains"]}
        self.assertEqual(chains["A_HARM_PROGRESSION"]["sequence"][0]["action"], "窃桃李")
        self.assertEqual(chains["B_QUANTITY_SCALING"]["sequence"][0]["quantity"], 1)
        self.assertEqual(chains["B_QUANTITY_SCALING"]["sequence"][2]["quantity"], 100)

    def test_each_chain_declares_scope_and_failure_conditions(self):
        for chain in self.graph["chains"]:
            self.assertTrue(chain["scope_conditions"])
            self.assertTrue(chain["failure_conditions"])
            self.assertTrue(chain["comparison_dimensions"])

    def test_adversarial_cases_include_contextual_exceptions(self):
        scenarios = " ".join(item["scenario"] for item in self.graph["adversarial_cases"])
        self.assertIn("防御", scenarios)
        self.assertIn("责任", scenarios)

    def test_evidence_status_is_not_promoted(self):
        self.assertEqual(self.graph["source_ref"]["evidence_status"], "digital_transcription_candidate")
        self.assertEqual(self.graph["source_ref"]["review_status"], "unreviewed")


if __name__ == "__main__":
    unittest.main()
