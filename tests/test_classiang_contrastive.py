import tempfile
import unittest
from pathlib import Path

from prototype.classiang_learning import TextAnnotation, TextRecord
from prototype.classiang_contrastive import ContrastiveSpanEncoder, train_contrastive


def sample_records():
    rows = []
    for index in range(8):
        text = f"device{index} transfers water through a narrow pipe"
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
