import hashlib
import unittest

from prototype.classiang_learning import (
    TextAnnotation,
    TextRecord,
    TrainableTextEncoder,
)
from prototype.classiang_review_queue import build_review_queue


def training_records():
    return (
        TextRecord(
            "obs-1", "subject-1", "mechanical", "source-1",
            "pump moves water", (TextAnnotation(5, 10, "function", "moves"),),
            group_id="family-1", negative_annotations=((0, 4),),
        ),
        TextRecord(
            "obs-2", "subject-2", "mechanical", "source-2",
            "valve blocks flow", (TextAnnotation(6, 12, "function", "blocks"),),
            group_id="family-2", negative_annotations=((0, 5),),
        ),
        TextRecord(
            "obs-3", "subject-3", "electrical", "source-3",
            "switch opens circuit", (TextAnnotation(7, 12, "function", "opens"),),
            group_id="family-3", negative_annotations=((0, 6),),
        ),
    )


class ClassiangReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.records = training_records()
        self.model = TrainableTextEncoder().fit(self.records)
        self.model_sha256 = hashlib.sha256(b"review-model-v1").hexdigest()

    def test_queue_preserves_exact_source_spans_and_excludes_reviewed_spans(self):
        queue = build_review_queue(
            self.records, self.model, model_sha256=self.model_sha256,
            max_items=50, max_per_group=10, max_per_observation=10,
        )
        self.assertGreater(queue["candidate_spans_scored"], 0)
        self.assertGreater(queue["selected_count"], 0)
        known = {
            (record.observation_id, start, end)
            for record in self.records
            for start, end in (
                [(a.start_char, a.end_char) for a in record.annotations]
                + list(record.negative_annotations)
            )
        }
        for item in queue["items"]:
            record = next(row for row in self.records
                          if row.observation_id == item["observation_id"])
            self.assertEqual(
                item["surface"],
                record.text[item["start_char"]:item["end_char"]],
            )
            self.assertEqual(
                item["evidence_ref"],
                f"text:{record.source_id}:chars:{item['start_char']}-{item['end_char']}",
            )
            self.assertNotIn(
                (item["observation_id"], item["start_char"], item["end_char"]),
                known,
            )
            self.assertEqual(item["review_status"], "pending_review")
            self.assertEqual(
                item["score_interpretation"],
                "uncalibrated_model_relative_softmax",
            )

    def test_model_suggestions_never_become_gold_labels(self):
        queue = build_review_queue(
            self.records, self.model, model_sha256=self.model_sha256,
        )
        self.assertTrue(queue["selection_policy"]["predictions_are_not_gold"])
        self.assertIn("Human-review queue only", queue["claim_boundary"])
        for item in queue["items"]:
            self.assertNotIn("annotations", item)
            self.assertNotIn("negative_annotations", item)
            self.assertNotIn("review_decision", item)
            self.assertIn("suggested_annotation", item)

    def test_selection_is_deterministic_and_respects_diversity_caps(self):
        first = build_review_queue(
            self.records, self.model, model_sha256=self.model_sha256,
            max_items=20, max_per_domain=2, max_per_group=1,
            max_per_observation=1,
        )
        second = build_review_queue(
            self.records, self.model, model_sha256=self.model_sha256,
            max_items=20, max_per_domain=2, max_per_group=1,
            max_per_observation=1,
        )
        self.assertEqual(first, second)
        self.assertEqual(len(first["items"]), 3)
        self.assertEqual(len({x["group_id"] for x in first["items"]}), 3)
        self.assertEqual(len({x["observation_id"] for x in first["items"]}), 3)

    def test_rejects_invalid_limits_or_model_digest(self):
        with self.assertRaisesRegex(ValueError, "max_items"):
            build_review_queue(
                self.records, self.model, model_sha256=self.model_sha256,
                max_items=0,
            )
        with self.assertRaisesRegex(ValueError, "model_sha256"):
            build_review_queue(
                self.records, self.model, model_sha256="not-a-digest",
            )

    def test_rejects_untrained_model_and_empty_records(self):
        with self.assertRaisesRegex(ValueError, "trained"):
            build_review_queue(
                self.records, TrainableTextEncoder(),
                model_sha256=self.model_sha256,
            )
        with self.assertRaisesRegex(ValueError, "non-empty"):
            build_review_queue(
                (), self.model, model_sha256=self.model_sha256,
            )


if __name__ == "__main__":
    unittest.main()
