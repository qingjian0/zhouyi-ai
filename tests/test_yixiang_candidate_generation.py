import unittest
from prototype.yixiang_candidate_generation import (
    CandidateDecision, EvidenceKind, Observation, ObservedFeature,
    ObservedRelation, generate_yixiang_candidates,
)


def obs(oid, domain, fk=EvidenceKind.DIRECT_OBSERVATION,
        rk=EvidenceKind.DIRECT_OBSERVATION, feature=True, relation=True):
    refs = (f"{oid}:f", f"{oid}:r")
    fs = (ObservedFeature("shape", "round", "vision", refs[0], fk),) if feature else ()
    rs = (ObservedRelation("supports", "base", "load", refs[1], rk),) if relation else ()
    return Observation(oid, domain, fs, rs, refs)


class CandidateGenerationTests(unittest.TestCase):
    def test_exact_feature_match_generates_proposal(self):
        result = generate_yixiang_candidates((obs("a", "craft"), obs("b", "botany", relation=False)))
        self.assertEqual(result[0].decision, CandidateDecision.PROPOSED)
        self.assertEqual(len(result[0].shared_features), 1)

    def test_exact_relation_match_generates_structural_candidate(self):
        result = generate_yixiang_candidates((obs("a", "a", feature=False), obs("b", "b", feature=False)))
        self.assertEqual(len(result[0].shared_relations), 1)

    def test_cross_domain_candidate_is_flagged(self):
        result = generate_yixiang_candidates((obs("a", "a"), obs("b", "b")))
        self.assertIn("CROSS_DOMAIN_CANDIDATE_REQUIRES_SEPARATE_SCOPE_REVIEW", result[0].reason_codes)

    def test_model_output_only_match_abstains(self):
        result = generate_yixiang_candidates((obs("a", "d", EvidenceKind.MODEL_OUTPUT, EvidenceKind.MODEL_OUTPUT),
                                               obs("b", "d", EvidenceKind.MODEL_OUTPUT, EvidenceKind.MODEL_OUTPUT)))
        self.assertEqual(result[0].decision, CandidateDecision.ABSTAIN)
        self.assertEqual(result[0].shared_features, ())

    def test_inference_only_match_abstains(self):
        result = generate_yixiang_candidates((obs("a", "d", EvidenceKind.INFERENCE, EvidenceKind.INFERENCE),
                                               obs("b", "d", EvidenceKind.INFERENCE, EvidenceKind.INFERENCE)))
        self.assertEqual(result[0].decision, CandidateDecision.ABSTAIN)

    def test_no_match_produces_no_candidate(self):
        a = Observation("a", "d", (ObservedFeature("shape", "round", "vision", "a:f", EvidenceKind.DIRECT_OBSERVATION),), (), ("a:f",))
        b = Observation("b", "d", (ObservedFeature("shape", "square", "vision", "b:f", EvidenceKind.DIRECT_OBSERVATION),), (), ("b:f",))
        self.assertEqual(generate_yixiang_candidates((a, b)), ())

    def test_modality_is_part_of_feature_signature(self):
        a = Observation("a", "d", (ObservedFeature("quality", "high", "vision", "a:f", EvidenceKind.DIRECT_OBSERVATION),), (), ("a:f",))
        b = Observation("b", "d", (ObservedFeature("quality", "high", "hearing", "b:f", EvidenceKind.DIRECT_OBSERVATION),), (), ("b:f",))
        self.assertEqual(generate_yixiang_candidates((a, b)), ())

    def test_unlinked_evidence_is_rejected(self):
        bad = Observation("a", "d", (ObservedFeature("shape", "round", "vision", "missing", EvidenceKind.DIRECT_OBSERVATION),), (), ("a:known",))
        with self.assertRaisesRegex(ValueError, "not linked"):
            generate_yixiang_candidates((bad,))

    def test_duplicate_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            generate_yixiang_candidates((obs("same", "d"), obs("same", "d")))

    def test_ids_are_deterministic_and_order_independent(self):
        a, b = obs("a", "d"), obs("b", "d")
        self.assertEqual(generate_yixiang_candidates((a, b)), generate_yixiang_candidates((b, a)))
        self.assertEqual(generate_yixiang_candidates((a, b))[0].candidate_id, "yc:a:b")

    def test_mixed_evidence_keeps_unsupported_match_audit_reason(self):
        a = Observation("a", "d", (
            ObservedFeature("shape", "round", "vision", "a:f1", EvidenceKind.DIRECT_OBSERVATION),
            ObservedFeature("color", "blue", "vision", "a:f2", EvidenceKind.MODEL_OUTPUT),
        ), (), ("a:f1", "a:f2"))
        b = Observation("b", "d", (
            ObservedFeature("shape", "round", "vision", "b:f1", EvidenceKind.DIRECT_OBSERVATION),
            ObservedFeature("color", "blue", "vision", "b:f2", EvidenceKind.MODEL_OUTPUT),
        ), (), ("b:f1", "b:f2"))
        result = generate_yixiang_candidates((a, b))[0]
        self.assertEqual(result.decision, CandidateDecision.PROPOSED)
        self.assertIn("SOME_FEATURE_MATCHES_LACK_ELIGIBLE_EVIDENCE", result.reason_codes)

    def test_colon_in_observation_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must not contain colon"):
            generate_yixiang_candidates((obs("bad:id", "d"), obs("b", "d")))

    def test_candidate_does_not_authorize_identity_or_causality(self):
        candidate = generate_yixiang_candidates((obs("a", "d"), obs("b", "d")))[0]
        self.assertIn("entity_identity", candidate.prohibited_shortcuts)
        self.assertIn("causal_equivalence", candidate.prohibited_shortcuts)
        self.assertIn("functional_equivalence", candidate.prohibited_shortcuts)


if __name__ == "__main__":
    unittest.main()
