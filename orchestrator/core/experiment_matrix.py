"""Deterministic experiment-matrix expansion for reproducible research runs.

This module compiles a declarative Cartesian product into ordinary scheduler
TaskSpec instances. It deliberately does not execute tasks or interpret
research semantics.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .scheduler import TaskSpec


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("experiment manifest must contain finite JSON values") from exc


def _unique_nonempty_strings(name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"{name} must be a non-empty tuple")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{name} must contain non-empty strings")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} values must be unique")


@dataclass(frozen=True)
class ExperimentMatrix:
    """A reproducible Cartesian product of tracks, conditions and seeds.

    Input order is preserved and is part of the manifest identity. A caller
    changing the order therefore creates a different manifest digest.
    """

    experiment: str
    handler: str
    seeds: tuple[int, ...]
    conditions: tuple[str, ...]
    tracks: tuple[str, ...]
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (("experiment", self.experiment), ("handler", self.handler)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.seeds, tuple) or not self.seeds:
            raise ValueError("seeds must be a non-empty tuple")
        if any(isinstance(seed, bool) or not isinstance(seed, int) or seed < 0 for seed in self.seeds):
            raise ValueError("seeds must contain non-negative integers")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("seeds must be unique")
        _unique_nonempty_strings("conditions", self.conditions)
        _unique_nonempty_strings("tracks", self.tracks)
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be an object")
        # Validate at construction time, not halfway through task expansion.
        _canonical_json(self.payload)

    @property
    def task_count(self) -> int:
        return len(self.tracks) * len(self.conditions) * len(self.seeds)

    def manifest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "experiment": self.experiment,
            "handler": self.handler,
            "tracks": list(self.tracks),
            "conditions": list(self.conditions),
            "seeds": list(self.seeds),
            "payload": self.payload,
            "task_count": self.task_count,
        }

    @property
    def digest(self) -> str:
        encoded = _canonical_json(self.manifest()).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_tasks(self) -> list[TaskSpec]:
        """Expand in stable track -> condition -> seed order."""
        tasks: list[TaskSpec] = []
        matrix_digest = self.digest
        for track_index, track in enumerate(self.tracks):
            for condition_index, condition in enumerate(self.conditions):
                for seed_index, seed in enumerate(self.seeds):
                    task_id = (
                        f"exp-{track_index:03d}-{condition_index:03d}-{seed_index:03d}"
                    )
                    task_payload = {
                        "experiment": self.experiment,
                        "matrix_digest": matrix_digest,
                        "track": track,
                        "condition": condition,
                        "seed": seed,
                        "payload": json.loads(_canonical_json(self.payload)),
                    }
                    tasks.append(TaskSpec(task_id, self.handler, payload=task_payload))
        return tasks
