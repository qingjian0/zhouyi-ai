import unittest

from prototype.yixiang_competing_hypotheses import (
    CandidateStatus, EvidenceLayer, EvidenceRecord, EvidenceStance,
    XiangCandidate, arbitrate, assess_candidate,
)


def evidence(eid, stance, layer=EvidenceLayer.PRIMARY_TEXT, dimension="relation", strength=0.9):
    return EvidenceRecord(eid, dimension, stance, strength, layer, f"source:{eid}")


class CompetingHypothesisTests(unittest.TestCase):
    def test_multiple_supported_candidates_remain_unresolved(self):
        candidates = (
            XiangCandidate("A", "mapping A", (), (), (), (), (evidence("a1", EvidenceStance.SUPPORTS),)),
            XiangCandidate("B", "mapping B", (), (), (), (), (evidence("b1", EvidenceStance.SUPPORTS),)),
        )
        result = arbitrate(candidates)
        self.assertEqual(result.viable_candidate_ids, ("A", "B"))
        self.assertTrue(result.unresolved)

    def test_missing_condition_is_not_treated_as_false(self):
        candidate = XiangCandidate(
            "A", "conditional mapping", ("spring",),
            ("spring", "moisture"), ("spring",), (), 
            (evidence("a1", EvidenceStance.SUPPORTS),),
        )
        assessment = assess_candidate(candidate)
        self.assertEqual(assessment.status, CandidateStatus.UNDERDETERMINED)
        self.assertEqual(assessment.missing_conditions, ("moisture",))

    def test_explicit_condition_violation_rejects_candidate(self):
        candidate = XiangCandidate(
            "A", "conditional mapping", ("spring",),
            ("spring",), (), ("spring",),
            (evidence("a1", EvidenceStance.SUPPORTS),),
        )
        self.assertEqual(assess_candidate(candidate).status, CandidateStatus.REJECTED)

    def test_counter_evidence_marks_candidate_contested_and_is_preserved(self):
        candidate = XiangCandidate(
            "A", "mapping", (), (), (), (),
            (
                evidence("support", EvidenceStance.SUPPORTS),
                evidence("counter", EvidenceStance.CONTRADICTS, EvidenceLayer.OBSERVATION),
            ),
        )
        assessment = assess_candidate(candidate)
        self.assertEqual(assessment.status, CandidateStatus.CONTESTED)
        self.assertEqual(assessment.profile.contradicting_records[0].evidence_id, "counter")
        self.assertEqual(assessment.profile.observation_support_count, 0)

    def test_evidence_layers_are_not_collapsed(self):
        candidate = XiangCandidate(
            "A", "mapping", (), (), (), (),
            (
                evidence("primary", EvidenceStance.SUPPORTS, EvidenceLayer.PRIMARY_TEXT),
                evidence("comment", EvidenceStance.SUPPORTS, EvidenceLayer.COMMENTARY),
                evidence("model", EvidenceStance.SUPPORTS, EvidenceLayer.MODEL_INFERENCE),
            ),
        )
        profile = assess_candidate(candidate).profile
        self.assertEqual(profile.primary_support_count, 1)
        self.assertEqual(profile.commentary_support_count, 1)
        self.assertEqual(profile.model_inference_support_count, 1)

    def test_duplicate_candidate_and_evidence_ids_are_rejected(self):
        one = XiangCandidate("A", "mapping", (), (), (), (), (evidence("e", EvidenceStance.SUPPORTS),))
        with self.assertRaises(ValueError):
            arbitrate((one, one))
        duplicate_evidence = XiangCandidate(
            "B", "mapping", (), (), (), (),
            (evidence("e", EvidenceStance.SUPPORTS), evidence("e", EvidenceStance.NEUTRAL)),
        )
        with self.assertRaises(ValueError):
            assess_candidate(duplicate_evidence)

    def test_invalid_condition_partition_is_rejected(self):
        candidate = XiangCandidate(
            "A", "mapping", (), ("x",), ("x",), ("x",),
            (evidence("e", EvidenceStance.SUPPORTS),),
        )
        with self.assertRaises(ValueError):
            assess_candidate(candidate)


if __name__ == "__main__":
    unittest.main()
