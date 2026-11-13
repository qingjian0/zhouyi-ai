import unittest

from prototype.yixiang_observation_grounding import (
    ObservationRecord, ObservationSource, PerceptualModality,
    ReferentDecision, ReferentPairEvidence, assess_referent_pair,
)


class XunziObservationGroundingTests(unittest.TestCase):
    def observation(self, observation_id, features, anchor, **overrides):
        values = dict(
            observation_id=observation_id,
            observed_features=features,
            modality=PerceptualModality.SIGHT,
            source=ObservationSource.DIRECT_SENSORY,
            context="controlled observation context",
            timepoint="t1",
            referent_anchor=anchor,
        )
        values.update(overrides)
        return ObservationRecord(**values)

    def test_same_appearance_does_not_merge_distinct_referents(self):
        pair = ReferentPairEvidence(
            first=self.observation("o1", ("red", "round"), "object-a"),
            second=self.observation("o2", ("red", "round"), "object-b"),
            separation_refs=("track:separate-objects",),
        )
        result = assess_referent_pair(pair)
        self.assertEqual(result.decision, ReferentDecision.DISTINCT_REFERENTS)
        self.assertEqual(result.appearance_relation, "same_recorded_features")
        self.assertFalse(result.identity_from_appearance_alone)

    def test_changed_appearance_can_preserve_referent_with_continuity(self):
        pair = ReferentPairEvidence(
            first=self.observation("o1", ("green", "small"), "plant-7"),
            second=self.observation("o2", ("brown", "large"), "plant-7",
                                    timepoint="t2"),
            continuity_refs=("track:continuous-growth",),
        )
        result = assess_referent_pair(pair)
        self.assertEqual(result.decision, ReferentDecision.SAME_REFERENT)
        self.assertTrue(result.transformation_detected)

    def test_appearance_alone_is_insufficient(self):
        pair = ReferentPairEvidence(
            first=self.observation("o1", ("same-shape",), ""),
            second=self.observation("o2", ("same-shape",), ""),
        )
        result = assess_referent_pair(pair)
        self.assertEqual(result.decision, ReferentDecision.ABSTAIN)
        self.assertIn("IDENTITY_REQUIRES_CONTINUITY_OR_SEPARATION_EVIDENCE",
                      result.reason_codes)

    def test_model_output_cannot_ground_identity(self):
        pair = ReferentPairEvidence(
            first=self.observation("o1", ("feature-a",), "x"),
            second=self.observation("o2", ("feature-a",), "x",
                                    source=ObservationSource.MODEL_OUTPUT),
            continuity_refs=("model:guessed-continuity",),
        )
        result = assess_referent_pair(pair)
        self.assertEqual(result.decision, ReferentDecision.ABSTAIN)
        self.assertIn("NON_PERCEPTUAL_SOURCE_CANNOT_GROUND_IDENTITY",
                      result.reason_codes)

    def test_testimony_is_recorded_but_not_direct_perceptual_grounding(self):
        pair = ReferentPairEvidence(
            first=self.observation("o1", ("feature-a",), "x",
                                   source=ObservationSource.TESTIMONY),
            second=self.observation("o2", ("feature-b",), "x"),
            continuity_refs=("report:claimed-continuity",),
        )
        result = assess_referent_pair(pair)
        self.assertEqual(result.decision, ReferentDecision.ABSTAIN)

    def test_conflicting_continuity_and_separation_evidence_abstains(self):
        pair = ReferentPairEvidence(
            first=self.observation("o1", ("a",), "x"),
            second=self.observation("o2", ("b",), "x"),
            continuity_refs=("track:same",),
            separation_refs=("track:distinct",),
        )
        result = assess_referent_pair(pair)
        self.assertEqual(result.decision, ReferentDecision.ABSTAIN)
        self.assertIn("CONTINUITY_AND_SEPARATION_EVIDENCE_CONFLICT",
                      result.reason_codes)

    def test_same_anchor_without_continuity_does_not_auto_merge(self):
        pair = ReferentPairEvidence(
            first=self.observation("o1", ("a",), "x"),
            second=self.observation("o2", ("b",), "x"),
        )
        result = assess_referent_pair(pair)
        self.assertEqual(result.decision, ReferentDecision.ABSTAIN)

    def test_invalid_modality_is_rejected(self):
        pair = ReferentPairEvidence(
            first=self.observation("o1", ("a",), "x",
                                   modality="visual"),
            second=self.observation("o2", ("a",), "x"),
        )
        with self.assertRaisesRegex(ValueError, "modality"):
            assess_referent_pair(pair)


if __name__ == "__main__":
    unittest.main()
