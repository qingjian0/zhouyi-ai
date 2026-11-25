import json
import tempfile
import unittest
from pathlib import Path

from prototype.classiang_learning_workflow import (
    cross_domain_evaluation, discover_text_classes, load_reviewed_feedback, train_deploy_workflow,
)
from prototype.classiang_learning import TextAnnotation, TextRecord, TrainableTextEncoder


def sample_records():
    rows = []
    for i in range(8):
        domain = "mechanical" if i < 4 else "biology"
        text = f"object {i} transfers water"
        start = text.index("transfers water")
        rows.append({
            "observation_id": f"obs-{i}", "subject_id": f"subject-{i}",
            "domain": domain, "source_id": f"src-{i}", "text": text,
            "group_id": f"group-{i}",
            "negative_annotations": [{
                "start_char": text.index("object"),
                "end_char": text.index("object") + len("object"),
            }],
            "annotations": [{
                "start_char": start, "end_char": start + len("transfers water"),
                "dimension": "function", "value": "transfers-water",
                "purposes": ["recognition"],
            }],
        })
    return {"schema_version": 1, "examples": rows}


class ClassiangLearningWorkflowTests(unittest.TestCase):
    def test_feedback_records_are_revalidated_and_rejects_become_hard_negatives(self):
        payload = sample_records()
        accepted = dict(payload["examples"][0])
        accepted["observation_id"] = "feedback-accepted"
        rejected = dict(payload["examples"][1])
        rejected["observation_id"] = "feedback-rejected"
        rejected["annotations"] = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feedback.jsonl"
            events = [
                {"event_id": "event-1", "reviewer_id": "human-a",
                 "decision": "correct", "record": accepted},
                {"event_id": "event-2", "reviewer_id": "human-b",
                 "decision": "reject", "record": rejected},
            ]
            path.write_text("".join(json.dumps(x) + "\n" for x in events), encoding="utf-8")
            loaded = load_reviewed_feedback(path)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0].observation_id, "feedback-accepted")
            self.assertEqual(loaded[1].annotations, ())

    def test_reject_feedback_cannot_smuggle_positive_labels(self):
        row = sample_records()["examples"][0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feedback.jsonl"
            path.write_text(json.dumps({
                "event_id": "event-1", "reviewer_id": "human",
                "decision": "reject", "record": row,
            }) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "empty-annotation"):
                load_reviewed_feedback(path)

    def test_cross_domain_evaluation_reports_held_out_domains(self):
        rows = []
        for item in sample_records()["examples"]:
            annotations = tuple(TextAnnotation(
                x["start_char"], x["end_char"], x["dimension"], x["value"],
                tuple(x["purposes"]),
            ) for x in item["annotations"])
            rows.append(TextRecord(
                item["observation_id"], item["subject_id"], item["domain"],
                item["source_id"], item["text"], annotations, (),
                item["group_id"],
                tuple((x["start_char"], x["end_char"])
                      for x in item["negative_annotations"]),
            ))
        report = cross_domain_evaluation(tuple(rows), threshold=0.2)
        self.assertEqual(report["status"], "evaluated")
        self.assertEqual(report["evaluated_folds"], 2)
        self.assertEqual(
            {x["held_out_domain"] for x in report["folds"]},
            {"mechanical", "biology"},
        )

    def test_cross_domain_fold_skips_when_training_has_no_reviewed_negatives(self):
        rows = []
        for item in sample_records()["examples"]:
            annotations = tuple(TextAnnotation(
                x["start_char"], x["end_char"], x["dimension"], x["value"],
                tuple(x["purposes"]),
            ) for x in item["annotations"])
            negatives = tuple(
                (x["start_char"], x["end_char"])
                for x in item["negative_annotations"]
            )
            if item["domain"] == "mechanical":
                negatives = ()
            rows.append(TextRecord(
                item["observation_id"], item["subject_id"], item["domain"],
                item["source_id"], item["text"], annotations, (),
                item["group_id"], negatives,
            ))
        report = cross_domain_evaluation(tuple(rows), threshold=0.2)
        mechanical_train_fold = next(
            fold for fold in report["folds"]
            if fold["held_out_domain"] == "biology"
        )
        self.assertEqual(mechanical_train_fold["status"], "not_run")
        self.assertIn("reviewed negative supervision", mechanical_train_fold["reason"])

    def test_learned_text_features_feed_unreviewed_class_discovery(self):
        source = []
        for item in sample_records()["examples"][:4]:
            annotation = item["annotations"][0]
            source.append(TextRecord(
                item["observation_id"], item["subject_id"], item["domain"],
                item["source_id"], item["text"],
                (TextAnnotation(
                    annotation["start_char"], annotation["end_char"],
                    annotation["dimension"], annotation["value"],
                    tuple(annotation["purposes"]),
                ),), (), item["group_id"],
                tuple((x["start_char"], x["end_char"])
                      for x in item["negative_annotations"]),
            ))
        model = TrainableTextEncoder().fit(tuple(source))
        result = discover_text_classes(
            model, tuple(source), purpose="recognition", min_support=0.5,
        )
        self.assertEqual(result.object_count, 4)
        self.assertTrue(result.candidates)
        self.assertEqual(result.candidates[0].status, "unreviewed_candidate")
        self.assertTrue(result.candidates[0].evidence_refs)

    def test_training_workflow_saves_checkpoint_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset.json"
            dataset.write_text(json.dumps(sample_records()), encoding="utf-8")
            model, report = train_deploy_workflow(
                dataset, checkpoint_path=root / "model.json",
                report_path=root / "report.json", seed=5,
            )
            self.assertTrue((root / "model.json").exists())
            self.assertTrue((root / "report.json").exists())
            self.assertEqual(report["training"]["records"], 6)
            self.assertEqual(report["validation"]["records"], 2)
            self.assertEqual(report["cross_domain"]["evaluated_folds"], 2)
            self.assertEqual(model.training_records, 6)


if __name__ == "__main__":
    unittest.main()
