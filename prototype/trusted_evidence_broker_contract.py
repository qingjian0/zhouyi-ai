"""Versioned, allowlisted DTOs for the future trusted evidence broker.

These serializers are defense-in-depth only. Importing or calling them does not
authenticate a principal, protect a SQLite file, or create a process boundary.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


BROKER_CONTRACT_VERSION = "0.1"
LEARNER_COLLECTIONS = (
    "observations",
    "predictions",
    "evidence",
    "structures",
    "candidates",
    "actions",
    "released_challenges",
    "track_candidate_objects",
    "track_action_objects",
)
# Metadata that belongs to the broker/event log, not to a learner DTO.
DROP_INTERNAL_KEYS = {
    "actor_role",
    "event_id",
    "sequence_no",
    "last_sequence",
    "split_role",
    "evaluation_role",
}
FORBIDDEN_KEYS = {
    "target",
    "label",
    "expected",
    "expected_answer",
    "source_evaluation_id",
    "source_prediction_id",
    "policy_digest",
    "allowed_evaluation_roles",
    "evaluator_provenance",
}


class BrokerContractError(ValueError):
    """A broker DTO cannot be serialized without violating its allowlist."""


def _public_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 32:
        raise BrokerContractError("learner DTO exceeds maximum nesting depth")
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_public_value(item, depth=depth + 1) for item in value]
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise BrokerContractError("learner DTO object keys must be strings")
            if key in DROP_INTERNAL_KEYS:
                # Never export raw event identity or global ordering metadata.
                continue
            if key in FORBIDDEN_KEYS:
                # Fail closed: a caller must not accidentally serialize an
                # evaluator-bearing projection by merely forgetting a filter.
                raise BrokerContractError(f"private field is forbidden in learner DTO: {key}")
            result[key] = _public_value(item, depth=depth + 1)
        return result
    raise BrokerContractError(f"unsupported learner DTO value type: {type(value).__name__}")


@dataclass(frozen=True)
class ChallengeSignalDTO:
    challenge_id: str
    observation_id: str
    challenge_kind: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ChallengeSignalDTO":
        required = {"challenge_id", "observation_id", "challenge_kind"}
        if not isinstance(payload, Mapping) or set(payload) != required:
            raise BrokerContractError("challenge signal must contain exactly three allowlisted fields")
        values = [payload[key] for key in ("challenge_id", "observation_id", "challenge_kind")]
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise BrokerContractError("challenge signal fields must be non-empty strings")
        return cls(*values)


@dataclass(frozen=True)
class LearnerSnapshotDTO:
    contract_version: str
    episode_id: str
    learner_track: str
    cursor: str
    observations: dict[str, Any]
    predictions: dict[str, Any]
    evidence: dict[str, Any]
    structures: dict[str, Any]
    candidates: dict[str, Any]
    actions: list[Any]
    released_challenges: list[dict[str, str]]
    track_candidate_objects: dict[str, Any]
    track_action_objects: dict[str, Any]

    @classmethod
    def from_projection(
        cls, projection: Mapping[str, Any], *, opaque_cursor: str
    ) -> "LearnerSnapshotDTO":
        if not isinstance(projection, Mapping):
            raise BrokerContractError("learner projection must be a mapping")
        episode_id = projection.get("episode_id")
        learner_track = projection.get("learner_track")
        if not isinstance(episode_id, str) or not episode_id.strip():
            raise BrokerContractError("projection episode_id must be non-empty")
        if not isinstance(learner_track, str) or not learner_track.strip():
            raise BrokerContractError("projection learner_track must be non-empty")
        if not isinstance(opaque_cursor, str) or not opaque_cursor.strip():
            raise BrokerContractError("opaque cursor must be non-empty")
        # Never forward the projection's global last_sequence as a client cursor.
        collections = {}
        for name in LEARNER_COLLECTIONS:
            value = projection.get(name, {} if name != "actions" and name != "released_challenges" else [])
            if name in {"actions", "released_challenges"} and not isinstance(value, (list, tuple)):
                raise BrokerContractError(f"{name} must be an array")
            if name not in {"actions", "released_challenges"} and not isinstance(value, Mapping):
                raise BrokerContractError(f"{name} must be an object")
            collections[name] = _public_value(value)
        challenges = [
            asdict(ChallengeSignalDTO.from_mapping(item))
            for item in collections["released_challenges"]
        ]
        return cls(
            contract_version=BROKER_CONTRACT_VERSION,
            episode_id=episode_id,
            learner_track=learner_track,
            cursor=opaque_cursor,
            observations=collections["observations"],
            predictions=collections["predictions"],
            evidence=collections["evidence"],
            structures=collections["structures"],
            candidates=collections["candidates"],
            actions=collections["actions"],
            released_challenges=challenges,
            track_candidate_objects=collections["track_candidate_objects"],
            track_action_objects=collections["track_action_objects"],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
