"""Resolve durable E09 reveal events into safe E12-A6 evidence references.

The resolver verifies the E09 event chain and split context. It never copies
raw target_or_feedback into the E12-A6 Evidence DTO.
"""
from __future__ import annotations

import math
from typing import Any

from prototype.e12a6_lifecycle_contract import Evidence, SplitRole
from prototype.e12a6_zpcm_persistence import LifecycleEventReceipt, PersistentLifecycleLedger
from prototype.shared_evidence_protocol import STRICT_PROTOCOL_VERSION, SQLiteEvidenceStore, digest_payload


class E09EvidenceBindingError(ValueError):
    """An E09 evidence reference is missing, mismatched, or not verifiable."""


_SPLIT_ROLE = {
    "SUPPORT": SplitRole.TRAIN,
    "GATE_DEV": SplitRole.GATE_DEV,
    "GATE_FINAL": SplitRole.GATE_FINAL,
    "LOCKED_TEST": SplitRole.LOCKED_TEST,
}


def _verify_event_envelope(event: dict[str, Any]) -> None:
    """Recompute the E09 immutable event-envelope fingerprint."""
    required = ("event_type", "protocol_version", "payload_schema", "payload",
                "actor_role", "causation_refs", "integrity_metadata")
    if any(key not in event for key in required):
        raise E09EvidenceBindingError("E09 event envelope is incomplete")
    expected = digest_payload({
        "event_type": event["event_type"],
        "protocol_version": event["protocol_version"],
        "payload_schema": event["payload_schema"],
        "payload": event["payload"],
        "actor_role": event["actor_role"],
        "causation_refs": event["causation_refs"],
        "integrity_metadata": event["integrity_metadata"],
    })
    if expected != event.get("payload_digest"):
        raise E09EvidenceBindingError("E09 event envelope digest verification failed")


