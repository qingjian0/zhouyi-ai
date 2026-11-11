"""ZNCA N3-D: persistent sparse counterfactual branches and compensation.

Branches share an immutable canonical base and persist only sparse deltas.
The append-only N3-C event stream remains authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from prototype.znca_n3c_event_store import (
    EventStoreError, IntegrityError, SQLiteEventStore, VersionConflict,
)


class BranchError(EventStoreError):
    pass


class StaleBranch(BranchError):
    pass


@dataclass(frozen=True)
class BranchView:
    branch_id: str
    hypothesis_id: str
    base_revision: int
    base_hash: str
    delta: tuple[tuple[str, str], ...]
    evidence_refs: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class CanonicalProjection:
    revision: int
    state: tuple[tuple[str, str], ...]
    canonical_hash: str
    compensated_sequences: tuple[int, ...]

    def as_dict(self) -> dict[str, str]:
        return dict(self.state)


class CounterfactualBranchLedger:
    """Persist branch metadata/deltas in N3-C without copying the base state."""

    METADATA_EVENTS = {
        "BranchCreated", "BranchDeltaRecorded", "BranchRejected",
    }

    def __init__(self, store: SQLiteEventStore) -> None:
        self.store = store

    def _projection(self) -> CanonicalProjection:
        state: dict[str, str] = {}
        revision = 0
        canonical_hash = "0" * 64
        compensated: set[int] = set()
        # Keep the exact pre/post image of each canonical mutation so replay
        # can validate compensation events, not merely trust their payload.
        mutation_effects: dict[int, tuple[dict[str, object], dict[str, str]]] = {}
        for event in self.store.verify():
            payload = event.payload
            if event.event_type in ("HypothesisCommitted", "BranchPromoted"):
                delta = payload.get("state_delta")
                if not isinstance(delta, dict) or any(
                    not isinstance(k, str) or not k.strip()
                    or not isinstance(v, str) or not v.strip()
                    for k, v in delta.items()
                ):
                    raise IntegrityError(f"invalid state_delta at sequence {event.sequence}")
                before = {
                    key: ({"present": True, "value": state[key]} if key in state
                          else {"present": False})
                    for key in delta
                }
                state.update(delta)
                mutation_effects[event.sequence] = (before, dict(delta))
                revision += 1
                canonical_hash = event.event_hash
            elif event.event_type == "CommitCompensated":
                target = payload.get("target_sequence")
                restore = payload.get("restore")
                if not isinstance(target, int) or target <= 0 or not isinstance(restore, dict):
                    raise IntegrityError("invalid compensation event")
                if target in compensated or target not in mutation_effects:
                    raise IntegrityError("compensation target is invalid or already compensated")
                expected_restore, target_delta = mutation_effects[target]
                if set(restore) != set(target_delta):
                    raise IntegrityError("compensation must restore exactly the target keys")
                for key, expected in expected_restore.items():
                    item = restore.get(key)
                    if item != expected:
                        raise IntegrityError("compensation restore does not match prior state")
                    if state.get(key) != target_delta[key]:
                        raise IntegrityError("compensation would overwrite a later canonical change")
                for key, item in restore.items():
                    if item["present"]:
                        state[key] = item["value"]
                    else:
                        state.pop(key, None)
                compensated.add(target)
                revision += 1
                canonical_hash = event.event_hash
            elif event.event_type in self.METADATA_EVENTS:
                continue
            else:
                raise IntegrityError(f"unsupported event type: {event.event_type}")
        return CanonicalProjection(
            revision, tuple(sorted(state.items())), canonical_hash,
            tuple(sorted(compensated)),
        )

    def projection(self) -> CanonicalProjection:
        return self._projection()

    def _branches(self) -> dict[str, BranchView]:
        branches: dict[str, BranchView] = {}
        deltas: dict[str, dict[str, str]] = {}
        for event in self.store.verify():
            p = event.payload
            kind = event.event_type
            if kind == "BranchCreated":
                branch_id = p.get("branch_id")
                if not isinstance(branch_id, str) or branch_id in branches:
                    raise IntegrityError("invalid or duplicate branch id")
                refs = p.get("evidence_refs")
                if not isinstance(refs, list) or not refs:
                    raise IntegrityError("branch evidence refs missing")
                branches[branch_id] = BranchView(
                    branch_id, str(p["hypothesis_id"]), int(p["base_revision"]),
                    str(p["base_hash"]), (), tuple(refs), "OPEN",
                )
                deltas[branch_id] = {}
            elif kind == "BranchDeltaRecorded":
                branch_id, key, value = p.get("branch_id"), p.get("key"), p.get("value")
                if branch_id not in branches or branches[branch_id].status != "OPEN":
                    raise IntegrityError("delta references a non-open branch")
                if not isinstance(key, str) or not key.strip() or not isinstance(value, str):
                    raise IntegrityError("invalid branch delta")
                deltas[branch_id][key] = value
            elif kind == "BranchRejected":
                branch_id = p.get("branch_id")
                if branch_id not in branches or branches[branch_id].status != "OPEN":
                    raise IntegrityError("reject references a non-open branch")
                old = branches[branch_id]
                branches[branch_id] = BranchView(
                    old.branch_id, old.hypothesis_id, old.base_revision,
                    old.base_hash, tuple(sorted(deltas[branch_id].items())),
                    old.evidence_refs, "REJECTED",
                )
            elif kind == "BranchPromoted":
                branch_id = p.get("branch_id")
                if branch_id not in branches or branches[branch_id].status != "OPEN":
                    raise IntegrityError("promotion references a non-open branch")
                old = branches[branch_id]
                branches[branch_id] = BranchView(
                    old.branch_id, old.hypothesis_id, old.base_revision,
                    old.base_hash, tuple(sorted(deltas[branch_id].items())),
                    old.evidence_refs, "PROMOTED",
                )
        for branch_id, old in tuple(branches.items()):
            if old.status == "OPEN":
                branches[branch_id] = BranchView(
                    old.branch_id, old.hypothesis_id, old.base_revision,
                    old.base_hash, tuple(sorted(deltas[branch_id].items())),
                    old.evidence_refs, old.status,
                )
        return branches

    def branches(self) -> tuple[BranchView, ...]:
        return tuple(self._branches()[key] for key in sorted(self._branches()))

    def get_branch(self, branch_id: str) -> BranchView:
        try:
            return self._branches()[branch_id]
        except KeyError as exc:
            raise BranchError("unknown branch_id") from exc

    def _append(self, transaction_id: str, event_type: str,
                payload: Mapping[str, object]):
        return self.store.append(
            expected_version=self.store.version, transaction_id=transaction_id,
            event_type=event_type, payload=payload,
        )

    def create_branch(self, *, branch_id: str, hypothesis_id: str,
                      evidence_refs: tuple[str, ...], transaction_id: str) -> BranchView:
        for value, name in ((branch_id, "branch_id"), (hypothesis_id, "hypothesis_id"),
                            (transaction_id, "transaction_id")):
            if not isinstance(value, str) or not value.strip():
                raise BranchError(f"{name} is required")
        refs = tuple(sorted(set(evidence_refs)))
        if not refs or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            raise BranchError("at least one unique evidence reference is required")
        if branch_id in self._branches():
            raise BranchError("branch_id must be unique")
        base = self._projection()
        self._append(transaction_id, "BranchCreated", {
            "branch_id": branch_id, "hypothesis_id": hypothesis_id,
            "base_revision": base.revision, "base_hash": base.canonical_hash,
            "evidence_refs": list(refs),
        })
        return self.get_branch(branch_id)

    def record_delta(self, *, branch_id: str, key: str, value: str,
                     transaction_id: str) -> BranchView:
        branch = self.get_branch(branch_id)
        if branch.status != "OPEN":
            raise BranchError("only OPEN branches accept deltas")
        if not isinstance(key, str) or not key.strip() or not isinstance(value, str):
            raise BranchError("delta key/value are invalid")
        self._append(transaction_id, "BranchDeltaRecorded", {
            "branch_id": branch_id, "key": key, "value": value,
        })
        return self.get_branch(branch_id)

    def reject(self, *, branch_id: str, reason: str, transaction_id: str) -> BranchView:
        branch = self.get_branch(branch_id)
        if branch.status != "OPEN":
            raise BranchError("only OPEN branches can be rejected")
        if not isinstance(reason, str) or not reason.strip():
            raise BranchError("rejection reason is required")
        self._append(transaction_id, "BranchRejected", {
            "branch_id": branch_id, "reason": reason,
        })
        return self.get_branch(branch_id)

    def promote(self, *, branch_id: str, transaction_id: str) -> BranchView:
        branch = self.get_branch(branch_id)
        if branch.status != "OPEN":
            raise BranchError("only OPEN branches can be promoted")
        if not branch.delta:
            raise BranchError("cannot promote an empty branch")
        current = self._projection()
        if (branch.base_revision != current.revision
                or branch.base_hash != current.canonical_hash):
            raise StaleBranch("branch base is stale; re-evaluate against current canonical state")
        self._append(transaction_id, "BranchPromoted", {
            "branch_id": branch_id, "hypothesis_id": branch.hypothesis_id,
            "base_revision": branch.base_revision, "base_hash": branch.base_hash,
            "evidence_refs": list(branch.evidence_refs),
            "state_delta": dict(branch.delta),
        })
        return self.get_branch(branch_id)

    def compensate(self, *, target_sequence: int, reason: str,
                   evidence_refs: tuple[str, ...], transaction_id: str):
        if not isinstance(target_sequence, int) or target_sequence <= 0:
            raise BranchError("target_sequence must be positive")
        if not isinstance(reason, str) or not reason.strip():
            raise BranchError("compensation reason is required")
        refs = tuple(sorted(set(evidence_refs)))
        if not refs or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            raise BranchError("compensation requires evidence references")
        events = self.store.verify()
        if target_sequence > len(events):
            raise BranchError("target event does not exist")
        target = events[target_sequence - 1]
        if target.event_type not in ("HypothesisCommitted", "BranchPromoted"):
            raise BranchError("only canonical mutation events can be compensated")
        projection = self._projection()
        if target_sequence in projection.compensated_sequences:
            raise BranchError("target event is already compensated")
        before: dict[str, str] = {}
        after: dict[str, str] = {}
        for event in events[:target_sequence - 1]:
            if event.event_type in ("HypothesisCommitted", "BranchPromoted"):
                before.update(event.payload["state_delta"])
            elif event.event_type == "CommitCompensated":
                for key, item in event.payload["restore"].items():
                    if item["present"]:
                        before[key] = item["value"]
                    else:
                        before.pop(key, None)
        after.update(before)
        after.update(target.payload["state_delta"])
        current = projection.as_dict()
        touched = set(target.payload["state_delta"])
        if any(current.get(key) != after.get(key) for key in touched):
            raise BranchError("later canonical changes overlap target; compensation is unsafe")
        restore = {
            key: ({"present": True, "value": before[key]} if key in before
                  else {"present": False})
            for key in sorted(touched)
        }
        return self._append(transaction_id, "CommitCompensated", {
            "target_sequence": target_sequence, "reason": reason,
            "evidence_refs": list(refs), "restore": restore,
        })
