import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from prototype.classiang_learning import TextAnnotation, TextRecord
from prototype.classiang_contrastive import ContrastiveSpanEncoder, train_contrastive


def sample_records():
    rows = []
    for index in range(8):
        text = f"device{index} transfers water; through a narrow pipe"
        phrase = "transfers water"
        start = text.index(phrase)
        rows.append(TextRecord(
            observation_id=f"obs-{index}", subject_id=f"subject-{index}",
            domain="mechanical" if index < 4 else "biology",
            source_id=f"source-{index}", text=text,
            annotations=(TextAnnotation(
                start, start + len(phrase), "function", "transfers-water",
                ("recognition",),
            ),),
            group_id=f"source-family-{index}",
            negative_annotations=((text.index("narrow pipe"), text.index("narrow pipe") + len("narrow pipe")),),
        ))
    return tuple(rows)


class ContrastiveSpanTrainingTests(unittest.TestCase):
    def test_hard_negative_training_and_group_disjoint_validation(self):
        model, report = train_contrastive(sample_records(), seed=11, threshold=0.2)
        self.assertTrue(report["group_disjoint"])
        self.assertGreater(report["training"]["hard_negatives"], 0)
        self.assertIn("__none__", model.classes)
        self.assertGreaterEqual(report["validation"]["f1"], 0.0)
        self.assertLessEqual(report["validation"]["f1"], 1.0)
        self.assertGreater(report["validation"]["true_positive"], 0)
        self.assertGreater(report["validation"]["recall"], 0.0)

    def test_predict_preserves_source_evidence_offsets(self):
        rows = sample_records()
        model = ContrastiveSpanEncoder(epochs=20, learning_rate=0.35).fit(rows[:6], seed=3)
        row = rows[6]
        observation = model.predict(
            observation_id=row.observation_id, subject_id=row.subject_id,
            domain=row.domain, source_id=row.source_id, text=row.text,
            threshold=0.2,
        )
        for feature in observation.features:
            ref = feature.evidence_refs[0]
            self.assertTrue(ref.startswith(f"text:{row.source_id}:chars:"))
            start, end = map(int, ref.rsplit(":", 1)[1].split("-"))
            self.assertGreaterEqual(start, 0)
            self.assertLess(end, len(row.text) + 1)
            self.assertEqual(feature.atom.value, "transfers-water")
            self.assertEqual(row.text[start:end], "transfers water")

    def test_equal_scores_preserve_source_order_before_span_width(self):
        rows = sample_records()
        model = ContrastiveSpanEncoder().fit(rows[:6], seed=5)
        positive_label = next(label for label in model.classes if label != "__none__")
        model._scores = lambda _surface: {positive_label: 1.0, "__none__": 0.0}
        text = "abcdefghij later"
        with patch(
            "prototype.classiang_contrastive._candidate_spans",
            return_value=[(0, 10), (11, 16)],
        ):
            observation = model.predict(
                observation_id="tie-order", subject_id="tie-subject",
                domain="test", source_id="tie-source", text=text,
                threshold=0.5,
            )
        self.assertEqual(len(observation.features), 1)
        self.assertEqual(
            observation.features[0].evidence_refs,
            ("text:tie-source:chars:0-10",),
        )

    def test_checkpoint_round_trip_and_integrity(self):
        model = ContrastiveSpanEncoder().fit(sample_records()[:6], seed=7)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contrastive.json"
            digest = model.save(path)
            restored = ContrastiveSpanEncoder.load(path)
            self.assertEqual(restored.to_dict(), model.to_dict())
            self.assertEqual(len(digest), 64)
            path.write_text(path.read_text(encoding="utf-8").replace('"epochs": 12', '"epochs": 13'), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                ContrastiveSpanEncoder.load(path)

    def test_unknown_only_records_are_not_counted_as_training(self):
        rows = sample_records()[:6]
        unknown = TextRecord(
            observation_id="unknown-only", subject_id="unknown-subject",
            domain="test", source_id="unknown-source",
            text="unreviewed material", annotations=(),
            group_id="unknown-group",
        )
        model = ContrastiveSpanEncoder().fit(rows + (unknown,))
        self.assertEqual(model.training_records, 6)

    def test_positive_warmup_requires_at_least_two_epochs(self):
        with self.assertRaisesRegex(ValueError, "positive-only warmup"):
            ContrastiveSpanEncoder(epochs=1)

    def test_rejects_empty_training_data(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            ContrastiveSpanEncoder().fit(())

    def test_unannotated_text_is_not_silently_used_as_negative(self):
        rows = tuple(
            TextRecord(
                observation_id=f"unknown-{index}", subject_id=f"unknown-subject-{index}",
                domain="test", source_id=f"unknown-source-{index}",
                text="object transfers water through a narrow pipe",
                annotations=(),
                group_id=f"unknown-group-{index}",
            )
            for index in range(2)
        )
        with self.assertRaisesRegex(ValueError, "explicitly reviewed negative_annotations"):
            ContrastiveSpanEncoder().fit(rows)


if __name__ == "__main__":
    unittest.main()
