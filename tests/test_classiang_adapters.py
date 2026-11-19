import unittest

from prototype.classiang_adapters import adapt_formation_trace
from prototype.yixiang_formation import (
    CategoryAssignment, FeatureSelection, FormationTrace, Observation,
)


def trace(*, reviewed=True):
    observation = Observation(
        observation_id="obs-1", subject_id="subject-1",
        context_id="context-a", context_version=2,
        description="Observed load-bearing structure", modality="text",
        recording_method="human annotation", interpretation_note="directly recorded",
        evidence_refs=("source:1",), observer_id="annotator-1",
    )
    feature = FeatureSelection(
        feature_id="feature-1", subject_id="subject-1",
        label="load-bearing", operational_description="transfers a vertical load",
        observation_refs=("obs-1",), evidence_refs=("source:1",),
        selection_rationale="directly stated in the observation",
        purpose="functional recognition", excluded_alternatives=("visual similarity",),
        reviewed=reviewed,
    )
    assignment = CategoryAssignment(
        assignment_id="assignment-1", subject_id="subject-1",
        category_id="category-1", criterion="shares load-transfer function",
        feature_refs=("feature-1",), evidence_refs=("source:1",),
        counterexample_refs=(), counterexamples_resolved=True, reviewed=reviewed,
    )
    return FormationTrace("trace-1", (observation,), (feature,), (assignment,))


class ClassiangAdapterTests(unittest.TestCase):
    def test_adapts_reviewed_trace_and_preserves_provenance(self):
        result = adapt_formation_trace(
            trace(), subject_id="subject-1", domain="mechanics",
            dimensions={"feature-1": "function"},
            purpose_scores={"feature-1": (("recognition", 0.9),)},
        )
        self.assertEqual(result.observation_id, "formation:trace-1:subject-1")
        self.assertEqual(result.evidence_refs, ("source:1",))
        self.assertEqual(result.features[0].evidence_refs, ("source:1",))
        self.assertEqual(result.features[0].atom.dimension, "function")
        self.assertEqual(result.context, ("context-a@2",))

    def test_rejects_unreviewed_trace(self):
        with self.assertRaisesRegex(ValueError, "not admission-ready"):
            adapt_formation_trace(
                trace(reviewed=False), subject_id="subject-1", domain="mechanics",
                dimensions={"feature-1": "function"},
                purpose_scores={"feature-1": (("recognition", 0.9),)},
            )

    def test_requires_exact_dimension_and_score_coverage(self):
        with self.assertRaisesRegex(ValueError, "exactly"):
            adapt_formation_trace(
                trace(), subject_id="subject-1", domain="mechanics",
                dimensions={}, purpose_scores={"feature-1": (("recognition", 0.9),)},
            )

    def test_rejects_unknown_dimension(self):
        with self.assertRaisesRegex(ValueError, "unknown feature dimension"):
            adapt_formation_trace(
                trace(), subject_id="subject-1", domain="mechanics",
                dimensions={"feature-1": "unknown"},
                purpose_scores={"feature-1": (("recognition", 0.9),)},
            )

    def test_rejects_subject_without_selected_features(self):
        with self.assertRaisesRegex(ValueError, "no selected features"):
            adapt_formation_trace(
                trace(), subject_id="other", domain="mechanics",
                dimensions={"feature-1": "function"},
                purpose_scores={"feature-1": (("recognition", 0.9),)},
            )


if __name__ == "__main__":
    unittest.main()
