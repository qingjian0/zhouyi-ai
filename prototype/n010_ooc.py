"""Disk-indexed JSONL streaming for N0.10 out-of-core experiments.

Training and development live in one artifact. Locked-test labels are accepted
only by the separate evaluator entry point, so the training runner never opens
or parses the locked-test file.
"""
from __future__ import annotations

import hashlib
import inspect
import itertools
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from prototype.n09_learnable_srok import (
    LearnableSROK,
    LearnableSROKError,
    Node,
    RoleSpec,
    TrainingExample,
)
from prototype.n010_experiment import _node_from_json


OOC_RUN_SCHEMA = "zhouyi-ai.n010-ooc-run-v1"
OOC_DATASET_SCHEMA = "zhouyi-ai.n010-ooc-dataset-v1"
DEFAULT_MAX_RECORD_BYTES = 8 * 1024 * 1024


def _sha256_file(path: Path, *, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def _implementation_fingerprint() -> dict[str, str]:
    """Hash the training/evaluation implementation that defines checkpoint semantics."""
    learner_path = Path(inspect.getsourcefile(LearnableSROK) or "")
    if not learner_path.is_file():
        raise LearnableSROKError("cannot locate learner implementation for checkpoint fingerprint")
    return {
        "n010_ooc_sha256": _sha256_file(Path(__file__)),
        "n09_learnable_srok_sha256": _sha256_file(learner_path),
    }


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _parse_record(raw: bytes, line_number: int, roles: Sequence[RoleSpec],
                  feature_dim: int, allowed_splits: frozenset[str]) -> dict:
    try:
        item = json.loads(raw.decode("utf-8"))
        allowed = {
            "id", "split", "nodes", "target_ids", "rule_family",
            "group_id", "source_group_id", "episode_id",
        }
        required = {"id", "split", "nodes", "target_ids"}
        if not isinstance(item, dict) or not required.issubset(item) or set(item) - allowed:
            raise ValueError("record fields do not match schema")
        example_id, split = item["id"], item["split"]
        if not isinstance(example_id, str) or not example_id.strip():
            raise ValueError("id must be a non-empty string")
        if split not in allowed_splits:
            raise ValueError(f"split must be one of {sorted(allowed_splits)}")
        family = item.get("rule_family", "unspecified")
        if not isinstance(family, str) or not family.strip():
            raise ValueError("rule_family must be a non-empty string")
        group_ids = {}
        for field in ("group_id", "source_group_id", "episode_id"):
            value = item.get(field)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{field} must be a non-empty string")
                group_ids[field] = value
        if not group_ids:
            raise ValueError(
                "each record must declare group_id, source_group_id, or episode_id"
            )
        if not isinstance(item["nodes"], list) or not isinstance(item["target_ids"], list):
            raise ValueError("nodes and target_ids must be lists")
        nodes = tuple(_node_from_json(node) for node in item["nodes"])
        if not nodes or len({node.node_id for node in nodes}) != len(nodes):
            raise ValueError("each row requires non-empty unique nodes")
        if any(len(node.features) != feature_dim for node in nodes):
            raise ValueError("node feature dimension mismatch")
        targets = item["target_ids"]
        if (len(targets) != len(roles)
                or any(not isinstance(target, str) or not target.strip() for target in targets)
                or len(set(targets)) != len(targets)):
            raise ValueError("target IDs must be unique non-empty strings matching role count")
        pools = tuple(tuple(
            node for node in nodes
            if (not role.allowed_types or node.node_type in role.allowed_types)
            and role.required_tags.issubset(node.tags)
        ) for role in roles)
        if any(not pool for pool in pools):
            raise ValueError("every role requires at least one compatible candidate")
        return {
            "id": example_id,
            "split": split,
            "rule_family": family,
            "group_ids": group_ids,
            "nodes": nodes,
            "target_ids": tuple(targets),
            "pools": pools,
        }
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise LearnableSROKError(f"invalid dataset row {line_number}: {exc}") from exc


class N010StreamingDataset:
    """SQLite-indexed metadata plus repeatable, one-record-at-a-time JSONL iterators."""

    def __init__(self, path: str | Path, roles: Sequence[RoleSpec], feature_dim: int,
                 *, expected_splits: Sequence[str],
                 max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES):
        if not expected_splits or any(
            split not in {"train", "dev", "locked_test"} for split in expected_splits
        ):
            raise LearnableSROKError("expected_splits must contain valid split names")
        if isinstance(feature_dim, bool) or not isinstance(feature_dim, int) or feature_dim < 1:
            raise LearnableSROKError("feature_dim must be a positive integer")
        if (isinstance(max_record_bytes, bool) or not isinstance(max_record_bytes, int)
                or max_record_bytes < 1):
            raise LearnableSROKError("max_record_bytes must be a positive integer")
        self.path = Path(path)
        self.roles = tuple(roles)
        self.feature_dim = feature_dim
        self.expected_splits = frozenset(expected_splits)
        self.max_record_bytes = max_record_bytes
        self._temporary = tempfile.TemporaryDirectory(prefix="zhouyi-n010-index-")
        self._db_path = Path(self._temporary.name) / "metadata.sqlite3"
        self._db = sqlite3.connect(str(self._db_path))
        self._db.execute("PRAGMA cache_size=-2048")
        self._db.execute("PRAGMA temp_store=FILE")
        self._db.execute("PRAGMA journal_mode=OFF")
        self._db.execute("""
            CREATE TABLE records (
                id TEXT PRIMARY KEY,
                split TEXT NOT NULL,
                rule_family TEXT NOT NULL,
                group_id TEXT,
                source_group_id TEXT,
                episode_id TEXT
            )
        """)
        self._db.execute("CREATE INDEX records_split_idx ON records(split)")
        self._db.execute("CREATE INDEX records_family_idx ON records(rule_family, split)")
        self._db.execute("""
            CREATE TABLE group_fingerprints (
                field TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                PRIMARY KEY(field, fingerprint)
            )
        """)
        self._db.commit()
        self.sha256 = _sha256_file(self.path)
        try:
            self.manifest = self._build_index()
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if getattr(self, "_db", None) is not None:
            self._db.close()
            self._db = None
        if getattr(self, "_temporary", None) is not None:
            self._temporary.cleanup()
            self._temporary = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _assert_unchanged(self) -> None:
        if _sha256_file(self.path) != self.sha256:
            raise LearnableSROKError("dataset changed after its streaming index was built")

    def _build_index(self) -> dict:
        counts = {split: 0 for split in self.expected_splits}
        try:
            with self.path.open("rb") as source:
                for line_number, raw in enumerate(source, 1):
                    if len(raw) > self.max_record_bytes:
                        raise LearnableSROKError(
                            f"dataset row {line_number} exceeds max_record_bytes={self.max_record_bytes}"
                        )
                    if not raw.strip():
                        continue
                    row = _parse_record(
                        raw, line_number, self.roles, self.feature_dim,
                        self.expected_splits,
                    )
                    groups = row["group_ids"]
                    try:
                        self._db.execute(
                            "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                row["id"], row["split"], row["rule_family"],
                                groups.get("group_id"), groups.get("source_group_id"),
                                groups.get("episode_id"),
                            ),
                        )
                    except sqlite3.IntegrityError as exc:
                        raise LearnableSROKError(
                            f"duplicate example id at dataset row {line_number}"
                        ) from exc
                    for field, value in groups.items():
                        fingerprint = hashlib.sha256(
                            (field + "\\0" + value).encode("utf-8")
                        ).hexdigest()
                        self._db.execute(
                            "INSERT OR IGNORE INTO group_fingerprints VALUES (?, ?)",
                            (field, fingerprint),
                        )
                    counts[row["split"]] += 1
            self._db.commit()
        except OSError as exc:
            raise LearnableSROKError(f"cannot read dataset: {exc}") from exc

        if any(count == 0 for count in counts.values()):
            raise LearnableSROKError("every expected split must be non-empty")

        for field in ("group_id", "source_group_id", "episode_id"):
            overlap = self._db.execute(f"""
                SELECT 1 FROM records a JOIN records b
                  ON a.{field} = b.{field}
                 WHERE a.{field} IS NOT NULL AND a.split <> b.split
                 LIMIT 1
            """).fetchone()
            if overlap:
                raise LearnableSROKError(f"{field} leakage across dataset splits")

        family_hashers = {
            split: hashlib.sha256() for split in self.expected_splits
        }
        family_unique_counts = {split: 0 for split in self.expected_splits}
        family_record_counts = {split: 0 for split in self.expected_splits}
        family_cursor = self._db.execute(
            "SELECT split, rule_family, COUNT(*) FROM records "
            "GROUP BY split, rule_family ORDER BY split, rule_family"
        )
        for split, family, count in family_cursor:
            encoded = _canonical_json([family, count]).encode("utf-8")
            family_hashers[split].update(len(encoded).to_bytes(8, "big"))
            family_hashers[split].update(encoded)
            family_unique_counts[split] += 1
            family_record_counts[split] += count
        families_by_split = {
            split: {
                "unique_family_count": family_unique_counts[split],
                "family_index_sha256": family_hashers[split].hexdigest(),
                "record_count": family_record_counts[split],
            }
            for split in self.expected_splits
        }

        group_counts = {}
        for field in ("group_id", "source_group_id", "episode_id"):
            group_counts[field] = {}
            for split in self.expected_splits:
                count = self._db.execute(
                    f"SELECT COUNT(DISTINCT {field}) FROM records WHERE split=? AND {field} IS NOT NULL",
                    (split,),
                ).fetchone()[0]
                group_counts[field][split] = count

        provenance_path = self.path.with_suffix(self.path.suffix + ".manifest.json")
        provenance = None
        if provenance_path.exists():
            try:
                provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise LearnableSROKError("invalid generation provenance manifest") from exc
            if (not isinstance(provenance, dict)
                    or provenance.get("schema") != "zhouyi-ai.n010-synthetic-rule-families-v1"
                    or provenance.get("dataset_sha256") != self.sha256):
                raise LearnableSROKError("generation provenance schema/hash mismatch")
            expected_families = provenance.get("rule_families_by_split")
            if not isinstance(expected_families, dict):
                raise LearnableSROKError("generation provenance family map is invalid")
            for split in self.expected_splits:
                expected_rows = expected_families.get(split)
                if not isinstance(expected_rows, list):
                    raise LearnableSROKError("generation provenance rule-family list is invalid")
                actual_rows = (
                    row[0] for row in self._db.execute(
                        "SELECT DISTINCT rule_family FROM records WHERE split=? ORDER BY rule_family",
                        (split,),
                    )
                )
                if any(left != right for left, right in itertools.zip_longest(
                    expected_rows, actual_rows, fillvalue=None
                )):
                    raise LearnableSROKError("generation provenance rule-family split mismatch")

        manifest = {
            "schema": OOC_DATASET_SCHEMA,
            "sha256": self.sha256,
            "records": sum(counts.values()),
            "split_counts": counts,
            "rule_families_by_split": families_by_split,
            "group_counts_by_split": group_counts,
            "feature_dim": self.feature_dim,
            "roles": [
                {"name": role.name, "allowed_types": sorted(role.allowed_types),
                 "required_tags": sorted(role.required_tags)}
                for role in self.roles
            ],
            "max_record_bytes": self.max_record_bytes,
            "index": "sqlite_metadata_only",
        }
        if provenance is not None:
            manifest["generation_provenance_sha256"] = hashlib.sha256(
                _canonical_json(provenance).encode("utf-8")
            ).hexdigest()
        # Bind the metadata index to one stable byte snapshot. The initial
        # digest is captured before indexing; re-hash after the scan so a file
        # replaced or edited during index construction cannot be accepted.
        self._assert_unchanged()
        return manifest

    def write_group_index(self, output_path: str | Path) -> Path:
        """Persist exact hashed group membership for later isolated evaluation."""
        self._assert_unchanged()
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        if temporary.exists():
            temporary.unlink()
        target = sqlite3.connect(str(temporary))
        try:
            target.execute("""
                CREATE TABLE groups (
                    field TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    PRIMARY KEY(field, fingerprint)
                )
            """)
            cursor = self._db.execute(
                "SELECT field, fingerprint FROM group_fingerprints ORDER BY field, fingerprint"
            )
            while rows := cursor.fetchmany(2048):
                target.executemany("INSERT INTO groups VALUES (?, ?)", rows)
            target.commit()
        finally:
            target.close()
        os.replace(temporary, output)
        return output

    def assert_no_group_overlap(self, training_group_index: str | Path) -> None:
        """Reject held-out rows sharing any declared source group with training."""
        self._assert_unchanged()
        index_path = Path(training_group_index)
        if not index_path.exists():
            raise LearnableSROKError("training group index is missing")
        try:
            self._db.execute("ATTACH DATABASE ? AS training_groups", (str(index_path),))
            overlap = self._db.execute("""
                SELECT 1 FROM group_fingerprints heldout
                JOIN training_groups.groups trained
                  ON heldout.field = trained.field
                 AND heldout.fingerprint = trained.fingerprint
                LIMIT 1
            """).fetchone()
            if overlap:
                raise LearnableSROKError(
                    "locked-test source group overlaps training/dev data"
                )
        finally:
            try:
                self._db.execute("DETACH DATABASE training_groups")
            except sqlite3.Error:
                pass

    def iter_split_rows(self, split: str) -> Iterator[dict]:
        if split not in self.expected_splits:
            raise LearnableSROKError(f"split {split!r} is not indexed")
        self._assert_unchanged()
        try:
            with self.path.open("rb") as source:
                for line_number, raw in enumerate(source, 1):
                    if len(raw) > self.max_record_bytes:
                        raise LearnableSROKError(
                            f"dataset row {line_number} exceeds max_record_bytes={self.max_record_bytes}"
                        )
                    if not raw.strip():
                        continue
                    # Parse only rows belonging to the requested split after a
                    # lightweight JSON split check; no split's examples are retained.
                    try:
                        item = json.loads(raw.decode("utf-8"))
                        row_split = item.get("split") if isinstance(item, dict) else None
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise LearnableSROKError(
                            f"invalid dataset row {line_number}: {exc}"
                        ) from exc
                    if row_split != split:
                        continue
                    yield _parse_record(
                        raw, line_number, self.roles, self.feature_dim,
                        self.expected_splits,
                    )
        finally:
            self._assert_unchanged()

    def iter_training_examples(self) -> Iterator[TrainingExample]:
        if "train" not in self.expected_splits:
            raise LearnableSROKError("this dataset index has no train split")
        for row in self.iter_split_rows("train"):
            yield TrainingExample(
                role_candidates=tuple(tuple(pool) for pool in row["pools"]),
                target_ids=tuple(row["target_ids"]),
            )


