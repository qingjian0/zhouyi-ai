"""Authenticated UDS RPC for the sole E12-A6 lifecycle writer."""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
import math
from typing import Any, Callable, Mapping

from prototype.csg_branch_delta import BranchDelta, BranchSnapshot, DeltaOperation
from prototype.csg_gcr_coordinator import CandidateProposal, GlobalConstraints
from prototype.e12a6_writer_service import (
    E12A6AuthenticatedWorkload,
    E12A6AuthenticationError,
    E12A6AuthorizationError,
    E12A6WriterService,
)
from prototype.typed_csg_gcr import TypedCandidateProposal
from prototype.typed_hypergraph_unifier import (
    HyperedgeProposal,
    RoleBinding,
    RoleRequirement,
    UnificationConstraints,
    VariableRef,
    VariableRelation,
    VariableSpec,
)
from prototype.unix_ipc import (
    IPCRequestContext,
    IPCRequestError,
    UnixJSONRPCServer,
    UnixPeerIdentity,
    UnixPeerResolver,
)


class UnixPeerE12A6Authenticator:
    """Map kernel-derived UDS identities to provisioned E12-A6 workload claims."""

    def __init__(self, principals: Mapping[str, E12A6AuthenticatedWorkload]) -> None:
        if not principals:
            raise ValueError("at least one E12-A6 workload principal is required")
        normalized = {}
        for workload_id, principal in principals.items():
            if not isinstance(workload_id, str) or not workload_id.strip():
                raise ValueError("workload IDs must be non-empty strings")
            if not isinstance(principal, E12A6AuthenticatedWorkload):
                raise TypeError("principal map values must be E12A6AuthenticatedWorkload")
            if principal.workload_id != workload_id:
                raise ValueError("principal map key must match workload_id")
            normalized[workload_id] = principal
        self._principals = normalized

    def authenticate(self, credential: object) -> E12A6AuthenticatedWorkload:
        if not isinstance(credential, UnixPeerIdentity):
            raise E12A6AuthenticationError("credential did not originate from Unix peer authentication")
        principal = self._principals.get(credential.workload_id)
        if principal is None:
            raise E12A6AuthenticationError("Unix peer workload is not provisioned")
        if principal.roles != credential.roles or principal.scopes != credential.scopes:
            raise E12A6AuthenticationError("Unix peer roles/scopes do not match Writer policy")
        return principal


def _fields(value: Any, required: set[str], optional: set[str] = frozenset(), field: str = "object") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IPCRequestError("invalid_body", f"{field} must be an object")
    if required - set(value) or set(value) - required - optional:
        raise IPCRequestError("invalid_body", f"{field} fields do not match the RPC schema")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IPCRequestError("invalid_body", f"{field} must be a non-empty string")
    return value


