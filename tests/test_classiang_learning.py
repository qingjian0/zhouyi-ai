import json
import tempfile
import unittest
from pathlib import Path

from prototype.classiang_learning import (
    NONE_LABEL, TextAnnotation, TextRecord, TrainableTextEncoder,
    append_reviewed_feedback, evaluate, train_and_evaluate,
)
from prototype.classiang_multimodal import (
    ImageRegionClaim, observation_from_image_regions,
)


def records():
    rows = []
    for index in range(6):
        text = f"设备{index} transfers water through pipe"
        phrase = "transfers water"
        start = text.index(phrase)
        rows.append(TextRecord(
            observation_id=f"obs-{index}", subject_id=f"subject-{index}",
            domain="mechanical" if index < 3 else "biology",
            source_id=f"source-{index}", text=text,
            annotations=(TextAnnotation(
                start, start + len(phrase), "function", "transfers-water",
                ("recognition",),
            ),),
            group_id=f"group-{index}",
            negative_annotations=((text.index("pipe"), text.index("pipe") + len("pipe")),),
        ))
    return tuple(rows)


class ClassiangLearningTests(unittest.TestCase):
    def test_train_predict_and_preserve_exact_evidence_span(self):
        model = TrainableTextEncoder().fit(records()[:4])
        row = records()[4]
        observation = model.predict(
            observation_id=row.observation_id, subject_id=row.subject_id,
            domain=row.domain, source_id=row.source_id, text=row.text,
            threshold=0.2,
        )
        self.assertTrue(observation.features)
        feature = observation.features[0]
        self.assertEqual(feature.atom.value, "transfers-water")
        self.assertIn(f"chars:{row.text.index('transfers water')}-"
                      f"{row.text.index('transfers water') + len('transfers water')}",
                      feature.evidence_refs[0])
        self.assertIn(("recognition", 1.0), feature.purpose_scores)

    def test_task_scores_are_prevalence_not_normalized_across_tasks(self):
        rows = []
        for index, row in enumerate(records()[:4]):
            annotation = row.annotations[0]
            rows.append(TextRecord(
                row.observation_id, row.subject_id, row.domain, row.source_id,
                row.text, (TextAnnotation(
                    annotation.start_char, annotation.end_char,
                    annotation.dimension, annotation.value,
                    ("recognition", "diagnosis"),
                ),), row.context, row.group_id, row.negative_annotations,
            ))
        model = TrainableTextEncoder().fit(tuple(rows))
        query = records()[4]
        observation = model.predict(
            observation_id=query.observation_id, subject_id=query.subject_id,
            domain=query.domain, source_id=query.source_id, text=query.text,
            threshold=0.2,
        )
        self.assertEqual(
            observation.features[0].purpose_scores,
            (("diagnosis", 1.0), ("recognition", 1.0)),
        )

    def test_reviewed_negative_spans_are_validated_and_kept_separate(self):
        row = records()[0]
        # Keep this fixture independent of the shared corpus wording: the
        # reviewed negative span must actually exist in the source text.
        text = row.text.replace("through pipe", "through narrow pipe")
        negative_text = "narrow pipe"
        start = text.index(negative_text)
        reviewed = TextRecord(
            row.observation_id, row.subject_id, row.domain, row.source_id,
            text, row.annotations, row.context, row.group_id,
            ((start, start + len(negative_text)),),
        )
        model = TrainableTextEncoder().fit((reviewed,))
        self.assertGreater(model.training_records, 0)
        with self.assertRaisesRegex(ValueError, "overlaps a positive"):
            invalid = TextRecord(
                row.observation_id, row.subject_id, row.domain, row.source_id,
                row.text, row.annotations, row.context, row.group_id,
                ((row.annotations[0].start_char, row.annotations[0].end_char),),
            )
            TrainableTextEncoder().fit((invalid,))

    def test_only_explicitly_reviewed_spans_enter_the_negative_class(self):
        model = TrainableTextEncoder().fit(records()[:1])
        self.assertEqual(model.class_docs[NONE_LABEL], 1)

    def test_unannotated_spans_are_not_used_as_negative_training_examples(self):
        rows = tuple(
            TextRecord(
                row.observation_id, row.subject_id, row.domain, row.source_id,
                row.text, row.annotations, row.context, row.group_id,
            )
            for row in records()[:4]
        )
        with self.assertRaisesRegex(ValueError, "explicitly reviewed negative_annotations"):
            TrainableTextEncoder().fit(rows)

    def test_unreviewed_only_records_are_skipped_not_used_as_negative(self):
        model = TrainableTextEncoder().fit(records()[:4] + (
            TextRecord(
                "unknown-only", "unknown-subject", "test", "unknown-source",
                "unreviewed material", (),
            ),
        ))
        self.assertEqual(model.training_records, 4)
        report = evaluate(model, (
            TextRecord(
                "unknown-eval", "unknown-subject", "test", "unknown-source",
                "unreviewed material", (),
            ),
        ))
        self.assertEqual(report["evaluated_records"], 0)
        self.assertEqual(report["unreviewed_records_skipped"], 1)
        self.assertEqual(report["false_positive"], 0)

    def test_training_rejects_spans_outside_token_boundaries(self):
        row = records()[0]
        text = "xtransfers water"
        invalid = TextRecord(
            row.observation_id, row.subject_id, row.domain, row.source_id,
            text,
            (TextAnnotation(
                1, len(text), row.annotations[0].dimension,
                row.annotations[0].value, row.annotations[0].purposes,
            ),), row.context, row.group_id,
        )
        with self.assertRaisesRegex(ValueError, "not representable"):
            TrainableTextEncoder().fit((invalid,))

    def test_group_disjoint_training_and_validation(self):
        model, report = train_and_evaluate(records(), seed=3)
        self.assertTrue(report["group_disjoint"])
        self.assertFalse(set(report["train_groups"]) & set(report["validation_groups"]))
        self.assertEqual(report["validation"]["records"], 1)
        self.assertGreaterEqual(report["validation"]["f1"], 0.0)
        self.assertIsNotNone(model)

    def test_checkpoint_digest_round_trip_and_tamper_detection(self):
        model = TrainableTextEncoder().fit(records()[:4])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            digest = model.save(path)
            restored = TrainableTextEncoder.load(path)
            self.assertEqual(restored.to_dict(), model.to_dict())
            self.assertEqual(len(digest), 64)
            envelope = json.loads(path.read_text(encoding="utf-8"))
            envelope["model"]["training_records"] += 1
            path.write_text(json.dumps(envelope), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                TrainableTextEncoder.load(path)

    def test_rejects_leaky_single_group_split(self):
        rows = tuple(
            TextRecord(
                row.observation_id, row.subject_id, row.domain, row.source_id,
                row.text, row.annotations, row.context, "same-group",
            ) for row in records()
        )
        with self.assertRaisesRegex(ValueError, "independent groups"):
            train_and_evaluate(rows)

    def test_reviewed_feedback_is_append_only_and_deduplicated(self):
        event = {
            "event_id": "fb-1", "reviewer_id": "reviewer-a",
            "decision": "correct", "record": {"source_id": "source-1"},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feedback.jsonl"
            append_reviewed_feedback(path, event)
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 1)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                append_reviewed_feedback(path, event)


class ClassiangMultimodalAdapterTests(unittest.TestCase):
    def test_image_region_claims_keep_content_addressed_coordinates(self):
        observation = observation_from_image_regions(
            observation_id="image-1", subject_id="object-1", domain="visual",
            image_sha256="a" * 64, provider="external-vision",
            provider_version="1.2",
            claims=(ImageRegionClaim(
                "region-1", (0.1, 0.2, 0.8, 0.9),
                "morphology", "elongated",
                (("recognition", 0.9),),
            ),),
        )
        self.assertEqual(observation.features[0].atom.value, "elongated")
        self.assertIn("sha256:" + "a" * 64, observation.features[0].evidence_refs[0])
        self.assertIn("xyxy:0.100000,0.200000,0.800000,0.900000",
                      observation.features[0].evidence_refs[0])

    def test_rejects_invalid_image_region(self):
        with self.assertRaisesRegex(ValueError, "positive area"):
            observation_from_image_regions(
                observation_id="image-1", subject_id="object-1", domain="visual",
                image_sha256="b" * 64, provider="external", provider_version="1",
                claims=(ImageRegionClaim(
                    "bad", (0.5, 0.5, 0.5, 0.8), "morphology", "shape",
                ),),
            )


if __name__ == "__main__":
    unittest.main()