def resolve_e09_reveal(
    store: SQLiteEvidenceStore,
    *,
    episode_id: str,
    evidence_ref: str,
    scope: str,
    learner_track: str,
    world_family: str,
    measurement_cost: float = 0.0,
) -> Evidence:
    """Verify an E09 reveal→commit→observation chain and return a redacted DTO.

    SUPPORT maps to E12-A6 TRAIN because this E09 split is the learner-visible
    support/training partition. Gate and locked-test roles remain isolated.
    world_family is mandatory caller-supplied context; it is never inferred
    from the E09 scope string.
    """
    for name, value in (("episode_id", episode_id), ("evidence_ref", evidence_ref),
                        ("scope", scope), ("learner_track", learner_track),
                        ("world_family", world_family)):
        if not isinstance(value, str) or not value.strip():
            raise E09EvidenceBindingError(f"{name} must be a non-empty string")
    if isinstance(measurement_cost, bool) or not isinstance(measurement_cost, (int, float)):
        raise E09EvidenceBindingError("measurement_cost must be numeric")
    if not math.isfinite(float(measurement_cost)) or measurement_cost < 0:
        raise E09EvidenceBindingError("measurement_cost must be finite and non-negative")

    try:
        events = store.replay_episode(episode_id)
    except Exception as exc:
        raise E09EvidenceBindingError(f"cannot replay E09 episode: {exc}") from exc

    reveals = [e for e in events if e.get("event_id") == evidence_ref]
    if len(reveals) != 1:
        raise E09EvidenceBindingError("evidence_ref must identify exactly one event in the episode")
    reveal = reveals[0]
    if reveal.get("event_type") != "evidence_reveal":
        raise E09EvidenceBindingError("evidence_ref is not an E09 evidence_reveal event")
    _verify_event_envelope(reveal)
    if reveal.get("protocol_version") != STRICT_PROTOCOL_VERSION:
        raise E09EvidenceBindingError("only strict E09 v0.3 reveal events are accepted")
    if reveal.get("actor_role") != "evaluator":
        raise E09EvidenceBindingError("evidence reveal must be committed by the evaluator role")

    rp = reveal.get("payload")
    if not isinstance(rp, dict):
        raise E09EvidenceBindingError("reveal payload is malformed")
    if rp.get("scope") != scope or rp.get("learner_track") != learner_track:
        raise E09EvidenceBindingError("reveal scope or learner track does not match request")
    split = rp.get("split")
    if split not in _SPLIT_ROLE:
        raise E09EvidenceBindingError("unsupported E09 evidence split")
    prediction_id = rp.get("prediction_id")
    if not isinstance(prediction_id, str) or not prediction_id:
        raise E09EvidenceBindingError("reveal has no prediction_id")

    commits = [
        e for e in events
        if e.get("event_type") == "prediction_commit"
        and e.get("payload", {}).get("prediction_id") == prediction_id
        and e.get("payload", {}).get("learner_track") == learner_track
    ]
    if len(commits) != 1:
        raise E09EvidenceBindingError("reveal must bind to exactly one prediction commit")
    commit = commits[0]
    _verify_event_envelope(commit)
    cp = commit.get("payload")
    if commit.get("protocol_version") != STRICT_PROTOCOL_VERSION:
        raise E09EvidenceBindingError("prediction commit is not strict E09 v0.3")
    if commit.get("sequence_no", 0) >= reveal.get("sequence_no", 0):
        raise E09EvidenceBindingError("prediction commit must precede evidence reveal")
    if cp.get("scope") != scope or cp.get("split") != split:
        raise E09EvidenceBindingError("commit scope/split does not match reveal")
    if cp.get("interop_commit_digest") != rp.get("commit_digest"):
        raise E09EvidenceBindingError("reveal semantic commit digest mismatch")
    if commit.get("payload_digest") != rp.get("event_digest"):
        raise E09EvidenceBindingError("reveal durable event digest mismatch")
    expected_commit_event = f"{episode_id}:prediction:{prediction_id}"
    if expected_commit_event not in reveal.get("causation_refs", []):
        raise E09EvidenceBindingError("reveal causation does not reference the prediction event")

    observation_id = cp.get("observation_id")
    observations = [
        e for e in events
        if e.get("event_type") == "observation"
        and e.get("payload", {}).get("observation_id") == observation_id
    ]
    if len(observations) != 1:
        raise E09EvidenceBindingError("prediction must bind to exactly one observation")
    observation = observations[0]
    _verify_event_envelope(observation)
    op = observation.get("payload")
    if observation.get("protocol_version") != STRICT_PROTOCOL_VERSION:
        raise E09EvidenceBindingError("observation is not strict E09 v0.3")
    if observation.get("sequence_no", 0) >= commit.get("sequence_no", 0):
        raise E09EvidenceBindingError("observation must precede prediction commit")
    for field in ("query_id", "scope", "split"):
        if op.get(field) != cp.get(field) or rp.get(field) != cp.get(field):
            raise E09EvidenceBindingError(f"E09 observation/commit/reveal {field} mismatch")
    if commit.get("event_id") != expected_commit_event:
        raise E09EvidenceBindingError("prediction event identity mismatch")

    reveal_digest = reveal.get("payload_digest")
    if not isinstance(reveal_digest, str) or len(reveal_digest) != 64:
        raise E09EvidenceBindingError("reveal envelope digest is missing or malformed")
    return Evidence(
        evidence_id=evidence_ref,
        episode_id=episode_id,
        world_family=world_family,
        split_role=_SPLIT_ROLE[split],
        observation_id=observation_id,
        outcome=f"opaque-e09-evidence-ref:{evidence_ref}",
        model_version=cp.get("model_version"),
        measurement_cost=float(measurement_cost),
        prediction_commit_step=commit["sequence_no"],
        label_visibility_step=reveal["sequence_no"],
        provenance=f"opaque-e09-event-digest:{reveal_digest}",
    )


def register_e09_reveal(
    ledger: PersistentLifecycleLedger,
    store: SQLiteEvidenceStore,
    **kwargs: Any,
) -> tuple[Evidence, LifecycleEventReceipt]:
    """Resolve an E09 reveal and register its redacted E12-A6 evidence DTO."""
    if not isinstance(ledger, PersistentLifecycleLedger):
        raise TypeError("ledger must be PersistentLifecycleLedger")
    evidence = resolve_e09_reveal(store, **kwargs)
    return evidence, ledger.register_evidence(evidence)
