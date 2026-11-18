import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from prototype.n09_learnable_srok import RoleSpec
from prototype.n010_experiment import run_experiment
from prototype.n010_ooc import (
    N010StreamingDataset,
    evaluate_locked_test_ooc,
    run_experiment_ooc,
)
from prototype.n09_learnable_srok import LearnableSROKError


class N010OutOfCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.roles = tuple(
            RoleSpec(name, frozenset({name}), frozenset({"eligible"}))
            for name in ("r0", "r1")
        )
        self.train_dev = self.root / "train-dev.jsonl"
        self.locked_test = self.root / "locked-test.jsonl"
        self.full_dataset = self.root / "all-splits.jsonl"
        self._write(self.train_dev, self._rows(("train", "dev")))
        self._write(self.locked_test, self._rows(("locked_test",)))
        self._write(
            self.full_dataset,
            self._rows(("train", "dev", "locked_test")),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _rows(self, splits):
        rows = []
        prefixes = {"train": "tr", "dev": "dv", "locked_test": "te"}
        for split in splits:
            prefix = prefixes[split]
            for index in range(4):
                nodes = []
                targets = []
                for role in ("r0", "r1"):
                    target_id = f"{prefix}-{index}-{role}-positive"
                    targets.append(target_id)
                    nodes.extend([
                        {
                            "node_id": target_id,
                            "node_type": role,
                            "features": [1.0],
                            "tags": ["eligible"],
                            "evidence_ids": [f"e-{target_id}"],
                        },
                        {
                            "node_id": f"{prefix}-{index}-{role}-negative",
                            "node_type": role,
                            "features": [-1.0],
                            "tags": ["eligible"],
                            "evidence_ids": [],
                        },
                    ])
                rows.append({
                    "id": f"{prefix}-{index}",
                    "split": split,
                    "rule_family": "family-A" if split != "locked_test" else "family-OOD",
                    "group_id": f"{prefix}-source-{index // 2}",
                    "source_group_id": f"{prefix}-document-{index // 2}",
                    "nodes": nodes,
                    "target_ids": targets,
                })
        return rows

    @staticmethod
    def _write(path, rows):
        path.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

    def test_sqlite_index_and_split_iterators_are_repeatable(self):
        with N010StreamingDataset(
            self.train_dev, self.roles, 1, expected_splits=("train", "dev")
        ) as dataset:
            self.assertEqual(dataset.manifest["split_counts"], {"train": 4, "dev": 4})
            self.assertEqual(dataset.manifest["index"], "sqlite_metadata_only")
            self.assertNotIn("split_ids", dataset.manifest)
            first = [
                (example.target_ids, tuple(tuple(node.node_id for node in pool)
                                            for pool in example.role_candidates))
                for example in dataset.iter_training_examples()
            ]
            second = [
                (example.target_ids, tuple(tuple(node.node_id for node in pool)
                                            for pool in example.role_candidates))
                for example in dataset.iter_training_examples()
            ]
            self.assertEqual(first, second)
            self.assertEqual(len(first), 4)
            self.assertEqual(len(list(dataset.iter_split_rows("dev"))), 4)

    def test_sqlite_index_rejects_group_leakage(self):
        rows = self._rows(("train", "dev"))
        rows[0]["group_id"] = "same-source"
        rows[4]["group_id"] = "same-source"
        self._write(self.train_dev, rows)
        with self.assertRaisesRegex(LearnableSROKError, "group_id leakage"):
            N010StreamingDataset(
                self.train_dev, self.roles, 1, expected_splits=("train", "dev")
            )

    def test_stream_fails_closed_if_dataset_changes_after_indexing(self):
        with N010StreamingDataset(
            self.train_dev, self.roles, 1, expected_splits=("train", "dev")
        ) as dataset:
            self.train_dev.write_text(
                self.train_dev.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(LearnableSROKError, "dataset changed"):
                list(dataset.iter_training_examples())

    def test_ooc_training_matches_materialized_fullbatch_and_locked_test_is_separate(self):
        ooc_checkpoint = self.root / "ooc-run.json"
        materialized_checkpoint = self.root / "materialized-run.json"

        report = run_experiment_ooc(
            self.train_dev, self.roles, 1, ooc_checkpoint,
            epochs=3, max_expansions=64, git_sha="ooc-test",
        )
        run_experiment(
            self.full_dataset, self.roles, 1, materialized_checkpoint,
            epochs=3, max_expansions=64, seed=0, git_sha="ooc-test",
        )
        ooc_bundle = json.loads(ooc_checkpoint.read_text(encoding="utf-8"))
        materialized_bundle = json.loads(
            materialized_checkpoint.read_text(encoding="utf-8")
        )
        self.assertEqual(
            ooc_bundle["model_checkpoint"],
            materialized_bundle["model_checkpoint"],
        )
        self.assertEqual(report["training_examples"], 4)
        self.assertNotIn("locked_test", report)
        self.assertEqual(
            report["locked_test_policy"], "separate_artifact_and_evaluator_entry_point"
        )
        dev_predictions = Path(report["dev"]["predictions_path"])
        self.assertEqual(len(dev_predictions.read_text(encoding="utf-8").splitlines()), 4)

        locked = evaluate_locked_test_ooc(
            self.locked_test, self.roles, 1, ooc_checkpoint,
            max_expansions=64,
        )
        self.assertEqual(locked["locked_test"]["examples"], 4)
        self.assertEqual(
            len(Path(locked["locked_test"]["predictions_path"])
                .read_text(encoding="utf-8").splitlines()),
            4,
        )

    def test_streaming_index_rejects_missing_source_group_provenance(self):
        rows = self._rows(("train", "dev"))
        for row in rows:
            row.pop("group_id", None)
            row.pop("source_group_id", None)
            row.pop("episode_id", None)
        self._write(self.train_dev, rows)
        with self.assertRaisesRegex(
            LearnableSROKError,
            "each record must declare group_id, source_group_id, or episode_id",
        ):
            N010StreamingDataset(
                self.train_dev, self.roles, 1, expected_splits=("train", "dev")
            )

    def test_locked_test_evaluator_rejects_training_group_overlap(self):
        checkpoint = self.root / "isolated.json"
        run_experiment_ooc(
            self.train_dev, self.roles, 1, checkpoint,
            epochs=1, max_expansions=64, git_sha="isolation-test",
        )
        rows = self._rows(("locked_test",))
        rows[0]["group_id"] = "tr-source-0"
        self._write(self.locked_test, rows)
        with self.assertRaisesRegex(LearnableSROKError, "overlaps training/dev"):
            evaluate_locked_test_ooc(
                self.locked_test, self.roles, 1, checkpoint, max_expansions=64
            )

    def test_locked_test_evaluator_rejects_tampered_training_group_index(self):
        checkpoint = self.root / "tamper-index.json"
        run_experiment_ooc(
            self.train_dev, self.roles, 1, checkpoint,
            epochs=1, max_expansions=64, git_sha="index-integrity-test",
        )
        group_index = checkpoint.with_suffix(checkpoint.suffix + ".groups.sqlite3")
        with sqlite3.connect(group_index) as db:
            db.execute("DELETE FROM groups")
            db.commit()
        with self.assertRaisesRegex(
            LearnableSROKError, "training group index integrity mismatch"
        ):
            evaluate_locked_test_ooc(
                self.locked_test, self.roles, 1, checkpoint, max_expansions=64
            )

    def test_resume_rejects_missing_group_index(self):
        checkpoint = self.root / "resume-missing-index.json"
        run_experiment_ooc(
            self.train_dev, self.roles, 1, checkpoint,
            epochs=1, max_expansions=64, git_sha="resume-missing-index",
        )
        group_index = checkpoint.with_suffix(checkpoint.suffix + ".groups.sqlite3")
        group_index.unlink()
        with self.assertRaisesRegex(
            LearnableSROKError, "resume group index is missing"
        ):
            run_experiment_ooc(
                self.train_dev, self.roles, 1, checkpoint,
                epochs=2, max_expansions=64, git_sha="resume-missing-index",
                resume=True,
            )

    def test_resume_rejects_tampered_group_index_before_rebuild(self):
        checkpoint = self.root / "resume-tamper-index.json"
        run_experiment_ooc(
            self.train_dev, self.roles, 1, checkpoint,
            epochs=1, max_expansions=64, git_sha="resume-index-integrity",
        )
        group_index = checkpoint.with_suffix(checkpoint.suffix + ".groups.sqlite3")
        with sqlite3.connect(group_index) as db:
            db.execute("DELETE FROM groups")
            db.commit()
        with self.assertRaisesRegex(
            LearnableSROKError, "resume group index integrity mismatch"
        ):
            run_experiment_ooc(
                self.train_dev, self.roles, 1, checkpoint,
                epochs=2, max_expansions=64, git_sha="resume-index-integrity",
                resume=True,
            )

    def test_ooc_checkpoint_resume_is_exact(self):
        partial = self.root / "partial-ooc.json"
        full = self.root / "full-ooc.json"
        run_experiment_ooc(
            self.train_dev, self.roles, 1, partial,
            epochs=2, max_expansions=64, git_sha="same",
        )
        run_experiment_ooc(
            self.train_dev, self.roles, 1, partial,
            epochs=3, max_expansions=64, git_sha="same", resume=True,
        )
        run_experiment_ooc(
            self.train_dev, self.roles, 1, full,
            epochs=3, max_expansions=64, git_sha="same",
        )
        partial_bundle = json.loads(partial.read_text(encoding="utf-8"))
        full_bundle = json.loads(full.read_text(encoding="utf-8"))
        self.assertEqual(
            partial_bundle["model_checkpoint"], full_bundle["model_checkpoint"]
        )
        self.assertEqual(
            partial_bundle["loss_history"], full_bundle["loss_history"]
        )


if __name__ == "__main__":
    unittest.main()
