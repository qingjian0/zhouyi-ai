"""Reproducible experiment metadata and append-only local registry.

The registry records specifications and outcomes; it deliberately does not execute code.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .artifact_store import ArtifactRef
from .protocol import EvidenceRef, _require_json, _require_text

_STATUSES = {"completed", "failed", "cancelled"}


def _canonical(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("value must be finite JSON data") from exc


def _require_digest(value: str, name: str) -> None:
    if (not isinstance(value, str) or len(value) != 64
            or any(ch not in "0123456789abcdef" for ch in value)):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _require_revision(value: str) -> None:
    if (not isinstance(value, str) or not 7 <= len(value) <= 64
            or any(ch not in "0123456789abcdef" for ch in value.lower())):
        raise ValueError("code_revision must be a 7-64 character hexadecimal commit ID")


def _require_aware_timestamp(value: str) -> None:
    _require_text(value, "created_at")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("created_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("created_at must include a timezone offset")


def _validate_budget(value: dict[str, int | float]) -> None:
    if not isinstance(value, dict) or not value:
        raise ValueError("budget must be a non-empty object")
    for key, amount in value.items():
        _require_text(key, "budget key")
        if (isinstance(amount, bool) or not isinstance(amount, (int, float))
                or not math.isfinite(amount) or amount <= 0):
            raise ValueError(f"budget[{key}] must be a positive finite number")


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    hypothesis: str
    method: str
    model_id: str
    model_version: str
    dataset_id: str
    dataset_version: str
    dataset_digest: str
    code_revision: str
    seed: int
    environment: dict[str, Any]
    budget: dict[str, int | float]
    created_at: str
    baseline_id: str | None = None
    comparison_group: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("experiment_id", "hypothesis", "method", "model_id",
                     "model_version", "dataset_id", "dataset_version"):
            _require_text(getattr(self, name), name)
        _require_digest(self.dataset_digest, "dataset_digest")
        _require_revision(self.code_revision)
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        _require_aware_timestamp(self.created_at)
        if self.baseline_id is not None:
            _require_text(self.baseline_id, "baseline_id")
            if self.baseline_id == self.experiment_id:
                raise ValueError("experiment cannot be its own baseline")
        if self.comparison_group is not None:
            _require_text(self.comparison_group, "comparison_group")
        if not isinstance(self.environment, dict) or not isinstance(self.config, dict):
            raise ValueError("environment and config must be objects")
        _require_json(self.environment, "environment")
        _require_json(self.config, "config")
        _validate_budget(self.budget)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentResult:
    experiment_id: str
    status: str
    metrics: dict[str, int | float]
    artifacts: tuple[ArtifactRef, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    blockers: tuple[str, ...] = ()
    completed_at: str = ""

    def __post_init__(self) -> None:
        _require_text(self.experiment_id, "experiment_id")
        if self.status not in _STATUSES:
            raise ValueError(f"unsupported experiment status: {self.status}")
        if not isinstance(self.metrics, dict):
            raise ValueError("metrics must be an object")
        for key, value in self.metrics.items():
            _require_text(key, "metric name")
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value)):
                raise ValueError(f"metric {key} must be a finite number")
        if not isinstance(self.artifacts, tuple) or not all(
                isinstance(item, ArtifactRef) for item in self.artifacts):
            raise ValueError("artifacts must be a tuple of ArtifactRef")
        if not isinstance(self.evidence, tuple) or not all(
                isinstance(item, EvidenceRef) for item in self.evidence):
            raise ValueError("evidence must be a tuple of EvidenceRef")
        if not isinstance(self.blockers, tuple) or not all(
                isinstance(item, str) and item.strip() for item in self.blockers):
            raise ValueError("blockers must be a tuple of non-empty strings")
        _require_aware_timestamp(self.completed_at)
        _require_json(self.to_dict(), "experiment result")

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "status": self.status,
            "metrics": self.metrics,
            "artifacts": [asdict(item) for item in self.artifacts],
            "evidence": [asdict(item) for item in self.evidence],
            "blockers": list(self.blockers),
            "completed_at": self.completed_at,
        }


class ExperimentRegistry:
    """SQLite-backed, append-only registry. It stores metadata, never runs experiments."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    spec_json TEXT NOT NULL,
                    spec_digest TEXT NOT NULL,
                    result_json TEXT,
                    result_digest TEXT
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10.0)
        db.execute("PRAGMA busy_timeout = 10000")
        return db

    @staticmethod
    def _digest(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def register(self, spec: ExperimentSpec) -> str:
        if not isinstance(spec, ExperimentSpec):
            raise TypeError("spec must be ExperimentSpec")
        payload = _canonical(spec.to_dict())
        digest = self._digest(payload)
        try:
            with self._connect() as db:
                db.execute(
                    "INSERT INTO experiments (experiment_id, spec_json, spec_digest) VALUES (?, ?, ?)",
                    (spec.experiment_id, payload, digest),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"experiment already registered: {spec.experiment_id}") from exc
        return digest

    def record_result(self, result: ExperimentResult) -> str:
        if not isinstance(result, ExperimentResult):
            raise TypeError("result must be ExperimentResult")
        payload = _canonical(result.to_dict())
        digest = self._digest(payload)
        with self._connect() as db:
            row = db.execute(
                "SELECT result_json FROM experiments WHERE experiment_id = ?",
                (result.experiment_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"experiment not registered: {result.experiment_id}")
            if row[0] is not None:
                raise ValueError(f"result already recorded: {result.experiment_id}")
            changed = db.execute(
                "UPDATE experiments SET result_json = ?, result_digest = ? "
                "WHERE experiment_id = ? AND result_json IS NULL",
                (payload, digest, result.experiment_id),
            ).rowcount
            if changed != 1:
                raise ValueError(f"result already recorded: {result.experiment_id}")
        return digest

    def get_spec(self, experiment_id: str) -> ExperimentSpec:
        _require_text(experiment_id, "experiment_id")
        with self._connect() as db:
            row = db.execute(
                "SELECT spec_json, spec_digest FROM experiments WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"experiment not found: {experiment_id}")
        if self._digest(row[0]) != row[1]:
            raise ValueError("experiment specification integrity check failed")
        return ExperimentSpec(**json.loads(row[0]))

    def get_result(self, experiment_id: str) -> ExperimentResult | None:
        _require_text(experiment_id, "experiment_id")
        with self._connect() as db:
            row = db.execute(
                "SELECT result_json, result_digest FROM experiments WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"experiment not found: {experiment_id}")
        if row[0] is None:
            return None
        if self._digest(row[0]) != row[1]:
            raise ValueError("experiment result integrity check failed")
        raw = json.loads(row[0])
        return ExperimentResult(
            experiment_id=raw["experiment_id"], status=raw["status"],
            metrics=raw["metrics"],
            artifacts=tuple(ArtifactRef(**item) for item in raw["artifacts"]),
            evidence=tuple(EvidenceRef(**item) for item in raw["evidence"]),
            blockers=tuple(raw["blockers"]), completed_at=raw["completed_at"],
        )

    def list_experiment_ids(self) -> tuple[str, ...]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT experiment_id FROM experiments ORDER BY experiment_id"
            ).fetchall()
        return tuple(row[0] for row in rows)
