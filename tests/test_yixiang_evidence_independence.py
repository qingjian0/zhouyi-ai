import unittest

from prototype.yixiang_evidence_independence import (
    LineageDecision,
    TextWitness,
    WitnessKind,
    assess_witness_lineages,
)


class EvidenceLineageTests(unittest.TestCase):
    def witness(self, ref, witness_id, root, kind=WitnessKind.DIGITAL_TRANSCRIPTION):
        return TextWitness(
            witness_ref=ref,
            work_id="mozi-xiaoqu",
            witness_id=witness_id,
            lineage_root_id=root,
            kind=kind,
        )

    def test_mirrored_platforms_from_same_edition_count_once(self):
        result = assess_witness_lineages(
            "mozi-xiaoqu",
            (
                self.witness("site-a", "w1", "edition-x"),
                self.witness("site-b", "w2", "edition-x"),
            ),
        )
        self.assertEqual(result.independent_lineage_count, 1)
        self.assertEqual(result.decision, LineageDecision.ABSTAIN)
        self.assertIn("INSUFFICIENT_DISTINCT_DECLARED_LINEAGES", result.reason_codes)

    def test_distinct_declared_roots_meet_threshold(self):
        result = assess_witness_lineages(
            "mozi-xiaoqu",
            (
                self.witness("witness-a", "w1", "root-a", WitnessKind.MANUSCRIPT),
                self.witness("witness-b", "w2", "root-b", WitnessKind.PRINTED_EDITION),
            ),
        )
        self.assertEqual(result.independent_lineage_count, 2)
        self.assertEqual(result.decision, LineageDecision.SUFFICIENT_DECLARED_LINEAGES)

    def test_model_generated_material_never_counts(self):
        result = assess_witness_lineages(
            "mozi-xiaoqu",
            (
                self.witness("witness-a", "w1", "root-a", WitnessKind.MANUSCRIPT),
                self.witness("model", "w2", "root-b", WitnessKind.MODEL_GENERATED),
            ),
        )
        self.assertEqual(result.independent_lineage_count, 1)
        self.assertEqual(result.decision, LineageDecision.ABSTAIN)
        self.assertEqual(result.ignored_refs, ("model",))

    def test_wrong_work_is_rejected(self):
        witness = TextWitness("ref", "xunzi-zhengming", "w1", "root", WitnessKind.MANUSCRIPT)
        with self.assertRaisesRegex(ValueError, "requested work"):
            assess_witness_lineages("mozi-xiaoqu", (witness,))

    def test_duplicate_references_are_rejected(self):
        item = self.witness("same", "w1", "root-a")
        duplicate = self.witness("same", "w2", "root-b")
        with self.assertRaisesRegex(ValueError, "witness_ref"):
            assess_witness_lineages("mozi-xiaoqu", (item, duplicate))

    def test_invalid_threshold_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            assess_witness_lineages("mozi-xiaoqu", (), True)


if __name__ == "__main__":
    unittest.main()
