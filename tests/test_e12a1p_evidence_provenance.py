import unittest

from prototype.e12a1_typed_predicate_induction import Example, FeatureSpec
from prototype.e12a1p_evidence_provenance import (
    EvidenceRecord, GENERATOR_VERSION, infer_with_provenance, predicate_id,
)


def record(eid, split, x, label, schema_version="schema/1"):
    return EvidenceRecord(eid, split, Example((("x", x),), label), schema_version)


class E12A1ProvenanceTests(unittest.TestCase):
    def test_lineage_is_explicit_and_split_separated(self):
        result = infer_with_provenance(
            (FeatureSpec("x", "numeric"),),
            tuple(record(f"tr{i}", "train", x, int(x % 2 == 0)) for i, x in enumerate(range(4))),
            (record("g4", "gate", 4, 1), record("g5", "gate", 5, 0)),
        )
        self.assertEqual(result["status"], "IDENTIFIABLE")
        self.assertEqual(result["evidence_lineage"]["train_evidence_ids"], ["tr0", "tr1", "tr2", "tr3"])
        self.assertEqual(result["evidence_lineage"]["gate_evidence_ids"], ["g4", "g5"])
        self.assertEqual(result["selected_candidate_id"], next(
            c["candidate_id"] for c in result["candidates"]
            if c["predicate"]["operator"] == "PARITY"
        ))

    def test_candidate_ids_are_stable_and_include_generator_version(self):
        from prototype.e12a1_typed_predicate_induction import Predicate
        p = Predicate("x", "numeric", "GE", 1.5)
        self.assertEqual(predicate_id(p), predicate_id(p))
        self.assertIn(GENERATOR_VERSION, predicate_id(p))

    def test_candidate_support_points_to_train_evidence(self):
        result = infer_with_provenance(
            (FeatureSpec("x", "numeric"),),
            (record("lo", "train", 1, 0), record("hi", "train", 3, 1)),
            (record("g", "gate", 4, 1),),
        )
        threshold_rows = [c for c in result["candidates"]
                          if c["predicate"]["operator"] == "GE"
                          and c["predicate"]["threshold"] == 2.0]
        self.assertEqual(len(threshold_rows), 1)
        self.assertEqual(threshold_rows[0]["support_evidence_ids"], ["lo", "hi"])

    def test_duplicate_evidence_ids_rejected(self):
        with self.assertRaises(ValueError):
            infer_with_provenance(
                (FeatureSpec("x", "numeric"),),
                (record("same", "train", 1, 0),),
                (record("same", "gate", 2, 1),),
            )

    def test_wrong_split_rejected(self):
        with self.assertRaises(ValueError):
            infer_with_provenance(
                (FeatureSpec("x", "numeric"),),
                (record("tr", "gate", 1, 0),),
                (record("g", "gate", 2, 1),),
            )

    def test_schema_version_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            infer_with_provenance(
                (FeatureSpec("x", "numeric"),),
                (record("tr", "train", 1, 0, "schema/2"),),
                (record("g", "gate", 2, 1),),
            )

    def test_budget_exhaustion_keeps_provenance_but_never_selects(self):
        result = infer_with_provenance(
            (FeatureSpec("x", "numeric"),),
            (record("a", "train", 0, 0), record("b", "train", 1, 1)),
            (record("c", "gate", 2, 0),),
            candidate_budget=1,
        )
        self.assertEqual(result["status"], "BUDGET_EXHAUSTED")
        self.assertIsNone(result["selected_candidate_id"])
        self.assertEqual(result["evaluated_count"], 1)


if __name__ == "__main__":
    unittest.main()
