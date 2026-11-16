import unittest

from prototype.yixiang_formation import (
    CategoryAssignment, FeatureSelection, FormationStatus, FormationTrace,
    Observation, assess_formation,
)


def observation(**changes):
    values = dict(observation_id="obs-1", subject_id="object-A", context_id="ctx-1",
                  context_version=1, description="A recorded visible contour", modality="vision",
                  recording_method="direct observation", interpretation_note="Possibly a tool edge",
                  evidence_refs=("source:1",), observer_id="annotator-1")
    values.update(changes)
    return Observation(**values)


def feature(**changes):
    values = dict(feature_id="feat-1", subject_id="object-A", label="contour", operational_description="outer boundary shape",
                  observation_refs=("obs-1",), evidence_refs=("source:1",),
                  selection_rationale="Contour is relevant to the stated recognition task.",
                  purpose="recognition", excluded_alternatives=("color",), reviewed=True)
    values.update(changes)
    return FeatureSelection(**values)


def assignment(**changes):
    values = dict(assignment_id="assign-1", subject_id="object-A", category_id="category-X",
                  criterion="matches the declared contour criterion", feature_refs=("feat-1",),
                  evidence_refs=("source:1",), counterexample_refs=(),
                  counterexamples_resolved=None, reviewed=True)
    values.update(changes)
    return CategoryAssignment(**values)


def trace(**changes):
    values = dict(trace_id="trace-1", observations=(observation(),),
                  selected_features=(feature(),), category_assignments=(assignment(),))
    values.update(changes)
    return FormationTrace(**values)


class FormationTests(unittest.TestCase):
    def test_complete_trace_is_only_provisional(self):
        result = assess_formation(trace())
        self.assertEqual(result.status, FormationStatus.PROVISIONAL_FORMATION)
        self.assertFalse(result.semantic_validity_established)
        self.assertFalse(result.category_truth_established)

    def test_missing_observation_is_detected(self):
        self.assertEqual(assess_formation(trace(observations=())).status, FormationStatus.MISSING_OBSERVATION)

    def test_feature_must_reference_existing_observation(self):
        result = assess_formation(trace(selected_features=(feature(observation_refs=("obs-missing",)),)))
        self.assertEqual(result.status, FormationStatus.MISSING_FEATURE_PROVENANCE)
        self.assertEqual(result.missing_observation_ids, ("feat-1",))

    def test_feature_evidence_must_come_from_its_linked_observations(self):
        other = observation(observation_id="obs-2", subject_id="object-B", evidence_refs=("source:2",))
        result = assess_formation(trace(observations=(observation(), other), selected_features=(feature(evidence_refs=("source:2",)),)))
        self.assertEqual(result.status, FormationStatus.FEATURE_NOT_GROUNDED)

    def test_feature_and_observation_subject_must_match(self):
        result = assess_formation(trace(selected_features=(feature(subject_id="object-B"),)))
        self.assertEqual(result.status, FormationStatus.DECLARATION_MISMATCH)

    def test_category_and_feature_subject_must_match(self):
        result = assess_formation(trace(category_assignments=(assignment(subject_id="object-B"),)))
        self.assertEqual(result.status, FormationStatus.DECLARATION_MISMATCH)

    def test_feature_evidence_must_be_grounded_in_observation(self):
        result = assess_formation(trace(selected_features=(feature(evidence_refs=("invented:2",)),)))
        self.assertEqual(result.status, FormationStatus.FEATURE_NOT_GROUNDED)

    def test_feature_requires_selection_rationale(self):
        result = assess_formation(trace(selected_features=(feature(selection_rationale=""),)))
        self.assertEqual(result.status, FormationStatus.MISSING_SELECTION_RATIONALE)

    def test_non_string_selection_rationale_is_rejected(self):
        with self.assertRaises(ValueError):
            assess_formation(trace(selected_features=(feature(selection_rationale=None),)))

    def test_non_string_category_criterion_is_rejected(self):
        with self.assertRaises(ValueError):
            assess_formation(trace(category_assignments=(assignment(criterion=None),)))

    def test_category_requires_explicit_criterion(self):
        result = assess_formation(trace(category_assignments=(assignment(criterion=""),)))
        self.assertEqual(result.status, FormationStatus.MISSING_CATEGORY_CRITERION)

    def test_category_requires_membership_evidence(self):
        result = assess_formation(trace(category_assignments=(assignment(evidence_refs=()),)))
        self.assertEqual(result.status, FormationStatus.MISSING_MEMBERSHIP_EVIDENCE)

    def test_unresolved_counterexample_blocks_provisional_formation(self):
        result = assess_formation(trace(category_assignments=(assignment(counterexample_refs=("ce:1",)),)))
        self.assertEqual(result.status, FormationStatus.COUNTEREXAMPLE_UNRESOLVED)

    def test_resolved_counterexample_can_be_recorded_without_erasure(self):
        result = assess_formation(trace(category_assignments=(assignment(counterexample_refs=("ce:1",), counterexamples_resolved=True),)))
        self.assertEqual(result.status, FormationStatus.PROVISIONAL_FORMATION)

    def test_unknown_feature_reference_is_reported(self):
        result = assess_formation(trace(category_assignments=(assignment(feature_refs=("feat-unknown",)),)))
        self.assertEqual(result.status, FormationStatus.DECLARATION_MISMATCH)

    def test_unreviewed_feature_prevents_pass(self):
        result = assess_formation(trace(selected_features=(feature(reviewed=False),)))
        self.assertEqual(result.status, FormationStatus.UNREVIEWED)

    def test_unreviewed_assignment_prevents_pass(self):
        result = assess_formation(trace(category_assignments=(assignment(reviewed=False),)))
        self.assertEqual(result.status, FormationStatus.UNREVIEWED)

    def test_observation_requires_recorded_modality(self):
        with self.assertRaises(ValueError):
            assess_formation(trace(observations=(observation(modality=" "),)))

    def test_observation_requires_recording_method(self):
        with self.assertRaises(ValueError):
            assess_formation(trace(observations=(observation(recording_method=" "),)))

    def test_observation_interpretation_is_separate_from_description(self):
        obs = observation(description="Boundary visible in source image", interpretation_note="May indicate a manufactured edge")
        result = assess_formation(trace(observations=(obs,)))
        self.assertEqual(result.status, FormationStatus.PROVISIONAL_FORMATION)

    def test_observation_context_version_is_validated(self):
        with self.assertRaises(ValueError):
            assess_formation(trace(observations=(observation(context_version=True),)))

    def test_duplicate_observation_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            assess_formation(trace(observations=(observation(), observation())))

    def test_duplicate_feature_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            assess_formation(trace(selected_features=(feature(), feature())))

    def test_duplicate_evidence_refs_are_rejected(self):
        with self.assertRaises(ValueError):
            assess_formation(trace(observations=(observation(evidence_refs=("source:1", "source:1")),)))

    def test_empty_feature_purpose_is_rejected(self):
        with self.assertRaises(ValueError):
            assess_formation(trace(selected_features=(feature(purpose=" "),)))

    def test_unresolved_counterexample_flag_must_be_boolean_or_unknown(self):
        with self.assertRaises(ValueError):
            assess_formation(trace(category_assignments=(assignment(counterexample_refs=("ce:1",), counterexamples_resolved="yes"),)))

    def test_no_category_assignment_does_not_invent_a_category(self):
        result = assess_formation(trace(category_assignments=()))
        self.assertEqual(result.status, FormationStatus.PROVISIONAL_FORMATION)


if __name__ == "__main__":
    unittest.main()
