"""Resolve durable E09 reveal events into safe E12-A6 evidence references.

The resolver verifies the E09 event chain and split context. It never copies
raw target_or_feedback into the E12-A6 Evidence DTO.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Callable

from prototype.csg_branch_delta import (
    VerifiedBranchMergeAuthorization, _issue_verified_branch_merge_authorization,
)
from prototype.e12a6_lifecycle_contract import Evidence, SplitRole
from prototype.e12a6_zpcm_persistence import LifecycleEventReceipt, PersistentLifecycleLedger
from prototype.shared_evidence_protocol import (
    DOMAIN_BOUND_PROTOCOL_VERSION, DOMAIN_FIELDS, STRICT_PROTOCOL_VERSION,
    SQLiteEvidenceStore, canonical_json, digest_payload,
)
from prototype.e09_domain_registry import E09DomainBinding, E09DomainRegistry


class E09EvidenceBindingError(ValueError):
    """An E09 evidence reference is missing, mismatched, or not verifiable."""


AUTHORIZATION_SIGNATURE_VERSION = "E09-AUTHZ-SIG-V2"
AUTHORIZATION_AUDIENCE = "e12a6-lifecycle"
AUTHORIZATION_PAYLOAD_SCHEMA = "branch_merge_authorization@2"


def branch_merge_authorization_signing_bytes(event: dict[str, Any]) -> bytes:
    """Canonical domain-separated signature over the complete security envelope."""
    required = ("episode_id", "event_id", "event_type", "protocol_version",
                "payload_schema", "actor_role", "causation_refs",
                "integrity_metadata", "payload")
    if any(key not in event for key in required):
        raise E09EvidenceBindingError("authorization signing envelope is incomplete")
    payload = event["payload"]
    if not isinstance(payload, dict):
        raise E09EvidenceBindingError("authorization payload is malformed")
    statement = {
        "domain": "zhouyi:e09:branch-merge:v2",
        "episode_id": event["episode_id"],
        "event_id": event["event_id"],
        "event_type": event["event_type"],
        "protocol_version": event["protocol_version"],
        "payload_schema": event["payload_schema"],
        "actor_role": event["actor_role"],
        "causation_refs": event["causation_refs"],
        "integrity_metadata": event["integrity_metadata"],
        "payload": {key: value for key, value in payload.items() if key != "signature"},
    }
    return canonical_json(statement).encode("utf-8")


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
    world_family: str | None = None,
    measurement_cost: float = 0.0,
    domain_registry: E09DomainRegistry | None = None,
    allow_legacy_migration: bool = False,
) -> Evidence:
    """Verify an E09 reveal→commit→observation chain and return a redacted DTO.

    SUPPORT maps to E12-A6 TRAIN because this E09 split is the learner-visible
    support/training partition. Gate and locked-test roles remain isolated.
    v0.4 derives domain metadata from the immutable observation and verifies it
    against the server-owned registry. The caller cannot override it. v0.3 is
    retained only as an explicit legacy compatibility path.
    """
    for name, value in (("episode_id", episode_id), ("evidence_ref", evidence_ref),
                        ("scope", scope), ("learner_track", learner_track)):
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
    protocol_version = reveal.get("protocol_version")
    if protocol_version not in (STRICT_PROTOCOL_VERSION, DOMAIN_BOUND_PROTOCOL_VERSION):
        raise E09EvidenceBindingError("unsupported E09 reveal protocol version")
    if protocol_version == DOMAIN_BOUND_PROTOCOL_VERSION:
        if world_family is not None:
            raise E09EvidenceBindingError("caller-supplied world-family overrides are forbidden")
        if domain_registry is None:
            raise E09EvidenceBindingError("v0.4 evidence requires the trusted domain registry")
        if reveal.get("payload_schema") != "evidence_reveal@4":
            raise E09EvidenceBindingError("v0.4 reveal requires the closed evidence_reveal@4 schema")
    elif not allow_legacy_migration:
        raise E09EvidenceBindingError("legacy v0.3 evidence is quarantined; explicit migration opt-in is required")
    elif not isinstance(world_family, str) or not world_family.strip():
        raise E09EvidenceBindingError("legacy v0.3 migration requires non-empty world-family context")
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
    if commit.get("protocol_version") != protocol_version:
        raise E09EvidenceBindingError("prediction commit protocol version differs from reveal")
    if protocol_version == DOMAIN_BOUND_PROTOCOL_VERSION and commit.get("payload_schema") != "prediction_commit@4":
        raise E09EvidenceBindingError("v0.4 commit requires the closed prediction_commit@4 schema")
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
    if observation.get("protocol_version") != protocol_version:
        raise E09EvidenceBindingError("observation protocol version differs from prediction commit")
    if protocol_version == DOMAIN_BOUND_PROTOCOL_VERSION and observation.get("payload_schema") != "observation@4":
        raise E09EvidenceBindingError("v0.4 observation requires the closed observation@4 schema")
    if observation.get("sequence_no", 0) >= commit.get("sequence_no", 0):
        raise E09EvidenceBindingError("observation must precede prediction commit")
    for field in ("query_id", "scope", "split"):
        if op.get(field) != cp.get(field) or rp.get(field) != cp.get(field):
            raise E09EvidenceBindingError(f"E09 observation/commit/reveal {field} mismatch")
    if commit.get("event_id") != expected_commit_event:
        raise E09EvidenceBindingError("prediction event identity mismatch")

    domain_id = domain_registry_id = domain_registry_version = ""
    if protocol_version == DOMAIN_BOUND_PROTOCOL_VERSION:
        for field in DOMAIN_FIELDS:
            if op.get(field) != cp.get(field) or rp.get(field) != cp.get(field):
                raise E09EvidenceBindingError(f"E09 observation/commit/reveal {field} mismatch")
        try:
            binding = domain_registry.resolve(scope)
        except Exception as exc:
            raise E09EvidenceBindingError("trusted domain registration is missing or revoked") from exc
        if not isinstance(binding, E09DomainBinding):
            raise E09EvidenceBindingError("trusted domain registry returned an invalid binding")
        expected = {
            "domain_id": binding.domain_id,
            "world_family": binding.world_family,
            "domain_registry_id": binding.registry_id,
            "domain_registry_version": binding.registry_version,
        }
        if not binding.active or any(op.get(key) != value for key, value in expected.items()):
            raise E09EvidenceBindingError("observation domain provenance does not match the active trusted registry")
        derived_world_family = binding.world_family
        domain_id = binding.domain_id
        domain_registry_id = binding.registry_id
        domain_registry_version = binding.registry_version
    else:
        derived_world_family = world_family

    reveal_digest = reveal.get("payload_digest")
    if not isinstance(reveal_digest, str) or len(reveal_digest) != 64:
        raise E09EvidenceBindingError("reveal envelope digest is missing or malformed")
    return Evidence(
        evidence_id=evidence_ref,
        episode_id=episode_id,
        world_family=derived_world_family,
        split_role=_SPLIT_ROLE[split],
        observation_id=observation_id,
        outcome=f"opaque-e09-evidence-ref:{evidence_ref}",
        model_version=cp.get("model_version"),
        measurement_cost=float(measurement_cost),
        prediction_commit_step=commit["sequence_no"],
        label_visibility_step=reveal["sequence_no"],
        provenance=f"opaque-e09-event-digest:{reveal_digest}",
        domain_id=domain_id,
        domain_registry_id=domain_registry_id,
        domain_registry_version=domain_registry_version,
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
    if not evidence.domain_id or not evidence.domain_registry_id or not evidence.domain_registry_version:
        raise E09EvidenceBindingError(
            "legacy v0.3 evidence is quarantined from E12-A6 registration; "
            "migration requires trusted v0.4 domain provenance"
        )
    return evidence, ledger.register_evidence(evidence)


def resolve_branch_merge_authorization(
    store: SQLiteEvidenceStore,
    *,
    episode_id: str,
    authorization_ref: str,
    parent_state_ref: str,
    branch_ids: tuple[str, ...],
    scope: str,
    learner_track: str,
    world_family_by_evidence: dict[str, str] | None = None,
    signature_verifier: Callable[[str, str, bytes, str], bool],
    verifier_id: str,
    now: datetime | None = None,
    domain_registry: E09DomainRegistry | None = None,
    allow_legacy_migration: bool = False,
) -> VerifiedBranchMergeAuthorization:
    """Authenticate a scoped branch-merge grant from an immutable E09 event.

    signature_verifier must be backed by an out-of-band trusted issuer keyring
    (normally pinned public keys). It receives issuer ID, algorithm, canonical
    signed bytes and signature. E09 event hashing alone is not authentication.
    """
    for name, value in (("episode_id", episode_id), ("authorization_ref", authorization_ref),
                        ("parent_state_ref", parent_state_ref), ("scope", scope),
                        ("learner_track", learner_track), ("verifier_id", verifier_id)):
        if not isinstance(value, str) or not value.strip():
            raise E09EvidenceBindingError(f"{name} must be a non-empty string")
    if not isinstance(branch_ids, (tuple, list)) or not branch_ids:
        raise E09EvidenceBindingError("branch_ids must be a non-empty sequence")
    if any(not isinstance(value, str) or not value.strip() for value in branch_ids):
        raise E09EvidenceBindingError("branch_ids must contain non-empty strings")
    if len(set(branch_ids)) != len(branch_ids):
        raise E09EvidenceBindingError("branch_ids must be unique")
    if domain_registry is not None and world_family_by_evidence is not None:
        raise E09EvidenceBindingError("caller-supplied world-family overrides are forbidden")
    if domain_registry is None and not allow_legacy_migration:
        raise E09EvidenceBindingError("legacy branch authorization is quarantined outside explicit migration")
    if domain_registry is None and not isinstance(world_family_by_evidence, dict):
        raise E09EvidenceBindingError("legacy migration requires explicit world-family mapping")
    if domain_registry is not None and allow_legacy_migration:
        raise E09EvidenceBindingError("legacy migration flag is invalid with a trusted domain registry")
    if not callable(signature_verifier):
        raise E09EvidenceBindingError("signature_verifier must be callable")

    try:
        events = store.replay_episode(episode_id)
    except Exception as exc:
        raise E09EvidenceBindingError(f"cannot replay E09 episode: {exc}") from exc
    matches = [event for event in events if event.get("event_id") == authorization_ref]
    if len(matches) != 1:
        raise E09EvidenceBindingError("authorization_ref must identify exactly one E09 event")
    event = matches[0]
    _verify_event_envelope(event)
    if event.get("event_type") != "branch_merge_authorization":
        raise E09EvidenceBindingError("authorization_ref is not a branch_merge_authorization event")
    if event.get("protocol_version") != STRICT_PROTOCOL_VERSION or event.get("actor_role") != "authorizer":
        raise E09EvidenceBindingError("authorization must be a strict v0.3 authorizer event")

    payload = event.get("payload")
    if not isinstance(payload, dict):
        raise E09EvidenceBindingError("authorization payload is malformed")
    issuer_id = payload.get("issuer_id")
    if payload.get("authorization_id") != authorization_ref:
        raise E09EvidenceBindingError("authorization event ID and authorization_id differ")
    if payload.get("scope") != scope or payload.get("parent_state_ref") != parent_state_ref:
        raise E09EvidenceBindingError("authorization scope or parent state does not match")
    authorized_branches = payload.get("branch_ids")
    if not isinstance(authorized_branches, list) or set(authorized_branches) != set(branch_ids):
        raise E09EvidenceBindingError("authorization branch set must exactly match selected branches")
    evidence_refs = payload.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs or len(set(evidence_refs)) != len(evidence_refs):
        raise E09EvidenceBindingError("authorization evidence_refs must be non-empty and unique")
    if event.get("causation_refs") != evidence_refs:
        raise E09EvidenceBindingError("authorization causation refs must exactly match its evidence refs")
    if domain_registry is None:
        if set(world_family_by_evidence) != set(evidence_refs):
            raise E09EvidenceBindingError("legacy authorization evidence context is incomplete")
        if any(not isinstance(value, str) or not value.strip() for value in world_family_by_evidence.values()):
            raise E09EvidenceBindingError("legacy world-family context values must be non-empty strings")

    try:
        issued = datetime.fromisoformat(payload["issued_at"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError) as exc:
        raise E09EvidenceBindingError("authorization timestamps are malformed") from exc
    if issued.tzinfo is None or expires.tzinfo is None or expires <= issued:
        raise E09EvidenceBindingError("authorization timestamps must be timezone-aware and ordered")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise E09EvidenceBindingError("verification time must be timezone-aware")
    if current < issued or current >= expires:
        raise E09EvidenceBindingError("branch merge authorization is not currently valid")

    for ref in evidence_refs:
        reveal = next((item for item in events if item.get("event_id") == ref), None)
        if reveal is None or reveal.get("sequence_no", 0) >= event.get("sequence_no", 0):
            raise E09EvidenceBindingError("authorization evidence must be prior E09 events")
        if domain_registry is not None:
            resolve_e09_reveal(
                store, episode_id=episode_id, evidence_ref=ref, scope=scope,
                learner_track=learner_track, domain_registry=domain_registry,
            )
        else:
            resolve_e09_reveal(
                store, episode_id=episode_id, evidence_ref=ref, scope=scope,
                learner_track=learner_track, world_family=world_family_by_evidence[ref],
                allow_legacy_migration=True,
            )

    if event.get("payload_schema") != AUTHORIZATION_PAYLOAD_SCHEMA:
        raise E09EvidenceBindingError("authorization requires branch_merge_authorization@2 schema")
    expected_payload_keys = {
        "authorization_id", "issuer_id", "scope", "parent_state_ref",
        "branch_ids", "evidence_refs", "issued_at", "expires_at",
        "signature_algorithm", "signature_version", "audience",
        "authorization_sequence", "signature",
    }
    if set(payload) != expected_payload_keys:
        raise E09EvidenceBindingError("authorization payload has missing or unknown fields")
    if payload.get("signature_version") != AUTHORIZATION_SIGNATURE_VERSION:
        raise E09EvidenceBindingError("unsupported authorization signature version")
    if payload.get("audience") != AUTHORIZATION_AUDIENCE:
        raise E09EvidenceBindingError("authorization audience does not match E12-A6 lifecycle service")
    authorization_sequence = payload.get("authorization_sequence")
    if (isinstance(authorization_sequence, bool)
            or not isinstance(authorization_sequence, int)
            or authorization_sequence < 1
            or authorization_sequence != event.get("sequence_no")):
        raise E09EvidenceBindingError("signed authorization_sequence does not match durable event sequence")
    signed_bytes = branch_merge_authorization_signing_bytes(event)
    algorithm = payload.get("signature_algorithm")
    signature = payload.get("signature")
    if not isinstance(issuer_id, str) or not issuer_id.strip():
        raise E09EvidenceBindingError("authorization issuer_id is missing")
    if algorithm != "Ed25519" or not isinstance(signature, str) or not signature:
        raise E09EvidenceBindingError("authorization signature metadata is missing or unsupported")
    try:
        valid = signature_verifier(issuer_id, algorithm, signed_bytes, signature)
    except Exception as exc:
        raise E09EvidenceBindingError("trusted issuer signature verifier failed") from exc
    if valid is not True:
        raise E09EvidenceBindingError("branch merge authorization signature is invalid or issuer is untrusted")

    return _issue_verified_branch_merge_authorization(
        authorization_ref=authorization_ref,
        parent_state_ref=parent_state_ref,
        branch_ids=tuple(sorted(branch_ids)),
        evidence_refs=tuple(evidence_refs),
        issuer_id=issuer_id,
        event_digest=event["payload_digest"],
        verifier_id=verifier_id,
        domain_provenance_verified=domain_registry is not None,
    )
