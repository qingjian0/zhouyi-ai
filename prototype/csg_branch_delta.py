"""Deterministic, provenance-preserving branch deltas for CSG-GCR.

Snapshots share an immutable parent state and carry only append-only edits.
This module validates structural mergeability; it does not infer semantic
compatibility, authorize cross-worldline transfer, or own candidate lifecycle.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Mapping


class DeltaOperation(str, Enum):
    ADD_NODE = "ADD_NODE"
    REMOVE_NODE = "REMOVE_NODE"
    ADD_RELATION = "ADD_RELATION"
    REMOVE_RELATION = "REMOVE_RELATION"
    ADD_HYPEREDGE = "ADD_HYPEREDGE"
    REMOVE_HYPEREDGE = "REMOVE_HYPEREDGE"
    UPDATE_ATTRIBUTE = "UPDATE_ATTRIBUTE"
    ADD_CONSTRAINT = "ADD_CONSTRAINT"
    REMOVE_CONSTRAINT = "REMOVE_CONSTRAINT"


class MergeStatus(str, Enum):
    MERGED = "MERGED"
    NO_OP = "NO_OP"
    CONFLICT = "CONFLICT"
    STALE = "STALE"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


@dataclass(frozen=True, init=False)
class BranchDelta:
    event_id: str
    operation: DeltaOperation
    target_ref: str
    before_hash: str | None
    _after_value_json: str
    evidence_refs: tuple[str, ...]
    causal_parent: str | None
    version: int

    def __init__(self, event_id: str, operation: DeltaOperation, target_ref: str,
                 before_hash: str | None, after_value: Any,
                 evidence_refs: tuple[str, ...], causal_parent: str | None,
                 version: int) -> None:
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "operation", operation)
        object.__setattr__(self, "target_ref", target_ref)
        object.__setattr__(self, "before_hash", before_hash)
        object.__setattr__(self, "_after_value_json", _canonical_json(after_value))
        object.__setattr__(self, "evidence_refs", tuple(evidence_refs))
        object.__setattr__(self, "causal_parent", causal_parent)
        object.__setattr__(self, "version", version)

    @property
    def after_value(self) -> Any:
        # Return a fresh decoded object so callers cannot mutate the event.
        return json.loads(self._after_value_json)


@dataclass(frozen=True)
class BranchSnapshot:
    parent_state_ref: str
    parent_state_hash: str
    branch_id: str
    base_version: int
    delta_events: tuple[BranchDelta, ...]
    read_set: tuple[str, ...]
    write_set: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    lineage: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in ("delta_events", "read_set", "write_set", "evidence_refs", "lineage"):
            object.__setattr__(self, field, tuple(getattr(self, field)))


@dataclass(frozen=True)
class BranchMergeAuthorization:
    """Unverified authorization claims. Never sufficient to authorize a merge."""
    authorization_ref: str
    parent_state_ref: str
    branch_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "branch_ids", tuple(self.branch_ids))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


_VERIFIED_AUTHORIZATION_SEAL = object()


@dataclass(frozen=True, init=False)
class VerifiedBranchMergeAuthorization(BranchMergeAuthorization):
    """E09-verified authorization capability; direct construction is blocked."""
    issuer_id: str
    event_digest: str
    verifier_id: str
    domain_provenance_verified: bool

    def __init__(
        self, authorization_ref: str, parent_state_ref: str,
        branch_ids: tuple[str, ...], evidence_refs: tuple[str, ...],
        issuer_id: str, event_digest: str, verifier_id: str,
        domain_provenance_verified: bool = False, *, _seal: object | None = None,
    ) -> None:
        if _seal is not _VERIFIED_AUTHORIZATION_SEAL:
            raise TypeError("VerifiedBranchMergeAuthorization must come from the E09 verifier")
        object.__setattr__(self, "authorization_ref", authorization_ref)
        object.__setattr__(self, "parent_state_ref", parent_state_ref)
        object.__setattr__(self, "branch_ids", tuple(branch_ids))
        object.__setattr__(self, "evidence_refs", tuple(evidence_refs))
        object.__setattr__(self, "issuer_id", issuer_id)
        object.__setattr__(self, "event_digest", event_digest)
        object.__setattr__(self, "verifier_id", verifier_id)
        object.__setattr__(self, "domain_provenance_verified", bool(domain_provenance_verified))


def _issue_verified_branch_merge_authorization(
    authorization_ref: str, parent_state_ref: str, branch_ids: tuple[str, ...],
    evidence_refs: tuple[str, ...], issuer_id: str, event_digest: str, verifier_id: str,
    domain_provenance_verified: bool = False,
) -> VerifiedBranchMergeAuthorization:
    """Internal factory called only after the E09 signature verifier succeeds."""
    return VerifiedBranchMergeAuthorization(
        authorization_ref, parent_state_ref, branch_ids, evidence_refs,
        issuer_id, event_digest, verifier_id, domain_provenance_verified,
        _seal=_VERIFIED_AUTHORIZATION_SEAL,
    )


def validate_merge_authorization(
    authorization: BranchMergeAuthorization,
    parent_state_ref: str,
    branch_ids: tuple[str, ...],
) -> None:
    if not isinstance(authorization, VerifiedBranchMergeAuthorization):
        raise ValueError("cross-branch merge requires an E09 signature-verified authorization")
    _text(authorization.issuer_id, "authorization issuer_id")
    _text(authorization.verifier_id, "authorization verifier_id")
    if authorization.domain_provenance_verified is not True:
        raise ValueError("cross-branch authorization lacks trusted domain provenance")
    if (not isinstance(authorization.event_digest, str) or len(authorization.event_digest) != 64
            or any(ch not in "0123456789abcdef" for ch in authorization.event_digest)):
        raise ValueError("verified authorization event_digest must be a lowercase SHA-256 digest")
    _text(authorization.authorization_ref, "authorization_ref")
    _text(authorization.parent_state_ref, "authorization parent_state_ref")
    if authorization.parent_state_ref != parent_state_ref:
        raise ValueError("merge authorization parent state does not match")
    for field, values in (("authorization branch_ids", authorization.branch_ids),
                          ("authorization evidence_refs", authorization.evidence_refs)):
        if not values or len(values) != len(set(values)):
            raise ValueError(f"{field} must be non-empty and unique")
        for value in values:
            _text(value, field)
    if not set(branch_ids).issubset(set(authorization.branch_ids)):
        raise ValueError("merge authorization does not cover every selected branch")


@dataclass(frozen=True)
class MergeResult:
    status: MergeStatus
    state: tuple[tuple[str, Any], ...]
    applied_event_ids: tuple[str, ...]
    conflicts: tuple[str, ...]
    reason: str = ""


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("delta values must be finite JSON-compatible data") from exc


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def validate_snapshot(snapshot: BranchSnapshot) -> None:
    if not isinstance(snapshot, BranchSnapshot):
        raise ValueError("snapshot must be BranchSnapshot")
    _text(snapshot.parent_state_ref, "parent_state_ref")
    if (not isinstance(snapshot.parent_state_hash, str) or len(snapshot.parent_state_hash) != 64
            or any(ch not in "0123456789abcdef" for ch in snapshot.parent_state_hash)):
        raise ValueError("parent_state_hash must be a lowercase SHA-256 hex digest")
    _text(snapshot.branch_id, "branch_id")
    if isinstance(snapshot.base_version, bool) or not isinstance(snapshot.base_version, int) or snapshot.base_version < 0:
        raise ValueError("base_version must be a non-negative integer")
    for field, values in (("read_set", snapshot.read_set), ("write_set", snapshot.write_set),
                          ("evidence_refs", snapshot.evidence_refs), ("lineage", snapshot.lineage)):
        if len(values) != len(set(values)):
            raise ValueError(f"{field} must not contain duplicates")
        for value in values:
            _text(value, field)
    ids = set()
    previous_version = snapshot.base_version
    previous_event = None
    actual_writes = set()
    evidence = set()
    for event in snapshot.delta_events:
        if not isinstance(event, BranchDelta):
            raise ValueError("delta_events must contain BranchDelta")
        _text(event.event_id, "event_id")
        _text(event.target_ref, "target_ref")
        if not isinstance(event.operation, DeltaOperation):
            raise ValueError("operation must be DeltaOperation")
        if event.event_id in ids:
            raise ValueError("event IDs must be unique within a branch")
        ids.add(event.event_id)
        if isinstance(event.version, bool) or not isinstance(event.version, int) or event.version <= previous_version:
            raise ValueError("delta versions must increase beyond base_version")
        if event.causal_parent != previous_event:
            raise ValueError("causal_parent must reference the preceding event")
        if event.before_hash is not None and (
                not isinstance(event.before_hash, str) or len(event.before_hash) != 64
                or any(ch not in "0123456789abcdef" for ch in event.before_hash)):
            raise ValueError("before_hash must be a lowercase SHA-256 hex digest or None")
        if not event.evidence_refs:
            raise ValueError("every delta event requires at least one evidence or derivation reference")
        if len(event.evidence_refs) != len(set(event.evidence_refs)):
            raise ValueError("event evidence_refs must not contain duplicates")
        if event.operation in (DeltaOperation.ADD_NODE, DeltaOperation.ADD_RELATION,
                               DeltaOperation.ADD_HYPEREDGE, DeltaOperation.ADD_CONSTRAINT):
            if event.before_hash is not None:
                raise ValueError("ADD operations require before_hash=None")
        else:
            if event.before_hash is None:
                raise ValueError("mutating/removal operations require before_hash")
        canonical_hash(event.after_value)
        for ref in event.evidence_refs:
            _text(ref, "event evidence ref")
            evidence.add(ref)
        actual_writes.add(event.target_ref)
        previous_version, previous_event = event.version, event.event_id
    if actual_writes != set(snapshot.write_set):
        raise ValueError("write_set must exactly match delta targets")
    if not evidence.issubset(set(snapshot.evidence_refs)):
        raise ValueError("snapshot evidence_refs must cover every event evidence ref")


def _apply_event(state: dict[str, Any], event: BranchDelta) -> str | None:
    exists = event.target_ref in state
    if event.before_hash is not None:
        if not exists or canonical_hash(state[event.target_ref]) != event.before_hash:
            return "before_hash mismatch (stale base or write dependency)"
    elif exists:
        return "ADD target already exists"
    if event.operation in (DeltaOperation.REMOVE_NODE, DeltaOperation.REMOVE_RELATION,
                           DeltaOperation.REMOVE_HYPEREDGE, DeltaOperation.REMOVE_CONSTRAINT):
        if not exists:
            return "REMOVE target does not exist"
        del state[event.target_ref]
    elif event.operation in (DeltaOperation.ADD_NODE, DeltaOperation.ADD_RELATION,
                             DeltaOperation.ADD_HYPEREDGE, DeltaOperation.ADD_CONSTRAINT,
                             DeltaOperation.UPDATE_ATTRIBUTE):
        if event.operation == DeltaOperation.UPDATE_ATTRIBUTE and not exists:
            return "UPDATE target does not exist"
        state[event.target_ref] = event.after_value
    else:
        return "unsupported operation"
    return None


def merge_branch_deltas(base_state: Mapping[str, Any],
                        snapshots: tuple[BranchSnapshot, ...]) -> MergeResult:
    """Merge disjoint deltas against one exact immutable parent snapshot.

    Same-target writes and write/read dependencies are rejected rather than
    resolved by score, branch order, timestamps, or model-generated guesses.
    """
    try:
        if not isinstance(base_state, Mapping):
            raise ValueError("base_state must be a mapping")
        state = {}
        for key, value in base_state.items():
            _text(key, "base state key")
            # Validate and detach nested mutable values from caller-owned objects.
            state[key] = json.loads(_canonical_json(value))
        if not snapshots:
            return MergeResult(MergeStatus.NO_OP, tuple(sorted(state.items())), (), ())
        for snap in snapshots:
            validate_snapshot(snap)
        branch_ids = [s.branch_id for s in snapshots]
        if len(branch_ids) != len(set(branch_ids)):
            return MergeResult(MergeStatus.REJECTED, tuple(sorted(state.items())), (), (),
                               "branch IDs must be unique in one merge request")
        parents = {s.parent_state_ref for s in snapshots}
        parent_hashes = {s.parent_state_hash for s in snapshots}
        versions = {s.base_version for s in snapshots}
        if len(parents) != 1 or len(parent_hashes) != 1 or len(versions) != 1:
            return MergeResult(MergeStatus.REJECTED, tuple(sorted(state.items())), (), (),
                               "all branches must share the exact parent identity, hash and base version")
        if canonical_hash(state) != next(iter(parent_hashes)):
            return MergeResult(MergeStatus.STALE, tuple(sorted(state.items())), (), (),
                               "base_state does not match the declared immutable parent hash")
        all_events: dict[str, BranchDelta] = {}
        target_writers: dict[str, dict[str, set[str]]] = {}
        for snap in snapshots:
            for event in snap.delta_events:
                previous = all_events.get(event.event_id)
                if previous is not None and previous != event:
                    return MergeResult(MergeStatus.CONFLICT, tuple(sorted(state.items())), (), (event.event_id,),
                                       "event ID reused with different content")
                all_events[event.event_id] = event
                target_writers.setdefault(event.target_ref, {}).setdefault(snap.branch_id, set()).add(event.event_id)
        unique_events = tuple(all_events.values())
        overlap = tuple(sorted(
            target for target, writers in target_writers.items()
            if len(set().union(*writers.values())) > 1 and len(writers) > 1
        ))
        if overlap:
            return MergeResult(MergeStatus.CONFLICT, tuple(sorted(state.items())), (), overlap,
                               "distinct branches write the same target")
        writes = set(target_writers)
        for snap in snapshots:
            other_reads = set().union(*(set(s.read_set) for s in snapshots if s.branch_id != snap.branch_id))
            collision = writes.intersection(other_reads)
            if collision:
                return MergeResult(MergeStatus.CONFLICT, tuple(sorted(state.items())), (),
                                   tuple(sorted(collision)), "write/read dependency conflict")
        ordered = tuple(sorted(unique_events, key=lambda e: (e.version, e.event_id)))
        applied = []
        for event in ordered:
            reason = _apply_event(state, event)
            if reason:
                status = MergeStatus.STALE if "before_hash" in reason else MergeStatus.CONFLICT
                return MergeResult(status, tuple(sorted(state.items())), tuple(applied),
                                   (event.target_ref,), reason)
            applied.append(event.event_id)
        status = MergeStatus.MERGED if applied else MergeStatus.NO_OP
        return MergeResult(status, tuple(sorted(state.items())), tuple(applied), ())
    except (TypeError, ValueError) as exc:
        safe_state = ()
        if isinstance(base_state, Mapping):
            try:
                safe_state = tuple(sorted((key, json.loads(_canonical_json(value)))
                                          for key, value in base_state.items()))
            except (TypeError, ValueError):
                safe_state = ()
        return MergeResult(MergeStatus.REJECTED, safe_state, (), (), str(exc))
