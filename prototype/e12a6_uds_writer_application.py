"""Production composition root for authenticated E12-A6 UDS candidate writes.

All identity claims are derived from SO_PEERCRED and a fixed server-owned
(uid, gid) map. JSON is a versioned data protocol, never an identity channel.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from prototype.csg_branch_delta import BranchDelta, BranchSnapshot, DeltaOperation
from prototype.csg_gcr_coordinator import CandidateProposal, GlobalConstraints
from prototype.e12a6_unix_socket import (
    E12A6IPCError, E12A6PeerCredentials, E12A6UnixSocketServer,
)
from prototype.e12a6_writer_runtime import E12A6WriterRuntime
from prototype.e12a6_writer_service import E12A6WorkloadAuthenticator
from prototype.typed_csg_gcr import TypedCandidateProposal
from prototype.typed_hypergraph_unifier import (
    HyperedgeProposal, RoleBinding, RoleRequirement, UnificationConstraints,
    VariableRef, VariableRelation, VariableSpec,
)


PROTOCOL_VERSION = 1
SUBMIT_OPERATION = "submit_authorized_merge_candidate"
_MAX_ITEMS = 4096
_MAX_STRING = 16_384
_MAX_DEPTH = 24
_MAX_NODES = 50_000


class E12A6UDSProtocolError(ValueError):
    """A UDS application request violates the strict versioned protocol."""


@dataclass(frozen=True)
class E12A6PeerWorkloadBinding:
    """Server-configured mapping from a kernel peer tuple to an auth credential."""
    uid: int
    gid: int
    credential: object


def _object(value: Any, required: set[str], optional: set[str], field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise E12A6UDSProtocolError(f"{field} must be an object")
    keys = set(value)
    missing, unknown = required - keys, keys - required - optional
    if missing or unknown:
        raise E12A6UDSProtocolError(
            f"{field} schema mismatch; missing={sorted(missing)} unknown={sorted(unknown)}"
        )
    return value


def _text(value: Any, field: str, *, maximum: int = _MAX_STRING) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise E12A6UDSProtocolError(f"{field} must be a non-empty bounded string")
    return value


def _int(value: Any, field: str, *, minimum: int = 0, maximum: int = 2**31 - 1) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise E12A6UDSProtocolError(f"{field} must be an integer in range")
    return value


def _optional_int(value: Any, field: str) -> int | None:
    return None if value is None else _int(value, field)


def _sequence(value: Any, field: str, *, maximum: int = _MAX_ITEMS) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum:
        raise E12A6UDSProtocolError(f"{field} must be a bounded array")
    return value


def _unique_strings(value: Any, field: str, *, maximum: int = _MAX_ITEMS) -> tuple[str, ...]:
    rows = tuple(_text(item, field) for item in _sequence(value, field, maximum=maximum))
    if len(rows) != len(set(rows)):
        raise E12A6UDSProtocolError(f"{field} must not contain duplicates")
    return rows


def _json_value(value: Any, field: str, *, budget: list[int] | None = None, depth: int = 0) -> Any:
    """Validate bounded JSON values before handing them to domain constructors."""
    if budget is None:
        budget = [_MAX_NODES]
    budget[0] -= 1
    if budget[0] < 0 or depth > _MAX_DEPTH:
        raise E12A6UDSProtocolError(f"{field} exceeds JSON complexity limits")
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise E12A6UDSProtocolError(f"{field} contains a non-finite number")
        return value
    if isinstance(value, str):
        if len(value) > _MAX_STRING:
            raise E12A6UDSProtocolError(f"{field} contains an oversized string")
        return value
    if isinstance(value, list):
        if len(value) > _MAX_ITEMS:
            raise E12A6UDSProtocolError(f"{field} contains an oversized array")
        return [_json_value(item, field, budget=budget, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        if len(value) > _MAX_ITEMS or any(not isinstance(key, str) for key in value):
            raise E12A6UDSProtocolError(f"{field} contains an invalid object")
        return {
            _text(key, f"{field} key"): _json_value(item, field, budget=budget, depth=depth + 1)
            for key, item in value.items()
        }
    raise E12A6UDSProtocolError(f"{field} contains a non-JSON value")


def _variable_ref(raw: Any, field: str) -> VariableRef:
    obj = _object(raw, {"namespace", "name"}, set(), field)
    return VariableRef(_text(obj["namespace"], field), _text(obj["name"], field))


def _variable_spec(raw: Any) -> VariableSpec:
    obj = _object(raw, {"ref", "value_type"}, {"required"}, "variable")
    required = obj.get("required", True)
    if type(required) is not bool:
        raise E12A6UDSProtocolError("variable.required must be boolean")
    return VariableSpec(_variable_ref(obj["ref"], "variable.ref"),
                        _text(obj["value_type"], "variable.value_type"), required)


def _constraints(raw: Any) -> UnificationConstraints:
    obj = _object(raw, set(), {"equal", "not_equal", "role_requirements", "subtype_of"},
                  "unification_constraints")
    def relations(name: str) -> tuple[VariableRelation, ...]:
        rows = []
        for item in _sequence(obj.get(name, []), name):
            pair = _object(item, {"left", "right"}, set(), name)
            rows.append(VariableRelation(_variable_ref(pair["left"], name),
                                         _variable_ref(pair["right"], name)))
        return tuple(rows)
    requirements = []
    for item in _sequence(obj.get("role_requirements", []), "role_requirements"):
        row = _object(item, {"relation_type", "role"}, {"required", "allowed_member_types"},
                      "role_requirement")
        required = row.get("required", True)
        if type(required) is not bool:
            raise E12A6UDSProtocolError("role_requirement.required must be boolean")
        requirements.append(RoleRequirement(
            _text(row["relation_type"], "relation_type"),
            _text(row["role"], "role"),
            required,
            _unique_strings(row.get("allowed_member_types", []), "allowed_member_types"),
        ))
    subtype = []
    for item in _sequence(obj.get("subtype_of", []), "subtype_of"):
        if not isinstance(item, list) or len(item) != 2:
            raise E12A6UDSProtocolError("subtype_of entries must be two-element arrays")
        subtype.append((_text(item[0], "subtype child"), _text(item[1], "subtype parent")))
    return UnificationConstraints(relations("equal"), relations("not_equal"),
                                  tuple(requirements), tuple(subtype))


def _typed_proposal(raw: Any) -> TypedCandidateProposal:
    obj = _object(raw, {"proposal", "hyperedge", "variables"},
                  {"constraints", "semantic_status"}, "typed_proposal")
    p = _object(obj["proposal"], {"proposal_id", "parent_state_ref", "branch_id",
                                  "bindings", "evidence_refs"},
                {"requires", "excludes", "score", "cost", "candidate_kind"}, "proposal")
    bindings = []
    for pair in _sequence(p["bindings"], "proposal.bindings"):
        if not isinstance(pair, list) or len(pair) != 2:
            raise E12A6UDSProtocolError("proposal.bindings entries must be pairs")
        bindings.append((_text(pair[0], "binding key"), _text(pair[1], "binding value")))
    score = p.get("score", 0.0)
    if type(score) not in (int, float) or not math.isfinite(score):
        raise E12A6UDSProtocolError("proposal.score must be finite")
    proposal = CandidateProposal(
        _text(p["proposal_id"], "proposal_id"),
        _text(p["parent_state_ref"], "parent_state_ref"),
        _text(p["branch_id"], "branch_id"), tuple(bindings),
        _unique_strings(p["evidence_refs"], "proposal.evidence_refs"),
        _unique_strings(p.get("requires", []), "proposal.requires"),
        _unique_strings(p.get("excludes", []), "proposal.excludes"),
        score, _int(p.get("cost", 1), "proposal.cost"),
        _text(p.get("candidate_kind", "UNSPECIFIED"), "candidate_kind"),
    )
    edge = _object(obj["hyperedge"], {"edge_id", "parent_state_ref", "branch_id",
                                      "relation_type", "roles", "evidence_refs"},
                   {"active_from", "active_until"}, "hyperedge")
    roles = []
    for item in _sequence(edge["roles"], "hyperedge.roles"):
        row = _object(item, {"role", "variable", "member_id", "member_type"}, set(), "role")
        roles.append(RoleBinding(_text(row["role"], "role"),
                                 _variable_ref(row["variable"], "role.variable"),
                                 _text(row["member_id"], "member_id"),
                                 _text(row["member_type"], "member_type")))
    variables = tuple(_variable_spec(item) for item in _sequence(obj["variables"], "variables"))
    semantic = _text(obj.get("semantic_status", "CANDIDATE"), "semantic_status")
    return TypedCandidateProposal(
        proposal,
        HyperedgeProposal(
            _text(edge["edge_id"], "edge_id"),
            _text(edge["parent_state_ref"], "edge.parent_state_ref"),
            _text(edge["branch_id"], "edge.branch_id"),
            _text(edge["relation_type"], "relation_type"),
            tuple(roles), _unique_strings(edge["evidence_refs"], "edge.evidence_refs"),
            _optional_int(edge.get("active_from"), "active_from"),
            _optional_int(edge.get("active_until"), "active_until"),
        ),
        variables, _constraints(obj.get("constraints", {})), semantic,
    )


def _branch_snapshot(raw: Any) -> BranchSnapshot:
    obj = _object(raw, {"parent_state_ref", "parent_state_hash", "branch_id",
                        "base_version", "delta_events", "read_set", "write_set",
                        "evidence_refs", "lineage"}, set(), "branch_snapshot")
    deltas = []
    for item in _sequence(obj["delta_events"], "delta_events"):
        row = _object(item, {"event_id", "operation", "target_ref", "before_hash",
                             "after_value", "evidence_refs", "causal_parent", "version"},
                      set(), "branch_delta")
        try:
            operation = DeltaOperation(_text(row["operation"], "delta.operation"))
        except ValueError as exc:
            raise E12A6UDSProtocolError("unsupported delta operation") from exc
        before_hash = row["before_hash"]
        if before_hash is not None:
            before_hash = _text(before_hash, "before_hash")
        causal_parent = row["causal_parent"]
        if causal_parent is not None:
            causal_parent = _text(causal_parent, "causal_parent")
        deltas.append(BranchDelta(
            _text(row["event_id"], "delta.event_id"), operation,
            _text(row["target_ref"], "delta.target_ref"), before_hash,
            _json_value(row["after_value"], "delta.after_value"),
            _unique_strings(row["evidence_refs"], "delta.evidence_refs"),
            causal_parent, _int(row["version"], "delta.version", minimum=1),
        ))
    return BranchSnapshot(
        _text(obj["parent_state_ref"], "parent_state_ref"),
        _text(obj["parent_state_hash"], "parent_state_hash"),
        _text(obj["branch_id"], "branch_id"),
        _int(obj["base_version"], "base_version"),
        tuple(deltas), _unique_strings(obj["read_set"], "read_set"),
        _unique_strings(obj["write_set"], "write_set"),
        _unique_strings(obj["evidence_refs"], "snapshot.evidence_refs"),
        _unique_strings(obj["lineage"], "lineage"),
    )


def _global_constraints(raw: Any) -> GlobalConstraints:
    obj = _object(raw, set(), {"required_bindings", "forbidden_bindings", "max_selected",
                              "max_cost", "max_states", "result_limit"}, "global_constraints")
    def pairs(name: str) -> tuple[tuple[str, str], ...]:
        result = []
        for item in _sequence(obj.get(name, []), name):
            if not isinstance(item, list) or len(item) != 2:
                raise E12A6UDSProtocolError(f"{name} entries must be pairs")
            result.append((_text(item[0], name), _text(item[1], name)))
        return tuple(result)
    return GlobalConstraints(
        pairs("required_bindings"), pairs("forbidden_bindings"),
        _int(obj.get("max_selected", 8), "max_selected", minimum=1, maximum=128),
        _int(obj.get("max_cost", 64), "max_cost", minimum=1, maximum=1_000_000),
        _int(obj.get("max_states", 10_000), "max_states", minimum=1, maximum=1_000_000),
        _int(obj.get("result_limit", 5), "result_limit", minimum=1, maximum=128),
    )


def decode_submit_request(request: dict[str, Any]) -> dict[str, Any]:
    """Decode the only supported operation; reject every unknown schema field."""
    obj = _object(request, {"version", "operation", "scope", "grammar_version",
                            "proposals", "base_state", "branch_snapshots", "receipt"},
                  {"selected_proposal_ids", "constraints"}, "request")
    if _int(obj["version"], "version", minimum=1, maximum=PROTOCOL_VERSION) != PROTOCOL_VERSION:
        raise E12A6UDSProtocolError("unsupported protocol version")
    if _text(obj["operation"], "operation") != SUBMIT_OPERATION:
        raise E12A6UDSProtocolError("unsupported operation")
    proposals = tuple(_typed_proposal(item) for item in _sequence(obj["proposals"], "proposals"))
    snapshots = tuple(_branch_snapshot(item) for item in _sequence(obj["branch_snapshots"], "branch_snapshots"))
    base = _json_value(obj["base_state"], "base_state")
    if not isinstance(base, dict):
        raise E12A6UDSProtocolError("base_state must be an object")
    receipt = _json_value(obj["receipt"], "receipt")
    if not isinstance(receipt, dict):
        raise E12A6UDSProtocolError("receipt must be an object")
    selected = obj.get("selected_proposal_ids")
    if selected is not None:
        selected = _unique_strings(selected, "selected_proposal_ids")
        if not selected:
            raise E12A6UDSProtocolError("selected_proposal_ids cannot be empty")
    return {
        "scope": _text(obj["scope"], "scope"),
        "grammar_version": _text(obj["grammar_version"], "grammar_version"),
        "proposals": proposals,
        "base_state": base,
        "branch_snapshots": snapshots,
        "receipt": receipt,
        "selected_proposal_ids": selected,
        "constraints": _global_constraints(obj.get("constraints", {})),
    }


class E12A6UDSWriterApplication:
    """Own writer runtime and authenticated UDS server with safe shutdown order.

    The caller supplies a fixed peer map and trusted cryptographic dependencies.
    It must run under a dedicated service UID; learner/runner UIDs must not be
    allowlisted and must not have filesystem access to the writer state.
    """

    def __init__(
        self,
        database_path: str | Path,
        socket_path: str | Path,
        *,
        scope: str,
        peer_bindings: tuple[E12A6PeerWorkloadBinding, ...],
        authenticator: E12A6WorkloadAuthenticator,
        receipt_signature_verifier: Callable[[str, str, bytes, str], bool],
        trusted_verifier_id: str,
        allowed_uids: set[int] | frozenset[int],
    ) -> None:
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("scope must be a non-empty string")
        mapping: dict[tuple[int, int], object] = {}
        for binding in peer_bindings:
            if not isinstance(binding, E12A6PeerWorkloadBinding):
                raise TypeError("peer_bindings must contain E12A6PeerWorkloadBinding")
            key = (binding.uid, binding.gid)
            if any(type(value) is not int or value < 0 for value in key) or key in mapping:
                raise ValueError("peer UID/GID bindings must be unique non-negative integers")
            mapping[key] = binding.credential
        if not mapping:
            raise ValueError("at least one server-owned peer binding is required")
        self._scope = scope
        self._mapping = mapping
        self._allowed_uids = frozenset(allowed_uids)
        if any(uid not in self._allowed_uids for uid, _ in mapping):
            raise ValueError("every peer binding UID must also be in allowed_uids")
        self._database_path = Path(database_path)
        self._socket_path = Path(socket_path)
        self._runtime: E12A6WriterRuntime | None = None
        self._server: E12A6UnixSocketServer | None = None
        self._authenticator = authenticator
        self._receipt_signature_verifier = receipt_signature_verifier
        self._trusted_verifier_id = trusted_verifier_id

    def _dispatch(self, peer: E12A6PeerCredentials, request: dict[str, Any]) -> dict[str, Any]:
        credential = self._mapping.get((peer.uid, peer.gid))
        if credential is None:
            raise E12A6IPCError("kernel peer UID/GID has no configured workload binding")
        if self._runtime is None or self._runtime.service is None:
            raise E12A6IPCError("writer runtime is not available")
        decoded = decode_submit_request(request)
        result = self._runtime.service.submit_authorized_merge_candidate(
            credential, **decoded,
        )
        return {
            "authorization_receipt_id": result.authorization_receipt_id,
            "submitter_workload_id": result.submitter_workload_id,
            "proposal_ids": list(result.proposal_ids),
            "replayed": bool(result.lifecycle_receipt.replayed),
        }

    def start(self) -> "E12A6UDSWriterApplication":
        if self._runtime is not None or self._server is not None:
            raise E12A6IPCError("UDS writer application is already started")
        runtime = E12A6WriterRuntime(
            self._database_path,
            authenticator=self._authenticator,
            receipt_signature_verifier=self._receipt_signature_verifier,
            trusted_verifier_id=self._trusted_verifier_id,
            scope=self._scope,
        )
        self._runtime = runtime
        try:
            self._server = E12A6UnixSocketServer(
                self._socket_path, self._dispatch,
                allowed_uids=self._allowed_uids,
            ).start()
        except Exception:
            self._runtime = None
            runtime.close()
            raise
        return self

    def close(self) -> None:
        server = self._server
        if server is not None:
            # If this raises because a dispatcher is still active, retain both
            # references and keep the SQLite runtime/lock alive for a retry.
            server.close()
            self._server = None
        runtime, self._runtime = self._runtime, None
        if runtime is not None:
            runtime.close()

    def __enter__(self) -> "E12A6UDSWriterApplication":
        return self.start()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
