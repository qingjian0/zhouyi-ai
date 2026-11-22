import unittest

from prototype.classiang_engine import FeatureAtom, select_aspects
from prototype.classiang_text_adapter import (
    TextFeatureAnnotation, observation_from_text_spans,
)


class ClassiangTextAdapterTests(unittest.TestCase):
    def setUp(self):
        self.text = "泵将液体沿管道输送。"
        self.annotations = (
            TextFeatureAnnotation(
                "f-function", 0, 1, "function", "transports-fluid",
                (("fluid-transfer", 0.95),),
            ),
            TextFeatureAnnotation(
                "f-process", 1, 3, "process", "directed-flow",
                (("fluid-transfer", 0.9),),
            ),
        )

    def build(self, **overrides):
        values = dict(
            observation_id="obs-text-1",
            subject_id="pump-1",
            domain="mechanics",
            source_id="manual:chapter-1",
            text=self.text,
            annotations=self.annotations,
            context=("chapter-1@v1",),
        )
        values.update(overrides)
        return observation_from_text_spans(**values)

    def test_preserves_unicode_source_offsets_and_evidence(self):
        observation = self.build()
        self.assertEqual(len(observation.features), 2)
        self.assertTrue(all(
            ref.startswith("text:manual:chapter-1:chars:")
            for ref in observation.evidence_refs
        ))
        selected = select_aspects(
            observation, purpose="fluid-transfer", min_relevance=0.8,
        )
        self.assertEqual(
            set(selected.selected),
            {FeatureAtom("function", "transports-fluid"),
             FeatureAtom("process", "directed-flow")},
        )

    def test_rejects_out_of_range_span(self):
        bad = (
            TextFeatureAnnotation(
                "bad", 0, len(self.text) + 1, "function", "invalid",
                (("fluid-transfer", 0.9),),
            ),
        )
        with self.assertRaisesRegex(ValueError, "exceeds source text"):
            self.build(annotations=bad)

    def test_rejects_duplicate_feature_ids(self):
        duplicate = (self.annotations[0], self.annotations[0])
        with self.assertRaisesRegex(ValueError, "feature IDs must be unique"):
            self.build(annotations=duplicate)

    def test_rejects_unknown_dimension_through_observation_contract(self):
        bad = (
            TextFeatureAnnotation(
                "bad-dimension", 0, 1, "unknown", "value",
                (("fluid-transfer", 0.9),),
            ),
        )
        with self.assertRaisesRegex(ValueError, "unknown feature dimension"):
            self.build(annotations=bad)


if __name__ == "__main__":
    unittest.main()
