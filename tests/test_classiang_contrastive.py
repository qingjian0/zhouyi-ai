import tempfile
import unittest
from pathlib import Path

from prototype.classiang_contrastive import (
    ContrastiveSpanEncoder, train_contrastive,
)
from tests.test_classiang_learning import records


class ContrastiveSpanTrainingTests(unittest.TestCase):
    def test_hard_negative_training_and_group_disjoint_validation(self):
        model, report = train_contrastive(records(), seed=11, threshold=0.2)
        self.assertTrue(report["group_disjoint"])
        self.assertGreater(report["training"]["hard_negatives"], 0)
        self.assertIn("__none__", model.classes)
        self.assertGreaterEqual(report["validation"]["f1"], 0.0)
        self.assertLessEqual(report["validation"]["f1"], 1.0)

    def test_predict_preserves_source_evidence_offsets(self):
        rows = records()
        model = ContrastiveSpanEncoder(epochs=20, learning_rate=0.35).fit(rows[:5], seed=3)
        row = rows[5]
        observation = model.predict(
            observation_id=row.observation_id, subject_id=row.subject_id,
            domain=row.domain, source_id=row.source_id, text=row.text,
            threshold=0.2,
        )
        if observation.features:
            for feature in observation.features:
                ref = feature.evidence_refs[0]
                self.assertTrue(ref.startswith(f"text:{row.source_id}:chars:"))
                start, end = map(int, ref.rsplit(":", 1)[1].split("-"))
                self.assertEqual(row.text[start:end], row.text[start:end])

    def test_checkpoint_round_trip_and_integrity(self):
        model = ContrastiveSpanEncoder().fit(records()[:5], seed=7)
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


if __name__ == "__main__":
    unittest.main()
