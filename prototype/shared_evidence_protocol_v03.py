"""Experimental v0.3 SQLite store layered on the stable v0.2 event format.

This first implementation slice adds atomic multi-event append, already-visible
TRAIN/SUPPORT ingestion, and typed E12 lifecycle-action records. It remains a
single-process reference store; it is not a distributed broker or a security
boundary between evaluator and learner processes.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from prototype.e12a6_lifecycle_contract import Action, ActionType, Candidate, CandidateState, Evidence, SplitRole, _TRANSITIONS
from prototype.shared_evidence_protocol import (
    EVENT_TYPES as V02_EVENT_TYPES,
    PROTOCOL_VERSION as V02_PROTOCOL_VERSION,
    EventReceipt,
    IdempotencyConflict,
    MissingReference,
    ProtocolError,
    SequenceConflict,
    SQLiteEvidenceStore,
    canonical_json,
    digest_payload,
)


CANDIDATE_DEFINITION_SCHEMA = "candidate_definition@1"


def candidate_definition_payload(candidate: Candidate) -> dict[str, Any]:
    """Serialize the semantic definition fields of an E12 Candidate.

    Identity, version, parent lineage, evidence references and lifecycle state
    are supplied by the enclosing structure/action events, not duplicated here.
    """
    return {
        "schema": CANDIDATE_DEFINITION_SCHEMA,
        "canonical_expression": candidate.canonical_expression,
        "proposer_family": candidate.proposer_family,
        "supporting_families": list(candidate.supporting_families),
        "input_types": list(candidate.input_types),
        "operator": candidate.operator,
        "conditions": list(candidate.conditions),
        "uncertainty": candidate.uncertainty,
        "complexity": candidate.complexity,
        "proposal_cost": candidate.proposal_cost,
    }


def _candidate_from_definition(
    *, candidate_id: str, version: int, definition: dict[str, Any],
    parent_refs: Sequence[str], evidence_ids: Sequence[str], state: CandidateState,
) -> Candidate:
    if definition.get("schema") != CANDIDATE_DEFINITION_SCHEMA:
        raise ProtocolError("unsupported candidate definition schema")
    required = {
        "canonical_expression", "proposer_family", "supporting_families",
        "input_types", "operator",
    }
    if not required.issubset(definition):
        raise ProtocolError(
            f"candidate definition missing fields: {sorted(required - definition.keys())}"
        )
    for field in ("supporting_families", "input_types", "conditions"):
        value = definition.get(field, [])
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            raise ProtocolError(f"candidate definition {field} must be an array of non-empty strings")
    for field in ("canonical_expression", "proposer_family", "operator"):
        if not isinstance(definition.get(field), str) or not definition[field].strip():
            raise ProtocolError(f"candidate definition {field} must be non-empty")
    try:
        return Candidate(
            candidate_id=candidate_id,
            version=version,
            canonical_expression=definition["canonical_expression"],
            proposer_family=definition["proposer_family"],
            supporting_families=tuple(definition["supporting_families"]),
            input_types=tuple(definition["input_types"]),
            operator=definition["operator"],
            conditions=tuple(definition.get("conditions", [])),
            uncertainty=definition.get("uncertainty", 1.0),
            complexity=definition.get("complexity", 1),
            proposal_cost=definition.get("proposal_cost", 0.0),
            parent_refs=tuple(parent_refs),
            evidence_ids=tuple(evidence_ids),
            state=state,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ProtocolError(f"invalid typed candidate definition: {exc}") from exc



EVIDENCE_DEFINITION_SCHEMA = "evidence_definition@1"


def evidence_definition_payload(evidence: Evidence) -> dict[str, Any]:
    """Serialize E12 evidence attributes not derivable from event causality."""
    return {
        "schema": EVIDENCE_DEFINITION_SCHEMA,
        "world_family": evidence.world_family,
        "outcome": evidence.outcome,
        "model_version": evidence.model_version,
        "measurement_cost": evidence.measurement_cost,
        "provenance": evidence.provenance,
    }


def _evidence_from_definition(
    *, evidence_id: str, episode_id: str, split_role: str, observation_id: str,
    definition: dict[str, Any], prediction_commit_step: int | None,
    label_visibility_step: int | None,
) -> Evidence:
    if definition.get("schema") != EVIDENCE_DEFINITION_SCHEMA:
        raise ProtocolError("unsupported evidence definition schema")
    required = {"world_family", "outcome", "model_version"}
    if not required.issubset(definition):
        raise ProtocolError(
            f"evidence definition missing fields: {sorted(required - definition.keys())}"
        )
    for field in ("world_family", "outcome", "model_version"):
        if not isinstance(definition[field], str) or not definition[field].strip():
            raise ProtocolError(f"evidence definition {field} must be non-empty")
    try:
        return Evidence(
            evidence_id=evidence_id, episode_id=episode_id,
            world_family=definition["world_family"],
            split_role=SplitRole(split_role), observation_id=observation_id,
            outcome=definition["outcome"], model_version=definition["model_version"],
            measurement_cost=definition.get("measurement_cost", 0.0),
            prediction_commit_step=prediction_commit_step,
            label_visibility_step=label_visibility_step,
            provenance=definition.get("provenance", ""),
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ProtocolError(f"invalid typed E12 evidence definition: {exc}") from exc


PROTOCOL_VERSION = "0.3"
EVENT_TYPES = V02_EVENT_TYPES | {"evidence_ingest", "lifecycle_action"}
SPLIT_ROLES = {role.value for role in SplitRole}
CHALLENGE_ROLES = {SplitRole.LOCKED_TEST.value, SplitRole.POST_DEPLOY.value}
SUPPORT_ROLES = {SplitRole.SUPPORT.value, SplitRole.TRAIN.value, SplitRole.GATE_DEV.value, SplitRole.GATE_FINAL.value}
ACTION_TYPES = {action.value for action in ActionType}
CANDIDATE_STATES = {state.value for state in CandidateState}


class ProjectionRecoveryRequired(ProtocolError):
    """A batch committed durably, but its derived projection could not be rebuilt."""

    def __init__(self, receipts: tuple[EventReceipt, ...], message: str):
        super().__init__(message)
        self.committed_receipts = receipts


class BatchConflict(ProtocolError):
    """A batch idempotency key was reused with different ordered content."""


def _fingerprint(spec: dict[str, Any]) -> str:
    return digest_payload({
        "event_type": spec["event_type"],
        "payload_schema": spec["payload_schema"],
        "payload": spec["payload"],
        "actor_role": spec["actor_role"],
        "causation_refs": spec["causation_refs"],
        "integrity_metadata": spec["integrity_metadata"],
    })



@dataclass(frozen=True)
class EpisodeProjection:
    """Deterministic, disposable read model rebuilt exclusively from durable events."""
    episode_id: str
    last_sequence: int
    observations: dict[str, dict[str, Any]]
    predictions: dict[str, dict[str, Any]]
    evidence: dict[str, dict[str, Any]]
    structures: dict[str, dict[str, Any]]
    candidates: dict[str, dict[str, Any]]
    candidate_objects: dict[str, Candidate]
    evidence_objects: dict[str, Evidence]
    action_objects: tuple[Action, ...]
    actions: tuple[dict[str, Any], ...]
    revisions: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id, "last_sequence": self.last_sequence,
            "observations": {k: self.observations[k] for k in sorted(self.observations)},
            "predictions": {k: self.predictions[k] for k in sorted(self.predictions)},
            "evidence": {k: self.evidence[k] for k in sorted(self.evidence)},
            "structures": {k: self.structures[k] for k in sorted(self.structures)},
            "candidates": {k: self.candidates[k] for k in sorted(self.candidates)},
            "evidence_objects": {k: _evidence_to_payload(self.evidence_objects[k]) for k in sorted(self.evidence_objects)},
            "action_objects": [_action_to_payload(a) for a in self.action_objects],
            "actions": list(self.actions),
            "revisions": {k: self.revisions[k] for k in sorted(self.revisions)},
        }

    @property
    def digest(self) -> str:
        return digest_payload(self.to_dict())



def _evidence_to_payload(item: Evidence) -> dict[str, Any]:
    return {
        "evidence_id": item.evidence_id, "episode_id": item.episode_id,
        "world_family": item.world_family, "split_role": item.split_role.value,
        "observation_id": item.observation_id, "outcome": item.outcome,
        "model_version": item.model_version, "measurement_cost": item.measurement_cost,
        "prediction_commit_step": item.prediction_commit_step,
        "label_visibility_step": item.label_visibility_step, "provenance": item.provenance,
    }


def _action_to_payload(item: Action) -> dict[str, Any]:
    return {
        "action_id": item.action_id, "action_type": item.action_type.value,
        "candidate_id": item.candidate_id, "candidate_version": item.candidate_version,
        "evidence_ids": list(item.evidence_ids), "cost": item.cost,
        "from_state": item.from_state.value if item.from_state else None,
        "to_state": item.to_state.value if item.to_state else None, "note": item.note,
    }


class SQLiteEvidenceStoreV03(SQLiteEvidenceStore):
    """v0.3 writer with v0.1/v0.2-compatible read/replay behavior."""

    def __init__(self, path):
        super().__init__(path)
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS batch_idempotency (
            episode_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            payload_digest TEXT NOT NULL,
            receipts_json TEXT NOT NULL,
            PRIMARY KEY (episode_id, idempotency_key)
        );
        """)

    def _event_by_id(self, episode_id: str, event_id: str):
        return self._db.execute(
            "SELECT * FROM events WHERE episode_id=? AND event_id=?",
            (episode_id, event_id),
        ).fetchone()

    def _event_by_payload_id(self, episode_id: str, event_type: str, field: str, value: str):
        return self._db.execute(
            "SELECT * FROM events WHERE episode_id=? AND event_type=? "
            "AND json_extract(payload_json, ?) = ?",
            (episode_id, event_type, "$." + field, value),
        ).fetchone()

    def _resolve_evidence_ref(self, episode_id: str, ref: Any):
        if isinstance(ref, dict):
            kind, value = ref.get("kind"), ref.get("id")
            if kind == "ingested":
                row = self._event_by_payload_id(episode_id, "evidence_ingest", "evidence_id", value)
            elif kind == "revealed":
                row = self._event_by_id(episode_id, value) if isinstance(value, str) else None
                if row is not None and row["event_type"] != "evidence_reveal":
                    row = None
            else:
                raise ProtocolError("typed evidence reference kind must be ingested or revealed")
            return row
        if not isinstance(ref, str) or not ref:
            raise ProtocolError("evidence reference must be a non-empty ID or typed reference")
        ingest = self._event_by_payload_id(episode_id, "evidence_ingest", "evidence_id", ref)
        reveal = self._event_by_id(episode_id, ref)
        if ingest is not None and reveal is not None:
            raise ProtocolError("ambiguous evidence ID; use a typed reference")
        if reveal is not None and reveal["event_type"] != "evidence_reveal":
            reveal = None
        return ingest or reveal

    def _resolve_evidence_id(self, episode_id: str, ref: Any) -> str | None:
        row = self._resolve_evidence_ref(episode_id, ref)
        if row is None:
            return None
        if row["event_type"] == "evidence_ingest":
            return json.loads(row["payload_json"])["evidence_id"]
        return row["event_id"]

    def _validate_semantics(self, episode_id: str, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == "evidence_ingest":
            required = {"evidence_id", "split_role", "outcome_ref", "source_provenance", "learner_track"}
            if not required.issubset(payload):
                raise ProtocolError(f"evidence_ingest missing fields: {sorted(required - payload.keys())}")
            if not isinstance(payload["evidence_id"], str) or not payload["evidence_id"].strip():
                raise ProtocolError("evidence_ingest evidence_id must be non-empty")
            if not isinstance(payload["split_role"], str) or payload["split_role"] not in {"train", "support"}:
                raise ProtocolError("evidence_ingest is restricted to already-visible train/support evidence")
            if not isinstance(payload["learner_track"], str) or not payload["learner_track"].strip():
                raise ProtocolError("evidence_ingest learner_track must be non-empty")
            if not isinstance(payload["source_provenance"], dict) or not payload["source_provenance"]:
                raise ProtocolError("evidence_ingest requires source provenance")
            if not isinstance(payload["outcome_ref"], str) or not payload["outcome_ref"].strip():
                raise ProtocolError("evidence_ingest outcome_ref must be a non-empty immutable reference")
            typed_definition = payload.get("evidence_definition")
            if typed_definition is not None:
                if not isinstance(typed_definition, dict):
                    raise ProtocolError("evidence_definition must be an object")
                _evidence_from_definition(
                    evidence_id=payload["evidence_id"], episode_id=episode_id,
                    split_role=payload["split_role"], observation_id="validation-observation",
                    definition=typed_definition, prediction_commit_step=None,
                    label_visibility_step=None,
                )
            if self._event_by_payload_id(episode_id, "evidence_ingest", "evidence_id", payload["evidence_id"]):
                raise ProtocolError("duplicate evidence_id in episode")
            observation_ref = payload.get("observation_ref")
            if not isinstance(observation_ref, str) or not observation_ref.strip():
                raise ProtocolError("evidence_ingest requires an observation_ref")
            observation = self._event_by_id(episode_id, observation_ref)
            if observation is None or observation["event_type"] != "observation":
                raise MissingReference("evidence_ingest observation_ref must reference a prior observation")
        elif event_type == "evidence_reveal":
            typed_definition = payload.get("evidence_definition")
            if typed_definition is not None:
                if not isinstance(typed_definition, dict):
                    raise ProtocolError("evidence_definition must be an object")
                if typed_definition.get("schema") != EVIDENCE_DEFINITION_SCHEMA:
                    raise ProtocolError("unsupported evidence definition schema")
                for field in ("world_family", "outcome"):
                    if not isinstance(typed_definition.get(field), str) or not typed_definition[field].strip():
                        raise ProtocolError(f"evidence definition {field} must be non-empty")
                cost = typed_definition.get("measurement_cost", 0.0)
                if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(float(cost)) or cost < 0:
                    raise ProtocolError("evidence definition measurement_cost must be finite and non-negative")
                if not isinstance(typed_definition.get("provenance", ""), str):
                    raise ProtocolError("evidence definition provenance must be a string")
        elif event_type == "lifecycle_action":
            required = {
                "action_id", "action_type", "candidate_id", "candidate_version",
                "from_state", "to_state", "evidence_refs", "cost", "note",
                "candidate_lineage_refs", "learner_track",
            }
            if not required.issubset(payload):
                raise ProtocolError(f"lifecycle_action missing fields: {sorted(required - payload.keys())}")
            if not isinstance(payload["action_id"], str) or not payload["action_id"].strip():
                raise ProtocolError("lifecycle_action action_id must be non-empty")
            if payload["action_type"] not in ACTION_TYPES:
                raise ProtocolError("unknown E12-A6 ActionType wire value")
            from_state, to_state = payload["from_state"], payload["to_state"]
            if (from_state is None) != (to_state is None):
                raise ProtocolError("from_state and to_state must both be null or both be present")
            if from_state is not None and (from_state not in CANDIDATE_STATES or to_state not in CANDIDATE_STATES):
                raise ProtocolError("unknown E12-A6 CandidateState wire value")
            candidate_id, candidate_version = payload["candidate_id"], payload["candidate_version"]
            if (candidate_id is None) != (candidate_version is None):
                raise ProtocolError("candidate_id and candidate_version must be paired")
            if candidate_id is not None and (not isinstance(candidate_id, str) or not candidate_id.strip()):
                raise ProtocolError("candidate_id must be non-empty")
            if candidate_version is not None and (
                isinstance(candidate_version, bool) or not isinstance(candidate_version, int) or candidate_version < 1
            ):
                raise ProtocolError("candidate_version must be a positive integer")
            if not isinstance(payload["learner_track"], str) or not payload["learner_track"].strip():
                raise ProtocolError("lifecycle_action learner_track must be non-empty")
            if not isinstance(payload["evidence_refs"], list) or not isinstance(payload["candidate_lineage_refs"], list):
                raise ProtocolError("lifecycle_action evidence_refs and candidate_lineage_refs must be arrays")
            if len({canonical_json(x) for x in payload["evidence_refs"]}) != len(payload["evidence_refs"]):
                raise ProtocolError("lifecycle_action evidence_refs must be unique")
            if isinstance(payload["cost"], bool) or not isinstance(payload["cost"], (int, float)) or not math.isfinite(float(payload["cost"])) or payload["cost"] < 0:
                raise ProtocolError("lifecycle_action cost must be finite and non-negative")
            if not isinstance(payload["note"], str):
                raise ProtocolError("lifecycle_action note must be a string")
            for ref in payload["evidence_refs"]:
                row = self._resolve_evidence_ref(episode_id, ref)
                if row is None:
                    raise MissingReference(f"lifecycle_action references unavailable evidence: {ref}")
                ref_track = json.loads(row["payload_json"]).get("learner_track")
                if ref_track and ref_track != payload["learner_track"]:
                    raise ProtocolError("lifecycle_action cannot cite evidence from another learner_track")
            # Reuse E12-A6's canonical transition table; do not fork its legal
            # transition semantics in the protocol layer.
            action = ActionType(payload["action_type"])
            allowed = _TRANSITIONS.get(action, set())
            if allowed:
                if from_state is None:
                    raise ProtocolError("this E12-A6 action requires an explicit state transition")
                transition = (CandidateState(from_state), CandidateState(to_state))
                if transition not in allowed:
                    raise ProtocolError("transition is not permitted by the E12-A6 contract")
            elif from_state is not None:
                raise ProtocolError("non-transition E12-A6 action must not change candidate state")
            if candidate_id is None and from_state is not None:
                raise ProtocolError("state transitions require a candidate reference")
            if candidate_id is not None:
                candidate_version_id = f"{candidate_id}@{candidate_version}"
                candidate_row = self._event_by_payload_id(
                    episode_id, "structure_version", "version_id", candidate_version_id
                )
                if candidate_row is None:
                    raise MissingReference(f"lifecycle_action references unknown candidate version: {candidate_version_id}")
                candidate_structure = json.loads(candidate_row["payload_json"])
                if candidate_structure.get("structure_id") != candidate_id:
                    raise ProtocolError("lifecycle_action candidate_id does not match structure_version structure_id")
                if payload["candidate_lineage_refs"] != candidate_structure.get("parent_version_ids", []):
                    raise ProtocolError("lifecycle_action candidate_lineage_refs must match its structure_version parent lineage")
            for lineage_ref in payload["candidate_lineage_refs"]:
                if not isinstance(lineage_ref, str) or not lineage_ref:
                    raise ProtocolError("candidate_lineage_refs must contain non-empty version IDs")
                if self._event_by_payload_id(episode_id, "structure_version", "version_id", lineage_ref) is None:
                    raise MissingReference(f"unknown candidate lineage version: {lineage_ref}")
            if candidate_id is not None and from_state is not None:
                latest = self._db.execute(
                    "SELECT payload_json FROM events WHERE episode_id=? AND event_type='lifecycle_action' "
                    "AND json_extract(payload_json, '$.candidate_id')=? "
                    "AND json_extract(payload_json, '$.candidate_version')=? "
                    "ORDER BY sequence_no DESC LIMIT 1",
                    (episode_id, candidate_id, candidate_version),
                ).fetchone()
                current_state = "observed" if latest is None else json.loads(latest["payload_json"])["to_state"]
                if current_state != from_state:
                    raise ProtocolError(f"stale lifecycle transition: current={current_state}, from={from_state}")
            duplicate = self._db.execute(
                "SELECT 1 FROM events WHERE episode_id=? AND event_type='lifecycle_action' "
                "AND json_extract(payload_json, '$.action_id')=?",
                (episode_id, payload["action_id"]),
            ).fetchone()
            if duplicate:
                raise ProtocolError("duplicate lifecycle action_id")
            required_role = {
                "train_supported": {"train"},
                "gate_validated": {"gate_final"},
                "challenged": CHALLENGE_ROLES,
            }.get(to_state)
            if required_role:
                roles = set()
                for ref in payload["evidence_refs"]:
                    row = self._resolve_evidence_ref(episode_id, ref)
                    evidence_payload = json.loads(row["payload_json"])
                    if row["event_type"] == "evidence_ingest":
                        roles.add(evidence_payload["split_role"])
                    else:
                        split_role = evidence_payload.get("split_role")
                        if not isinstance(split_role, str):
                            raise ProtocolError("revealed evidence used for lifecycle transitions must declare split_role")
                        roles.add(split_role)
                if not roles.intersection(required_role):
                    raise ProtocolError(f"{payload['to_state']} requires evidence role in {sorted(required_role)}")
        elif event_type == "structure_version":
            required = {"structure_id", "version_id", "kind", "definition", "parent_version_ids", "support_evidence_ids"}
            if not required.issubset(payload):
                raise ProtocolError(f"structure_version missing fields: {sorted(required - payload.keys())}")
            for parent_id in payload["parent_version_ids"]:
                if self._event_by_payload_id(episode_id, "structure_version", "version_id", parent_id) is None:
                    raise MissingReference(f"unknown parent structure version: {parent_id}")
            for evidence_ref in payload["support_evidence_ids"]:
                if self._resolve_evidence_ref(episode_id, evidence_ref) is None:
                    raise MissingReference(f"unknown support evidence reference: {evidence_ref}")
            if payload["kind"] == "candidate":
                version_id = payload["version_id"]
                structure_id = payload["structure_id"]
                try:
                    version = int(version_id.rsplit("@", 1)[1])
                except (IndexError, ValueError) as exc:
                    raise ProtocolError("candidate version_id must end in @<positive integer>") from exc
                if version < 1 or version_id != f"{structure_id}@{version}":
                    raise ProtocolError("candidate version_id must match structure_id@version")
                definition = payload["definition"]
                if isinstance(definition, dict) and definition.get("schema") == CANDIDATE_DEFINITION_SCHEMA:
                    resolved_support = [
                        self._resolve_evidence_id(episode_id, ref)
                        for ref in payload["support_evidence_ids"]
                    ]
                    _candidate_from_definition(
                        candidate_id=structure_id, version=version, definition=definition,
                        parent_refs=payload["parent_version_ids"], evidence_ids=resolved_support,
                        state=CandidateState.OBSERVED,
                    )
        else:
            super()._validate_semantics(episode_id, event_type, payload)

    def append_events(
        self,
        *,
        episode_id: str,
        events: Sequence[dict[str, Any]],
        idempotency_key: str,
        expected_sequence: int | None = None,
    ) -> tuple[EventReceipt, ...]:
        if not isinstance(episode_id, str) or not episode_id.strip():
            raise ProtocolError("episode_id must be non-empty")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ProtocolError("batch idempotency_key must be non-empty")
        if not isinstance(events, (list, tuple)) or not events:
            raise ProtocolError("events must be a non-empty ordered sequence")
        normalized = []
        event_ids = set()
        for index, raw in enumerate(events):
            if not isinstance(raw, dict):
                raise ProtocolError("each event spec must be an object")
            required = {"event_id", "event_type", "payload"}
            if not required.issubset(raw):
                raise ProtocolError(f"event spec missing fields: {sorted(required - raw.keys())}")
            event_id, event_type, payload = raw["event_id"], raw["event_type"], raw["payload"]
            if not all(isinstance(v, str) and v.strip() for v in (event_id, event_type)):
                raise ProtocolError("event_id and event_type must be non-empty")
            if event_id in event_ids:
                raise ProtocolError("duplicate event_id inside batch")
            event_ids.add(event_id)
            if event_type not in EVENT_TYPES:
                raise ProtocolError(f"unsupported v0.3 event_type: {event_type}")
            if not isinstance(payload, dict):
                raise ProtocolError("event payload must be an object")
            schema = raw.get("payload_schema") or f"{event_type}@1"
            if schema != f"{event_type}@1":
                raise ProtocolError(f"unsupported payload schema: {schema}")
            actor = raw.get("actor_role", "runner")
            if not isinstance(actor, str) or not actor.strip():
                raise ProtocolError("actor_role must be non-empty")
            causation = list(raw.get("causation_refs", ()))
            integrity = raw.get("integrity_metadata") or {}
            if not isinstance(integrity, dict):
                raise ProtocolError("integrity_metadata must be an object")
            spec = {
                "event_id": event_id, "event_type": event_type, "payload": payload,
                "payload_schema": schema, "actor_role": actor,
                "causation_refs": causation, "integrity_metadata": integrity,
                "idempotency_key": raw.get("idempotency_key", f"{idempotency_key}:{index}"),
            }
            if not isinstance(spec["idempotency_key"], str) or not spec["idempotency_key"].strip():
                raise ProtocolError("event idempotency_key must be non-empty")
            spec["fingerprint"] = _fingerprint(spec)
            normalized.append(spec)
        batch_digest = digest_payload([
            {
                **({} if len(normalized) == 1 and idempotency_key.startswith("single:") else {"event_id": spec["event_id"]}),
                **{k: spec[k] for k in ("event_type", "payload", "payload_schema",
                                        "actor_role", "causation_refs", "integrity_metadata",
                                        "idempotency_key")},
            }
            for spec in normalized
        ])
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                prior = self._db.execute(
                    "SELECT payload_digest, receipts_json FROM batch_idempotency "
                    "WHERE episode_id=? AND idempotency_key=?",
                    (episode_id, idempotency_key),
                ).fetchone()
                if prior:
                    if prior["payload_digest"] != batch_digest:
                        raise BatchConflict("batch idempotency key reused with different ordered content")
                    old = json.loads(prior["receipts_json"])
                    self._db.execute("COMMIT")
                    return tuple(EventReceipt(
                        episode_id, item["event_id"], item["sequence_no"],
                        item["payload_digest"], True,
                    ) for item in old)
                current = self._db.execute(
                    "SELECT COALESCE(MAX(sequence_no), 0) FROM events WHERE episode_id=?",
                    (episode_id,),
                ).fetchone()[0]
                if expected_sequence is not None and expected_sequence != current:
                    raise SequenceConflict(f"expected sequence {expected_sequence}, current sequence is {current}")
                receipts = []
                for offset, spec in enumerate(normalized, start=1):
                    existing = self._db.execute(
                        "SELECT payload_digest, event_id, sequence_no FROM idempotency "
                        "WHERE episode_id=? AND idempotency_key=?",
                        (episode_id, spec["idempotency_key"]),
                    ).fetchone()
                    if existing:
                        if existing["payload_digest"] != spec["fingerprint"]:
                            raise IdempotencyConflict("event idempotency key reused with different content")
                        raise ProtocolError("partial event-level retry is not accepted; retry the whole batch key")
                    self._validate_semantics(episode_id, spec["event_type"], spec["payload"])
                    sequence = current + offset
                    created_at = datetime.now(timezone.utc).isoformat()
                    payload_json = canonical_json(spec["payload"])
                    causation_json = canonical_json(spec["causation_refs"])
                    integrity_json = canonical_json(spec["integrity_metadata"])
                    self._db.execute(
                        "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (episode_id, sequence, spec["event_id"], spec["event_type"],
                         PROTOCOL_VERSION, payload_json, spec["fingerprint"], spec["actor_role"],
                         causation_json, spec["payload_schema"], integrity_json, created_at),
                    )
                    self._db.execute(
                        "INSERT INTO idempotency VALUES (?, ?, ?, ?, ?)",
                        (episode_id, spec["idempotency_key"], spec["fingerprint"],
                         spec["event_id"], sequence),
                    )
                    receipts.append({
                        "event_id": spec["event_id"], "sequence_no": sequence,
                        "payload_digest": spec["fingerprint"],
                    })
                self._db.execute(
                    "INSERT INTO batch_idempotency VALUES (?, ?, ?, ?)",
                    (episode_id, idempotency_key, batch_digest, canonical_json(receipts)),
                )
                self._db.execute("COMMIT")
                return tuple(EventReceipt(
                    episode_id, item["event_id"], item["sequence_no"],
                    item["payload_digest"], False,
                ) for item in receipts)
            except Exception:
                self._db.execute("ROLLBACK")
                raise


    def append_events_and_project(
        self, *, episode_id: str, events: Sequence[dict[str, Any]],
        idempotency_key: str, expected_sequence: int | None = None,
    ) -> tuple[tuple[EventReceipt, ...], EpisodeProjection]:
        """Commit first, then derive a projection; never pretend post-commit failure rolled back."""
        receipts = self.append_events(
            episode_id=episode_id, events=events, idempotency_key=idempotency_key,
            expected_sequence=expected_sequence,
        )
        try:
            projection = self.replay_projection(episode_id)
        except Exception as exc:
            raise ProjectionRecoveryRequired(
                receipts,
                "event batch is committed; projection rebuild failed and must be retried from durable history",
            ) from exc
        return receipts, projection

    def replay_projection(self, episode_id: str) -> EpisodeProjection:
        """Rebuild a read model from raw durable rows; never trusts cached state."""
        with self._lock:
            rows = self._db.execute(
                "SELECT episode_id, sequence_no, event_id, event_type, protocol_version, payload_json, "
                "payload_digest, actor_role, causation_refs_json, payload_schema, integrity_metadata_json "
                "FROM events WHERE episode_id=? ORDER BY sequence_no", (episode_id,),
            ).fetchall()
        observations, predictions, evidence = {}, {}, {}
        evidence_objects = {}
        structures, candidates, revisions = {}, {}, {}
        actions, action_ids, event_ids = [], set(), set()
        previous_sequence = 0

        def resolve_evidence(ref):
            if isinstance(ref, dict):
                return evidence.get(f"{ref.get('kind')}:{ref.get('id')}")
            if isinstance(ref, str):
                return evidence.get(f"revealed:{ref}") or evidence.get(f"ingested:{ref}")
            return None

        for row in rows:
            sequence, event_id = int(row["sequence_no"]), row["event_id"]
            if sequence != previous_sequence + 1:
                raise ProtocolError(f"non-contiguous replay sequence: expected {previous_sequence + 1}, got {sequence}")
            previous_sequence = sequence
            if event_id in event_ids:
                raise ProtocolError(f"duplicate event_id during replay: {event_id}")
            event_ids.add(event_id)
            payload = json.loads(row["payload_json"])
            fingerprint = _fingerprint({
                "event_type": row["event_type"], "payload_schema": row["payload_schema"],
                "payload": payload, "actor_role": row["actor_role"],
                "causation_refs": json.loads(row["causation_refs_json"]),
                "integrity_metadata": json.loads(row["integrity_metadata_json"]),
            })
            if fingerprint != row["payload_digest"]:
                raise ProtocolError(f"event digest mismatch during replay: {event_id}")
            event_type = row["event_type"]

            if event_type == "observation":
                oid = payload.get("observation_id")
                if not isinstance(oid, str) or not oid or oid in observations:
                    raise ProtocolError(f"invalid or duplicate observation during replay: {event_id}")
                observations[oid] = {"event_id": event_id, "sequence_no": sequence}
            elif event_type == "prediction_commit":
                pid, oid = payload.get("prediction_id"), payload.get("observation_id")
                if not isinstance(pid, str) or pid in predictions or oid not in observations:
                    raise ProtocolError(f"invalid prediction commit during replay: {event_id}")
                predictions[pid] = {
                    "event_id": event_id, "sequence_no": sequence, "observation_id": oid,
                    "learner_track": payload.get("learner_track", "legacy"),
                    "decision_status": payload.get("decision_status"),
                }
            elif event_type == "evidence_reveal":
                pid = payload.get("prediction_id")
                prediction = predictions.get(pid)
                if prediction is None:
                    raise MissingReference(f"replay reveal has no prior prediction: {event_id}")
                track = payload.get("learner_track", "legacy")
                if track != prediction["learner_track"]:
                    raise ProtocolError(f"replay reveal crosses learner tracks: {event_id}")
                evidence[f"revealed:{event_id}"] = {
                    "evidence_id": event_id, "kind": "revealed", "event_id": event_id,
                    "sequence_no": sequence, "split_role": payload.get("split_role"),
                    "learner_track": track, "prediction_id": pid,
                    "observation_id": prediction["observation_id"],
                    "outcome_ref": digest_payload(payload.get("target_or_feedback")),
                }
                definition = payload.get("evidence_definition")
                if definition is not None:
                    commit_step = prediction["sequence_no"]
                    evidence_objects[event_id] = _evidence_from_definition(
                        evidence_id=event_id, episode_id=episode_id,
                        split_role=payload["split_role"],
                        observation_id=prediction["observation_id"],
                        definition=definition, prediction_commit_step=commit_step,
                        label_visibility_step=sequence,
                    )
                    if definition["outcome"] != canonical_json(payload.get("target_or_feedback")) and definition["outcome"] != payload.get("target_or_feedback"):
                        raise ProtocolError("typed evidence outcome must match the revealed target/feedback")
            elif event_type == "evidence_ingest":
                eid, observation_ref = payload.get("evidence_id"), payload.get("observation_ref")
                observation = next((v for v in observations.values() if v["event_id"] == observation_ref), None)
                key = f"ingested:{eid}"
                if not isinstance(eid, str) or not eid or observation is None or key in evidence:
                    raise MissingReference(f"replay ingest lacks identity/prior observation or duplicates evidence: {event_id}")
                evidence[key] = {
                    "evidence_id": eid, "kind": "ingested", "event_id": event_id,
                    "sequence_no": sequence, "split_role": payload.get("split_role"),
                    "learner_track": payload.get("learner_track"),
                    "observation_ref": observation_ref, "outcome_ref": payload.get("outcome_ref"),
                    "source_provenance": payload.get("source_provenance"),
                }
                definition = payload.get("evidence_definition")
                if definition is not None:
                    evidence_objects[eid] = _evidence_from_definition(
                        evidence_id=eid, episode_id=episode_id,
                        split_role=payload["split_role"], observation_id=observation["observation_id"],
                        definition=definition, prediction_commit_step=None,
                        label_visibility_step=None,
                    )
            elif event_type == "structure_version":
                vid = payload.get("version_id")
                if not isinstance(vid, str) or not vid or vid in structures:
                    raise ProtocolError(f"invalid or duplicate structure version during replay: {event_id}")
                parents = payload.get("parent_version_ids", [])
                if not isinstance(parents, list) or any(parent not in structures for parent in parents):
                    raise MissingReference(f"structure version has missing prior parent: {event_id}")
                support_refs = payload.get("support_evidence_ids", [])
                if not isinstance(support_refs, list):
                    raise ProtocolError(f"structure support evidence must be an array: {event_id}")
                support_ids = []
                for ref in support_refs:
                    item = resolve_evidence(ref)
                    if item is None:
                        raise MissingReference(f"structure version has missing prior support evidence: {event_id}")
                    support_ids.append(item["evidence_id"])
                structure = {
                    "event_id": event_id, "sequence_no": sequence,
                    "structure_id": payload.get("structure_id"), "version_id": vid,
                    "kind": payload.get("kind"), "definition": payload.get("definition"),
                    "parent_version_ids": list(parents), "support_evidence_ids": support_ids,
                }
                structures[vid] = structure
                if payload.get("kind") == "candidate":
                    candidate_id = payload.get("structure_id")
                    candidate_version = self._candidate_version_number(vid)
                    candidates[vid] = {
                        **structure, "candidate_id": candidate_id,
                        "candidate_version": candidate_version,
                        "state": CandidateState.OBSERVED.value,
                        "definition_schema": (
                            payload["definition"].get("schema")
                            if isinstance(payload.get("definition"), dict) else None
                        ),
                    }
            elif event_type == "lifecycle_action":
                aid, track = payload.get("action_id"), payload.get("learner_track")
                action_key = (track, aid)
                if not isinstance(aid, str) or not aid or action_key in action_ids:
                    raise ProtocolError(f"invalid or duplicate lifecycle action during replay: {event_id}")
                action_ids.add(action_key)
                action_type = ActionType(payload["action_type"])
                cid, version = payload.get("candidate_id"), payload.get("candidate_version")
                candidate_key = f"{cid}@{version}" if cid is not None else None
                if candidate_key is not None and candidate_key not in candidates:
                    raise MissingReference(f"lifecycle action references missing candidate: {candidate_key}")
                if candidate_key is not None:
                    candidate = candidates[candidate_key]
                    if candidate.get("candidate_id") != cid:
                        raise ProtocolError("replayed lifecycle candidate_id does not match structure identity")
                    if payload.get("candidate_lineage_refs", []) != candidate.get("parent_version_ids", []):
                        raise ProtocolError("replayed candidate lineage differs from its structure version")
                resolved = []
                for ref in payload.get("evidence_refs", []):
                    item = resolve_evidence(ref)
                    if item is None:
                        raise MissingReference(f"lifecycle action references missing evidence: {ref}")
                    if item.get("learner_track") and item["learner_track"] != track:
                        raise ProtocolError("lifecycle action crosses learner tracks during replay")
                    resolved.append(item)
                from_state, to_state = payload.get("from_state"), payload.get("to_state")
                allowed = _TRANSITIONS.get(action_type, set())
                if allowed:
                    if candidate_key is None or (CandidateState(from_state), CandidateState(to_state)) not in allowed:
                        raise ProtocolError(f"invalid E12 transition during replay: {aid}")
                    current = candidates[candidate_key]["state"]
                    if current != from_state:
                        raise ProtocolError(f"stale E12 transition during replay: {aid}, current={current}, from={from_state}")
                    required_role = {
                        CandidateState.TRAIN_SUPPORTED.value: {SplitRole.TRAIN.value},
                        CandidateState.GATE_VALIDATED.value: {SplitRole.GATE_FINAL.value},
                        CandidateState.CHALLENGED.value: CHALLENGE_ROLES,
                    }.get(to_state)
                    if required_role and not any(item.get("split_role") in required_role for item in resolved):
                        raise ProtocolError(f"E12 transition lacks required evidence role: {aid}")
                    candidates[candidate_key]["state"] = to_state
                elif from_state is not None or to_state is not None:
                    raise ProtocolError(f"non-transition E12 action changes state: {aid}")
                for lineage_ref in payload.get("candidate_lineage_refs", []):
                    if lineage_ref not in structures:
                        raise MissingReference(f"lifecycle action has missing lineage: {lineage_ref}")
                actions.append({
                    "event_id": event_id, "sequence_no": sequence, "action_id": aid,
                    "action_type": action_type.value, "candidate_key": candidate_key,
                    "learner_track": track, "from_state": from_state, "to_state": to_state,
                    "evidence_ids": [item["evidence_id"] for item in resolved],
                    "candidate_lineage_refs": list(payload.get("candidate_lineage_refs", [])),
                    "cost": payload.get("cost"), "note": payload.get("note", ""),
                })
            elif event_type == "revision":
                rid = payload.get("revision_id")
                if not isinstance(rid, str) or not rid or rid in revisions:
                    raise ProtocolError(f"invalid or duplicate revision during replay: {event_id}")
                triggers = payload.get("trigger_evidence_ids", [])
                for trigger in triggers:
                    item = evidence.get(f"revealed:{trigger}")
                    if item is None or item.get("split_role") not in CHALLENGE_ROLES:
                        raise ProtocolError(f"revision trigger is not locked/post-deploy evidence: {trigger}")
                before, after = payload.get("before_version_ids", []), payload.get("after_version_ids", [])
                if any(vid not in structures for vid in list(before) + list(after)):
                    raise MissingReference(f"revision references missing structure version: {rid}")
                revisions[rid] = {
                    "event_id": event_id, "sequence_no": sequence, "operation": payload.get("operation"),
                    "trigger_evidence_ids": list(triggers), "before_version_ids": list(before),
                    "after_version_ids": list(after),
                }

        candidate_objects = {}
        for version_id, item in candidates.items():
            definition = item.get("definition")
            if isinstance(definition, dict) and definition.get("schema") == CANDIDATE_DEFINITION_SCHEMA:
                candidate_objects[version_id] = _candidate_from_definition(
                    candidate_id=item["candidate_id"],
                    version=item["candidate_version"],
                    definition=definition,
                    parent_refs=item["parent_version_ids"],
                    evidence_ids=item["support_evidence_ids"],
                    state=CandidateState(item["state"]),
                )

        action_objects = tuple(
            Action(
                action_id=item["action_id"], action_type=ActionType(item["action_type"]),
                candidate_id=(item["candidate_key"].rsplit("@", 1)[0] if item["candidate_key"] else None),
                candidate_version=(int(item["candidate_key"].rsplit("@", 1)[1]) if item["candidate_key"] else None),
                evidence_ids=tuple(item["evidence_ids"]), cost=item["cost"],
                from_state=CandidateState(item["from_state"]) if item["from_state"] else None,
                to_state=CandidateState(item["to_state"]) if item["to_state"] else None,
                note=item["note"],
            )
            for item in actions
        )
        return EpisodeProjection(
            episode_id=episode_id, last_sequence=previous_sequence,
            observations=observations, predictions=predictions, evidence=evidence,
            structures=structures, candidates=candidates, candidate_objects=candidate_objects,
            evidence_objects=evidence_objects, action_objects=action_objects,
            actions=tuple(actions), revisions=revisions,
        )

    @staticmethod
    def _candidate_version_number(version_id: str) -> int:
        try:
            value = int(version_id.rsplit("@", 1)[1])
        except (IndexError, ValueError):
            raise ProtocolError(f"candidate version_id must end in @<positive integer>: {version_id}")
        if value < 1:
            raise ProtocolError(f"candidate version must be positive: {version_id}")
        return value


    def append_event(
        self, *, episode_id: str, event_id: str, event_type: str, payload: dict[str, Any],
        idempotency_key: str, expected_sequence: int | None = None, actor_role: str = "runner",
        causation_refs: Iterable[str] = (), payload_schema: str | None = None,
        integrity_metadata: dict[str, Any] | None = None,
    ) -> EventReceipt:
        spec = {
            "event_id": event_id, "event_type": event_type, "payload": payload,
            "idempotency_key": idempotency_key, "actor_role": actor_role,
            "causation_refs": list(causation_refs),
            "payload_schema": payload_schema or f"{event_type}@1",
            "integrity_metadata": integrity_metadata or {},
        }
        return self.append_events(
            episode_id=episode_id, events=[spec],
            idempotency_key=f"single:{idempotency_key}",
            expected_sequence=expected_sequence,
        )[0]
