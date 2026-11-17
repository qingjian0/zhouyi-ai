import unittest
from prototype.yixiang_situated import (
    SituatedRelation, YixiangSituation, compare_situations,
)


def situation(sid, entities, position="middle", stage="growth", climate="mild"):
    return YixiangSituation(
        sid, "illustrative", 1, position, stage,
        {entities[0]: "active", entities[1]: "resource", entities[2]: "receiver"},
        (SituatedRelation("transfer", (
            ("agent", entities[0]), ("source", entities[1]), ("recipient", entities[2])
        )),),
        {"climate": climate, "season": "spring"},
        (f"evidence:{sid}",),
    )


class SituatedYixiangTests(unittest.TestCase):
    def setUp(self):
        self.source = situation("s", ("a", "b", "c"))
        self.target = situation("t", ("x", "y", "z"))

    def compare(self, **kwargs):
        return compare_situations(
            self.source, self.target, entity_mapping={"a": "x", "b": "y", "c": "z"},
            required_context=("climate", "season"), **kwargs
        )

    def test_accepts_joint_state_relation_and_context_match(self):
        result = self.compare()
        self.assertTrue(result.accepted)
        self.assertEqual(result.state_precision, 1.0)
        self.assertEqual(result.relation_precision, 1.0)

    def test_rejects_role_swap(self):
        swapped = YixiangSituation(
            "t", "illustrative", 1, "middle", "growth",
            self.target.state,
            (SituatedRelation("transfer", (
                ("agent", "x"), ("source", "z"), ("recipient", "y")
            )),),
            self.target.context, self.target.evidence_refs,
        )
        result = compare_situations(
            self.source, swapped, entity_mapping={"a": "x", "b": "y", "c": "z"},
            required_context=("climate", "season"),
        )
        self.assertFalse(result.accepted)
        self.assertIn("ROLE_RELATIONS_NOT_PRESERVED", result.reason_codes)

    def test_context_mismatch_is_not_hidden_by_state_similarity(self):
        target = situation("t", ("x", "y", "z"), climate="severe")
        result = compare_situations(
            self.source, target, entity_mapping={"a": "x", "b": "y", "c": "z"},
            required_context=("climate",),
        )
        self.assertFalse(result.accepted)
        self.assertIn("CONTEXT_CONDITION_MISMATCH", result.reason_codes)

    def test_position_and_stage_are_separate_gates(self):
        target = situation("t", ("x", "y", "z"), position="upper", stage="decline")
        result = compare_situations(
            self.source, target, entity_mapping={"a": "x", "b": "y", "c": "z"},
            required_context=("climate",), require_same_position=True,
            require_same_stage=True,
        )
        self.assertIn("POSITION_MISMATCH", result.reason_codes)
        self.assertIn("STAGE_MISMATCH", result.reason_codes)

    def test_duplicate_relations_are_not_collapsed(self):
        target = YixiangSituation(
            "t", "illustrative", 1, "middle", "growth", self.target.state,
            self.target.relations + self.target.relations,
            self.target.context, self.target.evidence_refs,
        )
        result = compare_situations(
            self.source, target, entity_mapping={"a": "x", "b": "y", "c": "z"},
            required_context=("climate",),
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.relation_precision, 0.5)
        self.assertIn("ROLE_RELATIONS_NOT_PRESERVED", result.reason_codes)

    def test_missing_evidence_rejected(self):
        target = situation("t", ("x", "y", "z"))
        target = YixiangSituation(
            target.situation_id, target.domain, target.step, target.position,
            target.stage, target.state, target.relations, target.context, (),
        )
        result = compare_situations(
            self.source, target, entity_mapping={"a": "x", "b": "y", "c": "z"},
            required_context=("climate",),
        )
        self.assertFalse(result.accepted)
        self.assertIn("MISSING_EVIDENCE", result.reason_codes)


if __name__ == "__main__":
    unittest.main()
