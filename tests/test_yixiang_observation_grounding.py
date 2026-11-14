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
            spatial_location="location-a",
            feature_modalities=tuple(PerceptualModality.SIGHT for _ in features),
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

    def test_same_location_does_not_override_distinct_referents(self):
        pair = ReferentPairEvidence(
            first=self.observation("o1", ("shape-a",), "object-a",
                                   spatial_location="same-room"),
            second=self.observation("o2", ("shape-b",), "object-b",
                                    spatial_location="same-room"),
            separation_refs=("track:distinct-objects",),
        )
        self.assertEqual(assess_referent_pair(pair).decision,
                         ReferentDecision.DISTINCT_REFERENTS)

    def test_location_change_does_not_break_identity_with_continuity(self):
        pair = ReferentPairEvidence(
            first=self.observation("o1", ("shape-a",), "object-a",
                                   spatial_location="room-1"),
            second=self.observation("o2", ("shape-b",), "object-a",
                                    spatial_location="room-2"),
            continuity_refs=("track:continuous-movement",),
        )
        self.assertEqual(assess_referent_pair(pair).decision,
                         ReferentDecision.SAME_REFERENT)

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

    def test_reasoned_inference_is_not_direct_observation(self):
        pair = ReferentPairEvidence(
            first=self.observation("o1", ("feature-a",), "x",
                                   source=ObservationSource.REASONED_INFERENCE),
            second=self.observation("o2", ("feature-b",), "x"),
            continuity_refs=("inference:assumed-continuity",),
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

    def test_feature_modality_must_match_observation_channel(self):
        pair = ReferentPairEvidence(
            first=self.observation("o1", ("red",), "x",
                                   modality=PerceptualModality.HEARING),
            second=self.observation("o2", ("red",), "x"),
            continuity_refs=("track:1",),
        )
        with self.assertRaisesRegex(ValueError, "feature modality"):
            assess_referent_pair(pair)

    def test_mixed_modality_features_are_explicitly_tagged(self):
        first = self.observation(
            "o1", ("red surface", "bell tone"), "x",
            modality=PerceptualModality.MIXED,
            feature_modalities=(PerceptualModality.SIGHT, PerceptualModality.HEARING),
        )
        second = self.observation(
            "o2", ("red surface", "bell tone"), "x",
            modality=PerceptualModality.MIXED,
            feature_modalities=(PerceptualModality.SIGHT, PerceptualModality.HEARING),
        )
        result = assess_referent_pair(ReferentPairEvidence(
            first=first, second=second, continuity_refs=("track:1",)
        ))
        self.assertEqual(result.decision, ReferentDecision.SAME_REFERENT)

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