def _string_list(value: Any, field: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise IPCRequestError("invalid_body", f"{field} must be a JSON array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise IPCRequestError("invalid_body", f"{field} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise IPCRequestError("invalid_body", f"{field} must not contain duplicates")
    return tuple(value)


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise IPCRequestError("invalid_body", f"{field} must be an integer >= {minimum}")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise IPCRequestError("invalid_body", f"{field} must be a finite number")
    return float(value)


def _variable_ref(value: Any, field: str) -> VariableRef:
    obj = _fields(value, {"namespace", "name"}, field=field)
    return VariableRef(_text(obj["namespace"], field + ".namespace"), _text(obj["name"], field + ".name"))


def _pairs(value: Any, field: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise IPCRequestError("invalid_body", f"{field} must be an array of string pairs")
    result = []
    for index, item in enumerate(value):
        if not isinstance(item, list) or len(item) != 2:
            raise IPCRequestError("invalid_body", f"{field}[{index}] must be a two-item array")
        result.append((_text(item[0], field), _text(item[1], field)))
    return tuple(result)


def _parse_candidate_proposal(value: Any) -> CandidateProposal:
    obj = _fields(
        value,
        {"proposal_id", "parent_state_ref", "branch_id", "bindings", "evidence_refs"},
        {"requires", "excludes", "score", "cost", "candidate_kind"},
        "proposal",
    )
    return CandidateProposal(
        proposal_id=_text(obj["proposal_id"], "proposal.proposal_id"),
        parent_state_ref=_text(obj["parent_state_ref"], "proposal.parent_state_ref"),
        branch_id=_text(obj["branch_id"], "proposal.branch_id"),
        bindings=_pairs(obj["bindings"], "proposal.bindings"),
        evidence_refs=_string_list(obj["evidence_refs"], "proposal.evidence_refs"),
        requires=_string_list(obj.get("requires", []), "proposal.requires"),
        excludes=_string_list(obj.get("excludes", []), "proposal.excludes"),
        score=_number(obj.get("score", 0.0), "proposal.score"),
        cost=_integer(obj.get("cost", 1), "proposal.cost"),
        candidate_kind=_text(obj.get("candidate_kind", "UNSPECIFIED"), "proposal.candidate_kind"),
    )


def _parse_hyperedge(value: Any) -> HyperedgeProposal:
    obj = _fields(
        value,
        {"edge_id", "parent_state_ref", "branch_id", "relation_type", "roles", "evidence_refs"},
        {"active_from", "active_until"},
        "hyperedge",
    )
    if not isinstance(obj["roles"], list):
        raise IPCRequestError("invalid_body", "hyperedge.roles must be an array")
    roles = []
    for index, raw in enumerate(obj["roles"]):
        row = _fields(raw, {"role", "variable", "member_id", "member_type"}, field=f"hyperedge.roles[{index}]")
        roles.append(RoleBinding(
            _text(row["role"], "role"),
            _variable_ref(row["variable"], "role.variable"),
            _text(row["member_id"], "role.member_id"),
            _text(row["member_type"], "role.member_type"),
        ))
    active_from = None if obj.get("active_from") is None else _integer(obj["active_from"], "active_from")
    active_until = None if obj.get("active_until") is None else _integer(obj["active_until"], "active_until")
    return HyperedgeProposal(
        edge_id=_text(obj["edge_id"], "hyperedge.edge_id"),
        parent_state_ref=_text(obj["parent_state_ref"], "hyperedge.parent_state_ref"),
        branch_id=_text(obj["branch_id"], "hyperedge.branch_id"),
        relation_type=_text(obj["relation_type"], "hyperedge.relation_type"),
        roles=tuple(roles),
        evidence_refs=_string_list(obj["evidence_refs"], "hyperedge.evidence_refs"),
        active_from=active_from,
        active_until=active_until,
    )


def _parse_variables(value: Any) -> tuple[VariableSpec, ...]:
    if not isinstance(value, list):
        raise IPCRequestError("invalid_body", "variables must be an array")
    result = []
    for index, raw in enumerate(value):
        row = _fields(raw, {"ref", "value_type"}, {"required"}, f"variables[{index}]")
        required = row.get("required", True)
        if not isinstance(required, bool):
            raise IPCRequestError("invalid_body", "VariableSpec.required must be boolean")
        result.append(VariableSpec(
            _variable_ref(row["ref"], "variables.ref"),
            _text(row["value_type"], "variables.value_type"),
            required,
        ))
    return tuple(result)


def _parse_constraints(value: Any) -> UnificationConstraints:
    obj = _fields(value, set(), {"equal", "not_equal", "role_requirements", "subtype_of"}, "unification constraints")
    relations = {}
    for name in ("equal", "not_equal"):
        raw_rows = obj.get(name, [])
        if not isinstance(raw_rows, list):
            raise IPCRequestError("invalid_body", f"constraints.{name} must be an array")
        parsed = []
        for index, raw in enumerate(raw_rows):
            row = _fields(raw, {"left", "right"}, field=f"constraints.{name}[{index}]")
            parsed.append(VariableRelation(
                _variable_ref(row["left"], f"{name}.left"),
                _variable_ref(row["right"], f"{name}.right"),
            ))
        relations[name] = tuple(parsed)
    raw_requirements = obj.get("role_requirements", [])
    if not isinstance(raw_requirements, list):
        raise IPCRequestError("invalid_body", "constraints.role_requirements must be an array")
    requirements = []
    for index, raw in enumerate(raw_requirements):
        row = _fields(raw, {"relation_type", "role"}, {"required", "allowed_member_types"}, f"role_requirements[{index}]")
        required = row.get("required", True)
        if not isinstance(required, bool):
            raise IPCRequestError("invalid_body", "RoleRequirement.required must be boolean")
        requirements.append(RoleRequirement(
            _text(row["relation_type"], "role_requirement.relation_type"),
            _text(row["role"], "role_requirement.role"),
            required,
            _string_list(row.get("allowed_member_types", []), "allowed_member_types"),
        ))
    raw_subtypes = obj.get("subtype_of", [])
    if not isinstance(raw_subtypes, list):
        raise IPCRequestError("invalid_body", "constraints.subtype_of must be an array")
    subtypes = []
    for index, pair in enumerate(raw_subtypes):
        if not isinstance(pair, list) or len(pair) != 2:
            raise IPCRequestError("invalid_body", f"subtype_of[{index}] must be a two-item array")
        subtypes.append((_text(pair[0], "subtype child"), _text(pair[1], "subtype parent")))
    return UnificationConstraints(
        equal=relations["equal"],
        not_equal=relations["not_equal"],
        role_requirements=tuple(requirements),
        subtype_of=tuple(subtypes),
    )


def _parse_typed_proposal(value: Any) -> TypedCandidateProposal:
    obj = _fields(value, {"proposal", "hyperedge", "variables"}, {"constraints"}, "typed proposal")
    return TypedCandidateProposal(
        proposal=_parse_candidate_proposal(obj["proposal"]),
        hyperedge=_parse_hyperedge(obj["hyperedge"]),
        variables=_parse_variables(obj["variables"]),
        constraints=_parse_constraints(obj.get("constraints", {})),
    )


def _parse_branch_delta(value: Any) -> BranchDelta:
    obj = _fields(
        value,
        {"event_id", "operation", "target_ref", "before_hash", "after_value", "evidence_refs", "causal_parent", "version"},
        set(),
        "branch delta",
    )
    try:
        operation = DeltaOperation(_text(obj["operation"], "delta.operation"))
    except ValueError as exc:
        raise IPCRequestError("invalid_body", "delta.operation is not supported") from exc
    before_hash = obj["before_hash"]
    if before_hash is not None and (not isinstance(before_hash, str) or not before_hash.strip()):
        raise IPCRequestError("invalid_body", "delta.before_hash must be a non-empty string or null")
    causal_parent = obj["causal_parent"]
    if causal_parent is not None and (not isinstance(causal_parent, str) or not causal_parent.strip()):
        raise IPCRequestError("invalid_body", "delta.causal_parent must be a non-empty string or null")
    return BranchDelta(
        _text(obj["event_id"], "delta.event_id"), operation,
        _text(obj["target_ref"], "delta.target_ref"), before_hash,
        obj["after_value"], _string_list(obj["evidence_refs"], "delta.evidence_refs"),
        causal_parent, _integer(obj["version"], "delta.version"),
    )


def _parse_branch_snapshot(value: Any) -> BranchSnapshot:
    obj = _fields(
        value,
        {"parent_state_ref", "parent_state_hash", "branch_id", "base_version", "delta_events",
         "read_set", "write_set", "evidence_refs", "lineage"},
        set(),
        "branch snapshot",
    )
    if not isinstance(obj["delta_events"], list):
        raise IPCRequestError("invalid_body", "snapshot.delta_events must be an array")
    return BranchSnapshot(
        _text(obj["parent_state_ref"], "snapshot.parent_state_ref"),
        _text(obj["parent_state_hash"], "snapshot.parent_state_hash"),
        _text(obj["branch_id"], "snapshot.branch_id"),
        _integer(obj["base_version"], "snapshot.base_version"),
        tuple(_parse_branch_delta(item) for item in obj["delta_events"]),
        _string_list(obj["read_set"], "snapshot.read_set"),
        _string_list(obj["write_set"], "snapshot.write_set"),
        _string_list(obj["evidence_refs"], "snapshot.evidence_refs"),
        _string_list(obj["lineage"], "snapshot.lineage"),
    )


def _parse_global_constraints(value: Any) -> GlobalConstraints:
    obj = _fields(
        value, set(),
        {"required_bindings", "forbidden_bindings", "max_selected", "max_cost", "max_states", "result_limit"},
        "global constraints",
    )
    return GlobalConstraints(
        required_bindings=_pairs(obj.get("required_bindings", []), "constraints.required_bindings"),
        forbidden_bindings=_pairs(obj.get("forbidden_bindings", []), "constraints.forbidden_bindings"),
        max_selected=_integer(obj.get("max_selected", 8), "constraints.max_selected", minimum=1),
        max_cost=_integer(obj.get("max_cost", 64), "constraints.max_cost"),
        max_states=_integer(obj.get("max_states", 10_000), "constraints.max_states", minimum=1),
        result_limit=_integer(obj.get("result_limit", 5), "constraints.result_limit", minimum=1),
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value):
        return {item.name: _jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported writer response type: {type(value).__name__}")


class E12A6WriterUnixRPC:
    """Expose only the authenticated atomic candidate bundle operation."""

    def __init__(
        self,
        writer: E12A6WriterService,
        *,
        peer_resolver: UnixPeerResolver,
        socket_path: str,
        authenticator: UnixPeerE12A6Authenticator,
        socket_mode: int = 0o660,
    ) -> None:
        if not isinstance(writer, E12A6WriterService):
            raise TypeError("writer must be E12A6WriterService")
        if not callable(getattr(authenticator, "authenticate", None)):
            raise TypeError("authenticator must implement authenticate")
        self.writer = writer
        self.authenticator = authenticator
        self.server = UnixJSONRPCServer(
            socket_path,
            peer_resolver=peer_resolver,
            handlers={
                "health": self._health,
                "candidate.submit_authorized_merge": self._submit,
            },
            socket_mode=socket_mode,
        )

    @staticmethod
    def _health(context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
        _fields(body, set(), field="health")
        if "candidate_submitter" not in context.peer.roles:
            raise IPCRequestError("permission_denied", "Peer is not an authorized candidate submitter")
        return {"service": "e12a6-writer", "protocol": "zhouyi-ipc/1", "ready": True}

    def _submit(self, context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
        required = {"proposals", "base_state", "branch_snapshots", "receipt", "scope", "grammar_version"}
        optional = {"selected_proposal_ids", "constraints"}
        _fields(body, required, optional, "candidate submission")
        scope = _text(body["scope"], "scope")
        if scope not in context.peer.scopes or "candidate_submitter" not in context.peer.roles:
            raise IPCRequestError("permission_denied", "Peer is not authorized for candidate submission")
        try:
            principal = self.authenticator.authenticate(context.peer)
        except E12A6AuthenticationError as exc:
            raise IPCRequestError("authentication_failed", "Writer workload authentication failed") from exc
        if principal.workload_id != context.peer.workload_id or principal.roles != context.peer.roles or principal.scopes != context.peer.scopes:
            raise IPCRequestError("authentication_failed", "Writer peer identity does not match configured workload policy")
        if not isinstance(body["proposals"], list) or not body["proposals"]:
            raise IPCRequestError("invalid_body", "proposals must be a non-empty array")
        if not isinstance(body["branch_snapshots"], list) or not body["branch_snapshots"]:
            raise IPCRequestError("invalid_body", "branch_snapshots must be a non-empty array")
        if not isinstance(body["base_state"], dict):
            raise IPCRequestError("invalid_body", "base_state must be an object")
        if not isinstance(body["receipt"], dict):
            raise IPCRequestError("invalid_body", "receipt must be an object")
        proposals = tuple(_parse_typed_proposal(item) for item in body["proposals"])
        snapshots = tuple(_parse_branch_snapshot(item) for item in body["branch_snapshots"])
        selected = None
        if "selected_proposal_ids" in body:
            selected = _string_list(body["selected_proposal_ids"], "selected_proposal_ids", allow_empty=False)
        constraints = _parse_global_constraints(body.get("constraints", {}))
        grammar_version = _text(body["grammar_version"], "grammar_version")
        receipt_id = _text(body["receipt"].get("receipt_id"), "receipt.receipt_id")
        if context.operation_id != receipt_id:
            raise IPCRequestError("invalid_operation_id", "operation_id must equal the signed receipt_id")
        try:
            result = self.writer.submit_authorized_merge_candidate(
                context.peer,
                proposals=proposals,
                base_state=body["base_state"],
                branch_snapshots=snapshots,
                receipt=body["receipt"],
                scope=scope,
                grammar_version=grammar_version,
                selected_proposal_ids=selected,
                constraints=constraints,
            )
        except E12A6AuthenticationError as exc:
            raise IPCRequestError("authentication_failed", "Writer workload authentication failed") from exc
        except E12A6AuthorizationError as exc:
            raise IPCRequestError("permission_denied", "Candidate submission was rejected by Writer policy") from exc
        except (TypeError, ValueError) as exc:
            raise IPCRequestError("invalid_request", "Candidate submission failed validation") from exc
        return _jsonable(result)

    def start(self) -> None:
        self.server.start()

    def close(self) -> None:
        self.server.close()

    def __enter__(self) -> "E12A6WriterUnixRPC":
        self.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
