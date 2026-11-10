"""Phase-gated evaluator for sequential E10-A Query delivery.

This is a trusted-process orchestration primitive, not a security sandbox.
Keep this evaluator object and its truth mapping outside the learner process.
"""
from __future__ import annotations

import copy
from typing import Any

from prototype.e10a_prequential_ledger import PrequentialLedger


class PhaseGatedEvaluator:
    """Release one unlabeled Query at a time, then reveal only after its commit."""

    def __init__(
        self, *, query_payload: dict[str, Any],
        evaluator_truth: dict[str, Any], ledger: PrequentialLedger,
    ):
        if not isinstance(query_payload, dict) or query_payload.get("phase") != "query":
            raise ValueError("query_payload must be an E10-A Query payload")
        if not isinstance(evaluator_truth, dict):
            raise ValueError("evaluator_truth must be a dictionary")
        if query_payload.get("mechanism_hash") != evaluator_truth.get("mechanism_hash"):
            raise ValueError("query/evaluator mechanism hash mismatch")
        observations = query_payload.get("observations")
        objects = query_payload.get("objects")
        truth_rows = evaluator_truth.get("query_truth")
        if not isinstance(observations, list) or not isinstance(objects, list):
            raise ValueError("query observations and objects must be lists")
        if not isinstance(truth_rows, list):
            raise ValueError("evaluator query_truth must be a list")

        query_ids = [row.get("observation_id") for row in observations]
        truth_ids = [row.get("observation_id") for row in truth_rows]
        if len(query_ids) != len(set(query_ids)) or set(query_ids) != set(truth_ids):
            raise ValueError("query/evaluator observation IDs must match uniquely")
        object_ids = {row.get("object_id") for row in objects}
        if len(object_ids) != len(objects) or None in object_ids:
            raise ValueError("query object IDs must be unique and non-empty")
        for row in observations:
            if {"outcome", "valid", "violation", "template_id",
                "role_objects", "source_group_id"}.intersection(row):
                raise ValueError("Query learner payload contains evaluator fields")
            if not set(row.get("participants", [])) <= object_ids:
                raise ValueError("Query observation references an unknown Query object")
        for row in truth_rows:
            if not isinstance(row.get("valid"), bool):
                raise ValueError("evaluator query labels must be exact booleans")

        self._query = copy.deepcopy(query_payload)
        self._truth = {
            row["observation_id"]: copy.deepcopy(row) for row in truth_rows
        }
        self._ledger = ledger
        self._index = 0
        self._pending_observation_id: str | None = None
        self._object_table_sent = False

    def open_next_query(self) -> dict[str, Any] | None:
        """Release the next unlabeled observation only after the prior reveal."""
        if self._pending_observation_id is not None:
            raise ValueError("current Query must be committed and revealed before advancing")
        rows = self._query["observations"]
        if self._index >= len(rows):
            return None
        row = rows[self._index]
        self._pending_observation_id = row["observation_id"]
        self._index += 1
        object_table = [] if self._object_table_sent else copy.deepcopy(self._query["objects"])
        self._object_table_sent = True
        return {
            "schema_version": self._query["schema_version"],
            "phase": "query",
            "mechanism_hash": self._query["mechanism_hash"],
            "objects": object_table,
            "observation": copy.deepcopy(row),
            "query_index": self._index - 1,
        }

    def reveal_current(self, *, prediction_id: str, reveal_id: str) -> dict[str, Any]:
        """Reveal current target only after a matching durable prediction commit."""
        if self._pending_observation_id is None:
            raise ValueError("there is no open Query observation")
        commit = self._ledger.committed_prediction_for_observation(
            self._pending_observation_id
        )
        if commit is None:
            raise ValueError("current Query has no committed prediction")
        if commit["prediction_id"] != prediction_id:
            raise ValueError("prediction commit does not match current Query")
        truth = self._truth[self._pending_observation_id]
        reveal = self._ledger.reveal_evidence(
            reveal_id=reveal_id,
            prediction_id=prediction_id,
            target=truth["valid"],
            reveal_source="e10a-phase-gated-evaluator",
            reliability={"label_type": "synthetic_exact"},
        )
        self._pending_observation_id = None
        return reveal

    @property
    def is_complete(self) -> bool:
        return (
            self._index == len(self._query["observations"])
            and self._pending_observation_id is None
        )