def _atomic_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                         allow_nan=False) + "\n"
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(path.parent),
            prefix=path.name + ".", suffix=".tmp", delete=False,
        ) as target:
            temporary_path = Path(target.name)
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def evaluate_to_jsonl(model: LearnableSROK, rows: Iterable[dict],
                      output_path: str | Path, *, max_expansions: int = 4096,
                      search_strategy: str = "product", beam_width: int = 64) -> dict:
    """Evaluate a stream and write each prediction immediately; never collect rows."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    digest = hashlib.sha256()
    correct = covered = exhausted = total = 0
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=str(output.parent), prefix=output.name + ".",
            suffix=".tmp", delete=False,
        ) as sink:
            temporary_path = Path(sink.name)
            for row in rows:
                result = model.predict(
                    row["nodes"], retrieval_mode="joint",
                    search_strategy=search_strategy, beam_width=beam_width,
                    max_expansions=max_expansions, result_limit=1,
                )
                prediction = None if result.abstained or not result.candidates else tuple(
                    node_id for _, node_id in result.candidates[0].role_bindings
                )
                matched = prediction == row["target_ids"]
                covered += int(prediction is not None)
                correct += int(matched)
                exhausted += int(result.budget_exhausted)
                total += 1
                encoded = (_canonical_json({
                    "id": row["id"],
                    "prediction": prediction,
                    "target_match": matched,
                }) + "\n").encode("utf-8")
                sink.write(encoded)
                digest.update(encoded)
            sink.flush()
            os.fsync(sink.fileno())
        if total == 0:
            raise LearnableSROKError("evaluation stream must not be empty")
        os.replace(temporary_path, output)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    return {
        "search_strategy": search_strategy,
        "beam_width": beam_width,
        "examples": total,
        "exact_match_accuracy": correct / total,
        "coverage": covered / total,
        "abstention_rate": (total - covered) / total,
        "budget_exhaustion_rate": exhausted / total,
        "covered_accuracy": correct / covered if covered else 0.0,
        "predictions_path": str(output),
        "predictions_sha256": digest.hexdigest(),
    }


def run_experiment_ooc(dataset_path: str | Path, roles: Sequence[RoleSpec],
                       feature_dim: int, checkpoint_path: str | Path, *,
                       epochs: int = 20, learning_rate: float = 0.2,
                       l2: float = 1e-4, max_assignments_per_example: int = 4096,
                       max_expansions: int = 4096, beam_width: int = 64,
                       git_sha: str = "unknown", resume: bool = False) -> dict:
    """Train from train/dev JSONL only; this function has no locked-test path."""
    if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
        raise LearnableSROKError("epochs must be a positive integer")
    if not isinstance(git_sha, str) or not git_sha.strip():
        raise LearnableSROKError("git_sha must be a non-empty string")
    checkpoint = Path(checkpoint_path)
    implementation_fingerprint = _implementation_fingerprint()
    with N010StreamingDataset(
        dataset_path, roles, feature_dim, expected_splits=("train", "dev")
    ) as dataset:
        group_index_path = checkpoint.with_suffix(checkpoint.suffix + ".groups.sqlite3")
        dataset.write_group_index(group_index_path)
        group_index_sha256 = _sha256_file(group_index_path)
        config = {
            "epochs": epochs,
            "learning_rate": learning_rate,
            "l2": l2,
            "max_assignments_per_example": max_assignments_per_example,
            "max_expansions": max_expansions,
            "beam_width": beam_width,
            "git_sha": git_sha,
        }
        history = []
        completed_epochs = 0
        if resume:
            if not checkpoint.exists():
                raise LearnableSROKError("resume checkpoint does not exist")
            bundle = json.loads(checkpoint.read_text(encoding="utf-8"))
            if (bundle.get("schema") != OOC_RUN_SCHEMA
                    or bundle.get("dataset_manifest") != dataset.manifest):
                raise LearnableSROKError("resume dataset/schema does not match")
            if bundle.get("group_index_sha256") != group_index_sha256:
                raise LearnableSROKError("resume group index integrity mismatch")
            if bundle.get("implementation_fingerprint") != implementation_fingerprint:
                raise LearnableSROKError("resume implementation fingerprint does not match")
            saved_config = bundle.get("config", {})
            if {k: v for k, v in saved_config.items() if k != "epochs"} != {
                k: v for k, v in config.items() if k != "epochs"
            }:
                raise LearnableSROKError("resume configuration does not match")
            model = LearnableSROK.from_checkpoint_json(bundle["model_checkpoint"])
            history = list(bundle["loss_history"])
            completed_epochs = bundle["completed_epochs"]
            if (isinstance(completed_epochs, bool) or not isinstance(completed_epochs, int)
                    or completed_epochs < 0 or epochs < completed_epochs):
                raise LearnableSROKError("invalid checkpoint epoch progress")
        else:
            model = LearnableSROK(roles, feature_dim)

        for epoch in range(completed_epochs, epochs):
            losses = model.fit_reiterable(
                dataset.iter_training_examples,
                epochs=1,
                learning_rate=learning_rate,
                l2=l2,
                max_assignments_per_example=max_assignments_per_example,
            )
            history.extend(losses)
            _atomic_write_json(checkpoint, {
                "schema": OOC_RUN_SCHEMA,
                "dataset_manifest": dataset.manifest,
                "group_index_path": str(group_index_path),
                "group_index_sha256": group_index_sha256,
                "implementation_fingerprint": implementation_fingerprint,
                "config": config,
                "completed_epochs": epoch + 1,
                "loss_history": history,
                "model_checkpoint": model.checkpoint_json(),
            })

        dev_metrics = evaluate_to_jsonl(
            model, dataset.iter_split_rows("dev"),
            checkpoint.with_suffix(checkpoint.suffix + ".dev-predictions.jsonl"),
            max_expansions=max_expansions,
        )
        report = {
            "schema": OOC_RUN_SCHEMA,
            "dataset_manifest": dataset.manifest,
            "config": config,
            "completed_epochs": epochs,
            "training_examples": dataset.manifest["split_counts"]["train"],
            "loss_history": history,
            "dev": dev_metrics,
            "checkpoint": str(checkpoint),
            "locked_test_policy": "separate_artifact_and_evaluator_entry_point",
        }
        _atomic_write_json(
            checkpoint.with_suffix(checkpoint.suffix + ".report.json"), report
        )
        return report


def evaluate_locked_test_ooc(locked_test_path: str | Path, roles: Sequence[RoleSpec],
                             feature_dim: int, checkpoint_path: str | Path, *,
                             max_expansions: int = 4096,
                             beam_width: int = 64) -> dict:
    """Separate evaluator entry point; invoke in a separate process after training is frozen."""
    checkpoint = Path(checkpoint_path)
    if not checkpoint.exists():
        raise LearnableSROKError("training checkpoint does not exist")
    bundle = json.loads(checkpoint.read_text(encoding="utf-8"))
    if bundle.get("implementation_fingerprint") != _implementation_fingerprint():
        raise LearnableSROKError("locked-test evaluator implementation fingerprint does not match")
    if bundle.get("schema") != OOC_RUN_SCHEMA:
        raise LearnableSROKError("unsupported out-of-core checkpoint schema")
    model = LearnableSROK.from_checkpoint_json(bundle["model_checkpoint"])
    with N010StreamingDataset(
        locked_test_path, roles, feature_dim, expected_splits=("locked_test",)
    ) as dataset:
        training_manifest = bundle.get("dataset_manifest", {})
        group_index_path = checkpoint.with_suffix(checkpoint.suffix + ".groups.sqlite3")
        expected_group_index_sha256 = bundle.get("group_index_sha256")
        if (not isinstance(expected_group_index_sha256, str)
                or _sha256_file(group_index_path) != expected_group_index_sha256):
            raise LearnableSROKError("training group index integrity mismatch")
        dataset.assert_no_group_overlap(group_index_path)
        if (training_manifest.get("feature_dim") != dataset.manifest["feature_dim"]
                or training_manifest.get("roles") != dataset.manifest["roles"]
                or model.feature_dim != feature_dim):
            raise LearnableSROKError("locked-test schema does not match the frozen training model")
        metrics = evaluate_to_jsonl(
            model, dataset.iter_split_rows("locked_test"),
            checkpoint.with_suffix(checkpoint.suffix + ".locked-test-predictions.jsonl"),
            max_expansions=max_expansions,
        )
        report = {
            "schema": OOC_RUN_SCHEMA,
            "dataset_manifest": dataset.manifest,
            "checkpoint_dataset_sha256": bundle["dataset_manifest"]["sha256"],
            "checkpoint": str(checkpoint),
            "locked_test": metrics,
            "process_boundary": "separate_evaluator_entry_point",
        }
        _atomic_write_json(
            checkpoint.with_suffix(checkpoint.suffix + ".locked-test-report.json"),
            report,
        )
        return report
