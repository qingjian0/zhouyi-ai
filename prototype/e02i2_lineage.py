"""E02-I2-A: append-only relation identity, version and lineage ledger.

This is a deterministic bookkeeping prototype, not an identity matcher.
Candidate-to-identity assignment and evidence relevance are intentionally
outside this module and must be evaluated by later E02-I2 stages.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class IdentityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    SPLIT = "SPLIT"
    MERGED = "MERGED"
    REPLACED = "REPLACED"
    RETIRED = "RETIRED"


class LineageKind(str, Enum):
    SPLIT_FROM = "SPLIT_FROM"
    MERGED_FROM = "MERGED_FROM"
    REPLACED_BY = "REPLACED_BY"


@dataclass(frozen=True)
class RelationVersion:
    version_id: str
    identity_id: str
    version_index: int
    members: tuple[str, ...]
    roles: tuple[str, ...]
    operator: str
    rule_signature: str
    context_signature: str
    valid_from_window: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.version_id.strip() or not self.identity_id.strip():
            raise ValueError("version and identity IDs must be non-empty")
        if self.version_index < 1 or self.valid_from_window < 0:
            raise ValueError("invalid version index or window")
        if not self.members or len(set(self.members)) != len(self.members):
            raise ValueError("members must be non-empty and unique")
        if len(self.roles) != len(self.members):
            raise ValueError("each member must have exactly one role")
        if any(not x.strip() for x in (*self.members, *self.roles)):
            raise ValueError("members and roles must be non-empty")
        if not self.operator.strip() or not self.rule_signature.strip():
            raise ValueError("operator and rule signature must be non-empty")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("evidence references must be unique")


@dataclass(frozen=True)
class RelationIdentity:
    identity_id: str
    status: IdentityStatus
    created_window: int
    last_active_window: int
    version_ids: tuple[str, ...]


@dataclass(frozen=True)
class LineageEdge:
    kind: LineageKind
    source_identity_ids: tuple[str, ...]
    target_identity_id: str
    window: int
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class VersionTransition:
    kind: str
    identity_id: str
    from_version_id: str
    to_version_id: str
    window: int
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class LedgerEvent:
    sequence: int
    kind: str
    window: int
    identity_ids: tuple[str, ...]
    version_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


class LineageError(ValueError):
    """Raised when an identity/version transition violates ledger invariants."""


class RelationLineageLedger:
    """Append-only event ledger with immutable relation structure versions."""

    _TERMINAL = {
        IdentityStatus.SPLIT,
        IdentityStatus.MERGED,
        IdentityStatus.REPLACED,
        IdentityStatus.RETIRED,
    }

    def __init__(self) -> None:
        self.identities: dict[str, RelationIdentity] = {}
        self.versions: dict[str, RelationVersion] = {}
        self.lineage_edges: list[LineageEdge] = []
        self.version_transitions: list[VersionTransition] = []
        self.events: list[LedgerEvent] = []
        self._last_window = -1

    def _check_window(self, window: int) -> None:
        if window < 0 or window < self._last_window:
            raise LineageError("event windows must be non-negative and monotonic")

    def _record(self, kind: str, window: int, identity_ids: tuple[str, ...],
                version_ids: tuple[str, ...] = (),
                evidence_refs: tuple[str, ...] = ()) -> None:
        self.events.append(LedgerEvent(
            len(self.events) + 1, kind, window, identity_ids,
            version_ids, evidence_refs,
        ))
        self._last_window = window

    def _active(self, identity_id: str) -> RelationIdentity:
        identity = self.identities.get(identity_id)
        if identity is None:
            raise LineageError(f"unknown identity: {identity_id}")
        if identity.status != IdentityStatus.ACTIVE:
            raise LineageError(f"identity is not active: {identity_id}")
        return identity

    def _version(self, *, identity_id: str, version_id: str,
                 version_index: int, members: tuple[str, ...],
                 roles: tuple[str, ...], operator: str,
                 rule_signature: str, context_signature: str,
                 window: int, evidence_refs: tuple[str, ...]) -> RelationVersion:
        if version_id in self.versions:
            raise LineageError(f"duplicate version ID: {version_id}")
        return RelationVersion(
            version_id=version_id,
            identity_id=identity_id,
            version_index=version_index,
            members=members,
            roles=roles,
            operator=operator,
            rule_signature=rule_signature,
            context_signature=context_signature,
            valid_from_window=window,
            evidence_refs=evidence_refs,
        )

    def create(self, *, identity_id: str, version_id: str,
               members: tuple[str, ...], roles: tuple[str, ...],
               operator: str, rule_signature: str,
               context_signature: str = "global", window: int,
               evidence_refs: tuple[str, ...] = ()) -> RelationIdentity:
        self._check_window(window)
        if not identity_id.strip() or identity_id in self.identities:
            raise LineageError("identity ID must be non-empty and unique")
        version = self._version(
            identity_id=identity_id, version_id=version_id, version_index=1,
            members=members, roles=roles, operator=operator,
            rule_signature=rule_signature, context_signature=context_signature,
            window=window, evidence_refs=evidence_refs,
        )
        identity = RelationIdentity(
            identity_id, IdentityStatus.ACTIVE, window, window, (version_id,)
        )
        self.versions[version_id] = version
        self.identities[identity_id] = identity
        self._record("CREATE", window, (identity_id,), (version_id,), evidence_refs)
        return identity

    def keep(self, identity_id: str, *, window: int,
             evidence_refs: tuple[str, ...] = ()) -> RelationIdentity:
        self._check_window(window)
        identity = self._active(identity_id)
        updated = replace(identity, last_active_window=window)
        self.identities[identity_id] = updated
        self._record("KEEP", window, (identity_id,),
                     (identity.version_ids[-1],), evidence_refs)
        return updated

    def modify(self, identity_id: str, *, version_id: str,
               members: tuple[str, ...], roles: tuple[str, ...],
               operator: str, rule_signature: str,
               context_signature: str = "global", window: int,
               evidence_refs: tuple[str, ...] = ()) -> RelationVersion:
        self._check_window(window)
        identity = self._active(identity_id)
        previous_id = identity.version_ids[-1]
        version = self._version(
            identity_id=identity_id, version_id=version_id,
            version_index=len(identity.version_ids) + 1,
            members=members, roles=roles, operator=operator,
            rule_signature=rule_signature, context_signature=context_signature,
            window=window, evidence_refs=evidence_refs,
        )
        self.versions[version_id] = version
        self.identities[identity_id] = replace(
            identity, last_active_window=window,
            version_ids=(*identity.version_ids, version_id),
        )
        self.version_transitions.append(VersionTransition(
            "MODIFIED_FROM", identity_id, previous_id, version_id,
            window, evidence_refs,
        ))
        self._record("MODIFY", window, (identity_id,),
                     (previous_id, version_id), evidence_refs)
        return version

    def suspend(self, identity_id: str, *, window: int,
                evidence_refs: tuple[str, ...] = ()) -> RelationIdentity:
        self._check_window(window)
        identity = self._active(identity_id)
        updated = replace(identity, status=IdentityStatus.SUSPENDED)
        self.identities[identity_id] = updated
        self._record("SUSPEND", window, (identity_id,),
                     (identity.version_ids[-1],), evidence_refs)
        return updated

    def reactivate(self, identity_id: str, *, window: int,
                   evidence_refs: tuple[str, ...]) -> RelationIdentity:
        self._check_window(window)
        identity = self.identities.get(identity_id)
        if identity is None or identity.status != IdentityStatus.SUSPENDED:
            raise LineageError("only a suspended identity can be reactivated")
        if not evidence_refs:
            raise LineageError("reactivation requires fresh confirming evidence")
        updated = replace(
            identity, status=IdentityStatus.ACTIVE, last_active_window=window
        )
        self.identities[identity_id] = updated
        self._record("REACTIVATE", window, (identity_id,),
                     (identity.version_ids[-1],), evidence_refs)
        return updated

    def retire(self, identity_id: str, *, window: int,
               evidence_refs: tuple[str, ...] = ()) -> RelationIdentity:
        self._check_window(window)
        identity = self.identities.get(identity_id)
        if identity is None or identity.status not in {
            IdentityStatus.ACTIVE, IdentityStatus.SUSPENDED
        }:
            raise LineageError("only active or suspended identities can retire")
        updated = replace(identity, status=IdentityStatus.RETIRED)
        self.identities[identity_id] = updated
        self._record("RETIRE", window, (identity_id,),
                     (identity.version_ids[-1],), evidence_refs)
        return updated

    def split(self, parent_id: str, *, children: tuple[dict, ...],
              window: int, evidence_refs: tuple[str, ...] = ()) -> tuple[RelationIdentity, ...]:
        self._check_window(window)
        parent = self._active(parent_id)
        if len(children) < 2:
            raise LineageError("split requires at least two child identities")
        child_ids = [item.get("identity_id") for item in children]
        if len(set(child_ids)) != len(child_ids) or parent_id in child_ids:
            raise LineageError("split child IDs must be unique and differ from parent")
        created = []
        for item in children:
            child = self.create(
                identity_id=item["identity_id"], version_id=item["version_id"],
                members=tuple(item["members"]), roles=tuple(item["roles"]),
                operator=item["operator"], rule_signature=item["rule_signature"],
                context_signature=item.get("context_signature", "global"),
                window=window, evidence_refs=tuple(item.get("evidence_refs", ())),
            )
            created.append(child)
        self.identities[parent_id] = replace(parent, status=IdentityStatus.SPLIT)
        self.lineage_edges.extend(
            LineageEdge(LineageKind.SPLIT_FROM, (parent_id,), child.identity_id,
                        window, evidence_refs)
            for child in created
        )
        self._record("SPLIT", window, (parent_id, *child_ids),
                     tuple(v for child in created for v in child.version_ids),
                     evidence_refs)
        return tuple(created)

    def merge(self, parent_ids: tuple[str, ...], *, identity_id: str,
              version_id: str, members: tuple[str, ...], roles: tuple[str, ...],
              operator: str, rule_signature: str,
              context_signature: str = "global", window: int,
              evidence_refs: tuple[str, ...] = ()) -> RelationIdentity:
        self._check_window(window)
        if len(parent_ids) < 2 or len(set(parent_ids)) != len(parent_ids):
            raise LineageError("merge requires at least two distinct parents")
        parents = [self._active(parent_id) for parent_id in parent_ids]
        child = self.create(
            identity_id=identity_id, version_id=version_id, members=members,
            roles=roles, operator=operator, rule_signature=rule_signature,
            context_signature=context_signature, window=window,
            evidence_refs=evidence_refs,
        )
        for parent in parents:
            self.identities[parent.identity_id] = replace(
                parent, status=IdentityStatus.MERGED
            )
        self.lineage_edges.append(LineageEdge(
            LineageKind.MERGED_FROM, parent_ids, identity_id, window,
            evidence_refs,
        ))
        self._record("MERGE", window, (*parent_ids, identity_id),
                     (version_id,), evidence_refs)
        return child

    def replace(self, old_identity_id: str, *, identity_id: str,
                version_id: str, members: tuple[str, ...],
                roles: tuple[str, ...], operator: str, rule_signature: str,
                context_signature: str = "global", window: int,
                evidence_refs: tuple[str, ...] = ()) -> RelationIdentity:
        self._check_window(window)
        old = self._active(old_identity_id)
        if identity_id == old_identity_id:
            raise LineageError("replacement must create a new identity")
        new = self.create(
            identity_id=identity_id, version_id=version_id, members=members,
            roles=roles, operator=operator, rule_signature=rule_signature,
            context_signature=context_signature, window=window,
            evidence_refs=evidence_refs,
        )
        self.identities[old_identity_id] = replace(
            old, status=IdentityStatus.REPLACED
        )
        self.lineage_edges.append(LineageEdge(
            LineageKind.REPLACED_BY, (old_identity_id,), identity_id,
            window, evidence_refs,
        ))
        self._record("REPLACE", window, (old_identity_id, identity_id),
                     (old.version_ids[-1], version_id), evidence_refs)
        return new

    def assert_consistent(self) -> None:
        for identity_id, identity in self.identities.items():
            if identity.identity_id != identity_id or not identity.version_ids:
                raise AssertionError("identity key or version history is inconsistent")
            previous_index = 0
            for version_id in identity.version_ids:
                version = self.versions.get(version_id)
                if version is None or version.identity_id != identity_id:
                    raise AssertionError("identity references a missing/foreign version")
                if version.version_index <= previous_index:
                    raise AssertionError("version indices must strictly increase")
                previous_index = version.version_index
        for edge in self.lineage_edges:
            if edge.target_identity_id not in self.identities:
                raise AssertionError("lineage target is missing")
            if any(source not in self.identities for source in edge.source_identity_ids):
                raise AssertionError("lineage source is missing")
        for transition in self.version_transitions:
            if transition.from_version_id not in self.versions or transition.to_version_id not in self.versions:
                raise AssertionError("version transition references a missing version")
            if self.versions[transition.from_version_id].identity_id != transition.identity_id:
                raise AssertionError("version transition source identity mismatch")
            if self.versions[transition.to_version_id].identity_id != transition.identity_id:
                raise AssertionError("version transition target identity mismatch")
