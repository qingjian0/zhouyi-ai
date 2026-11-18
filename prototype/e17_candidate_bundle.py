"""E17 P0 CandidateBundle contracts and guarded publication registry.

This is a small, deterministic governance kernel. It does not discover
candidates, evaluate scientific truth, or execute cognitive programs.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Any, Iterable


class CandidateContractError(ValueError):
    """A candidate or receipt violates the static contract."""


class CandidateStateError(RuntimeError):
    """A candidate lifecycle transition is not permitted."""


class VersionConflictError(RuntimeError):
    """The candidate was built against stale parent versions."""


class BundleKind(str, Enum):
    MEASUREMENT_ONLY = "MEASUREMENT_ONLY"
    PRIMITIVE_ONLY = "PRIMITIVE_ONLY"
    RELATION_ONLY = "RELATION_ONLY"
    MECHANISM_ONLY = "MECHANISM_ONLY"
    PROGRAM_ONLY = "PROGRAM_ONLY"
    CROSS_LAYER = "CROSS_LAYER"


class ChangeLayer(str, Enum):
    MEASUREMENT = "MEASUREMENT"
    PRIMITIVE = "PRIMITIVE"
    RELATION = "RELATION"
    MECHANISM = "MECHANISM"
    PROGRAM = "PROGRAM"


class ChangeOperation(str, Enum):
    CREATE = "CREATE"
    REVISE = "REVISE"
    SPLIT = "SPLIT"
    MERGE = "MERGE"
    RETYPE = "RETYPE"
    REWIRE = "REWIRE"
    SUSPEND = "SUSPEND"
    REPLACE = "REPLACE"


class EvidenceStance(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"


class GateDecision(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class LifecycleState(str, Enum):
    PROPOSED = "PROPOSED"
    STATIC_VALID = "STATIC_VALID"
    STATIC_REJECTED = "STATIC_REJECTED"
    GATE_PENDING = "GATE_PENDING"
    GATE_PASSED = "GATE_PASSED"
    GATE_FAILED = "GATE_FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    DEFERRED = "DEFERRED"
    COMMITTED = "COMMITTED"


@dataclass(frozen=True)
class ResourceEstimate:
    wall_clock_ms: float = 0.0
    cpu_time_ms: float = 0.0
    gpu_time_ms: float = 0.0
    peak_memory_bytes: int = 0
    candidate_count: int = 0
    search_node_count: int = 0
    operator_invocations: int = 0
    storage_delta_bytes: int = 0


@dataclass(frozen=True)
class EvidenceProvenance:
    evidence_id: str
    stance: EvidenceStance
    source_group_id: str | None = None
    acquisition_batch_id: str | None = None
    generator_run_id: str | None = None
    object_id: str | None = None
    scenario_id: str | None = None

    def dependency_keys(self) -> tuple[tuple[str, str], ...]:
        """Keys that imply shared provenance/dependence for conservative counting."""
        fields = (
            ("source_group", self.source_group_id),
            ("acquisition_batch", self.acquisition_batch_id),
            ("generator_run", self.generator_run_id),
            ("object", self.object_id),
            ("scenario", self.scenario_id),
        )
        return tuple((name, value) for name, value in fields if value)


@dataclass(frozen=True)
class ChangeItem:
    change_id: str
    target_layer: ChangeLayer
    operation: ChangeOperation
    target_refs: tuple[str, ...]
    proposed_definition_ref: str
    input_output_contract_ref: str
    preconditions: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    depends_on_change_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateBundle:
    bundle_id: str
    schema_version: str
    kind: BundleKind
    created_at: str
    proposer_id: str
    proposer_version: str
    generation_method: str
    parent_version_refs: tuple[str, ...]
    proposed_version_ref: str
    evidence_snapshot_refs: tuple[str, ...]
    proposed_scope: tuple[tuple[str, str], ...]
    changes: tuple[ChangeItem, ...]
    predicted_effects: tuple[tuple[str, str], ...]
    required_observations: tuple[str, ...]
    validation_plan_refs: tuple[str, ...]
    resource_estimate: ResourceEstimate
    risk_score: float
    provenance: tuple[EvidenceProvenance, ...] = ()

    @property
    def content_digest(self) -> str:
        payload = _canonical_json(self)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ValidationReceipt:
    receipt_id: str
    bundle_id: str
    bundle_digest: str
    parent_version_refs: tuple[str, ...]
    evaluator_id: str
    evaluation_partition_id: str
    independent_gate: bool
    decision: GateDecision
    metrics: tuple[tuple[str, float], ...] = ()
    protocol_deviations: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceIndependenceReport:
    independent_support_groups: int
    independent_counterexample_groups: int
    unknown_provenance_evidence_ids: tuple[str, ...]


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_to_jsonable(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _to_jsonable(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )


def _require_nonempty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CandidateContractError(f"{field} must be a non-empty string")


def _require_unique(values: Iterable[str], field: str) -> None:
    items = tuple(values)
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise CandidateContractError(f"{field} must contain non-empty strings")
    if len(items) != len(set(items)):
        raise CandidateContractError(f"{field} must not contain duplicates")


def validate_candidate_bundle(bundle: CandidateBundle) -> None:
    """Validate structural invariants; this does not establish scientific validity."""
    for field in (
        "bundle_id", "schema_version", "created_at", "proposer_id",
        "proposer_version", "generation_method", "proposed_version_ref",
    ):
        _require_nonempty(getattr(bundle, field), field)

    if not isinstance(bundle.kind, BundleKind):
        raise CandidateContractError("kind must be a BundleKind")
    if not bundle.changes:
        raise CandidateContractError("changes must not be empty")
    if not isinstance(bundle.resource_estimate, ResourceEstimate):
        raise CandidateContractError("resource_estimate must be ResourceEstimate")
    if not math.isfinite(bundle.risk_score) or not 0.0 <= bundle.risk_score <= 1.0:
        raise CandidateContractError("risk_score must be finite and in [0, 1]")

    for field in (
        "parent_version_refs", "evidence_snapshot_refs",
        "required_observations", "validation_plan_refs",
    ):
        _require_unique(getattr(bundle, field), field)

    layers = {change.target_layer for change in bundle.changes}
    expected_layer = {
        BundleKind.MEASUREMENT_ONLY: ChangeLayer.MEASUREMENT,
        BundleKind.PRIMITIVE_ONLY: ChangeLayer.PRIMITIVE,
        BundleKind.RELATION_ONLY: ChangeLayer.RELATION,
        BundleKind.MECHANISM_ONLY: ChangeLayer.MECHANISM,
        BundleKind.PROGRAM_ONLY: ChangeLayer.PROGRAM,
    }
    if bundle.kind is BundleKind.CROSS_LAYER:
        if len(layers) < 2:
            raise CandidateContractError("CROSS_LAYER bundle must change at least two layers")
    elif layers != {expected_layer[bundle.kind]}:
        raise CandidateContractError("bundle kind does not match its change layers")

    change_ids = tuple(change.change_id for change in bundle.changes)
    _require_unique(change_ids, "change_ids")
    known_change_ids = set(change_ids)
    for change in bundle.changes:
        _require_nonempty(change.change_id, "change_id")
        _require_nonempty(change.proposed_definition_ref, "proposed_definition_ref")
        _require_nonempty(change.input_output_contract_ref, "input_output_contract_ref")
        if not isinstance(change.target_layer, ChangeLayer):
            raise CandidateContractError("target_layer must be a ChangeLayer")
        if not isinstance(change.operation, ChangeOperation):
            raise CandidateContractError("operation must be a ChangeOperation")
        _require_unique(change.target_refs, "target_refs")
        _require_unique(change.preconditions, "preconditions")
        _require_unique(change.effects, "effects")
        _require_unique(change.evidence_refs, "evidence_refs")
        _require_unique(change.depends_on_change_ids, "depends_on_change_ids")
        unknown = set(change.depends_on_change_ids) - known_change_ids
        if unknown:
            raise CandidateContractError(
                f"change {change.change_id} has unknown dependencies: {sorted(unknown)}"
            )
        if change.change_id in change.depends_on_change_ids:
            raise CandidateContractError("a change cannot depend on itself")

    # Detect cycles in the intra-bundle change dependency graph.
    graph = {change.change_id: change.depends_on_change_ids for change in bundle.changes}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise CandidateContractError("change dependency graph contains a cycle")
        if node in visited:
            return
        visiting.add(node)
        for parent in graph[node]:
            visit(parent)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)

    for key, value in bundle.proposed_scope:
        _require_nonempty(key, "proposed_scope key")
        _require_nonempty(value, "proposed_scope value")
    for key, value in bundle.predicted_effects:
        _require_nonempty(key, "predicted_effect key")
        _require_nonempty(value, "predicted_effect value")

    numeric_resources = (
        bundle.resource_estimate.wall_clock_ms,
        bundle.resource_estimate.cpu_time_ms,
        bundle.resource_estimate.gpu_time_ms,
    )
    if any(not math.isfinite(value) or value < 0 for value in numeric_resources):
        raise CandidateContractError("resource time estimates must be finite and non-negative")
    integer_resources = (
        bundle.resource_estimate.peak_memory_bytes,
        bundle.resource_estimate.candidate_count,
        bundle.resource_estimate.search_node_count,
        bundle.resource_estimate.operator_invocations,
        bundle.resource_estimate.storage_delta_bytes,
    )
    if any(not isinstance(value, int) or value < 0 for value in integer_resources):
        raise CandidateContractError("integer resource estimates must be non-negative integers")

    evidence_ids = tuple(item.evidence_id for item in bundle.provenance)
    _require_unique(evidence_ids, "provenance evidence_ids")
    for item in bundle.provenance:
        _require_nonempty(item.evidence_id, "evidence_id")
        if not isinstance(item.stance, EvidenceStance):
            raise CandidateContractError("evidence stance must be EvidenceStance")


def _count_provenance_components(items: tuple[EvidenceProvenance, ...]
                                 ) -> tuple[int, tuple[str, ...]]:
    """Count conservative connected components over shared provenance keys."""
    parent = list(range(len(items)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[b] = a

    owner_by_key: dict[tuple[str, str], int] = {}
    unknown: list[str] = []
    for index, item in enumerate(items):
        keys = item.dependency_keys()
        if not keys:
            unknown.append(item.evidence_id)
        for key in keys:
            previous = owner_by_key.get(key)
            if previous is None:
                owner_by_key[key] = index
            else:
                union(index, previous)

    known_indices = [i for i, item in enumerate(items) if item.dependency_keys()]
    return len({find(i) for i in known_indices}), tuple(sorted(unknown))


def assess_evidence_independence(
    provenance: Iterable[EvidenceProvenance],
) -> EvidenceIndependenceReport:
    items = tuple(provenance)
    support = tuple(item for item in items if item.stance is EvidenceStance.SUPPORTS)
    counter = tuple(item for item in items if item.stance is EvidenceStance.CONTRADICTS)
    support_count, support_unknown = _count_provenance_components(support)
    counter_count, counter_unknown = _count_provenance_components(counter)
    return EvidenceIndependenceReport(
        independent_support_groups=support_count,
        independent_counterexample_groups=counter_count,
        unknown_provenance_evidence_ids=tuple(sorted(support_unknown + counter_unknown)),
    )


class CandidateRegistry:
    """Append-only candidate lifecycle with guarded, optimistic publication."""

    _TRANSITIONS = {
        LifecycleState.PROPOSED: {
            LifecycleState.STATIC_VALID, LifecycleState.STATIC_REJECTED,
            LifecycleState.DEFERRED,
        },
        LifecycleState.STATIC_VALID: {
            LifecycleState.GATE_PENDING, LifecycleState.DEFERRED,
        },
        LifecycleState.GATE_PENDING: {
            LifecycleState.GATE_PASSED, LifecycleState.GATE_FAILED,
            LifecycleState.INCONCLUSIVE, LifecycleState.DEFERRED,
        },
        LifecycleState.GATE_PASSED: {LifecycleState.COMMITTED},
        LifecycleState.STATIC_REJECTED: set(),
        LifecycleState.GATE_FAILED: set(),
        LifecycleState.INCONCLUSIVE: set(),
        LifecycleState.DEFERRED: set(),
        LifecycleState.COMMITTED: set(),
    }

    def __init__(
        self,
        active_version_refs: Iterable[str] = (),
        trusted_gate_evaluator_ids: Iterable[str] = (),
    ) -> None:
        self._active_version_refs = set(active_version_refs)
        self._trusted_gate_evaluator_ids = frozenset(trusted_gate_evaluator_ids)
        if any(not isinstance(item, str) or not item.strip()
               for item in self._trusted_gate_evaluator_ids):
            raise CandidateContractError("trusted gate evaluator ids must be non-empty strings")
        self._bundles: dict[str, CandidateBundle] = {}
        self._states: dict[str, LifecycleState] = {}
        self._receipts: dict[str, ValidationReceipt] = {}
        self._events: list[dict[str, Any]] = []

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(copy.deepcopy(event) for event in self._events)

    @property
    def active_version_refs(self) -> frozenset[str]:
        """Read-only view; callers cannot bypass publication through set mutation."""
        return frozenset(self._active_version_refs)

    def advance_version_projection(
        self, parent_version_refs: Iterable[str], new_version_ref: str
    ) -> None:
        """Apply a separate committed version, useful for conflict/concurrency handling."""
        parents = tuple(parent_version_refs)
        _require_unique(parents, "parent_version_refs")
        _require_nonempty(new_version_ref, "new_version_ref")
        missing = set(parents) - self._active_version_refs
        if missing:
            raise VersionConflictError(
                f"cannot advance from inactive parent versions: {sorted(missing)}"
            )
        if new_version_ref in self._active_version_refs:
            raise VersionConflictError("new version reference is already active")
        next_active = set(self._active_version_refs)
        next_active.difference_update(parents)
        next_active.add(new_version_ref)
        self._active_version_refs = next_active
        self._events.append({
            "event": "EXTERNAL_VERSION_ADVANCE",
            "parent_version_refs": list(parents),
            "new_version_ref": new_version_ref,
        })

    def state_of(self, bundle_id: str) -> LifecycleState:
        if bundle_id not in self._states:
            raise CandidateStateError("unknown bundle_id")
        return self._states[bundle_id]

    def propose(self, bundle: CandidateBundle) -> str:
        validate_candidate_bundle(bundle)
        if bundle.bundle_id in self._bundles:
            raise CandidateContractError("bundle_id already exists")
        if bundle.proposed_version_ref in self.active_version_refs:
            raise CandidateContractError("proposed_version_ref is already active")
        self._bundles[bundle.bundle_id] = bundle
        self._states[bundle.bundle_id] = LifecycleState.PROPOSED
        self._events.append({
            "event": "PROPOSED", "bundle_id": bundle.bundle_id,
            "bundle_digest": bundle.content_digest,
        })
        return bundle.content_digest

    def _transition(self, bundle_id: str, target: LifecycleState,
                    details: dict[str, Any] | None = None) -> None:
        current = self.state_of(bundle_id)
        if target not in self._TRANSITIONS[current]:
            raise CandidateStateError(
                f"invalid lifecycle transition: {current.value} -> {target.value}"
            )
        self._states[bundle_id] = target
        self._events.append({
            "event": target.value, "bundle_id": bundle_id,
            "details": dict(details or {}),
        })

    def static_validate(self, bundle_id: str) -> None:
        bundle = self._bundles.get(bundle_id)
        if bundle is None:
            raise CandidateStateError("unknown bundle_id")
        try:
            validate_candidate_bundle(bundle)
        except CandidateContractError as exc:
            self._transition(bundle_id, LifecycleState.STATIC_REJECTED,
                             {"reason": str(exc)})
            raise
        self._transition(bundle_id, LifecycleState.STATIC_VALID)

    def submit_for_gate(self, bundle_id: str) -> None:
        self._transition(bundle_id, LifecycleState.GATE_PENDING)

    def record_gate_receipt(self, receipt: ValidationReceipt) -> None:
        if receipt.bundle_id not in self._bundles:
            raise CandidateStateError("receipt references unknown bundle")
        if self.state_of(receipt.bundle_id) is not LifecycleState.GATE_PENDING:
            raise CandidateStateError("bundle is not waiting for independent gate")
        bundle = self._bundles[receipt.bundle_id]
        if receipt.receipt_id in self._receipts:
            raise CandidateContractError("receipt_id already exists")
        if receipt.bundle_digest != bundle.content_digest:
            raise CandidateContractError("receipt digest does not match frozen bundle")
        if receipt.parent_version_refs != bundle.parent_version_refs:
            raise CandidateContractError("receipt parent versions do not match bundle")
        if not receipt.evaluator_id or receipt.evaluator_id == bundle.proposer_id:
            raise CandidateContractError("gate evaluator must be distinct from proposer")
        if receipt.evaluator_id not in self._trusted_gate_evaluator_ids:
            raise CandidateContractError("gate evaluator is not in the trusted evaluator allowlist")
        if not receipt.evaluation_partition_id:
            raise CandidateContractError("evaluation partition id is required")
        if receipt.independent_gate is not True:
            raise CandidateContractError("receipt is not from an independent gate")
        if not isinstance(receipt.decision, GateDecision):
            raise CandidateContractError("receipt decision must be GateDecision")
        metric_names = [name for name, _ in receipt.metrics]
        _require_unique(metric_names, "receipt metric names")
        if any(not math.isfinite(value) for _, value in receipt.metrics):
            raise CandidateContractError("receipt metrics must be finite")
        self._receipts[receipt.receipt_id] = receipt
        target = {
            GateDecision.PASS: LifecycleState.GATE_PASSED,
            GateDecision.FAIL: LifecycleState.GATE_FAILED,
            GateDecision.INCONCLUSIVE: LifecycleState.INCONCLUSIVE,
        }[receipt.decision]
        self._transition(receipt.bundle_id, target, {
            "receipt_id": receipt.receipt_id,
            "evaluation_partition_id": receipt.evaluation_partition_id,
            "decision": receipt.decision.value,
        })

    def commit(self, bundle_id: str) -> str:
        if self.state_of(bundle_id) is not LifecycleState.GATE_PASSED:
            raise CandidateStateError("only independently gate-passed bundles can commit")
        bundle = self._bundles[bundle_id]
        missing = set(bundle.parent_version_refs) - self.active_version_refs
        if missing:
            self._events.append({
                "event": "COMMIT_CONFLICT", "bundle_id": bundle_id,
                "missing_parent_versions": sorted(missing),
            })
            raise VersionConflictError(
                f"parent versions are stale or inactive: {sorted(missing)}"
            )
        if bundle.proposed_version_ref in self.active_version_refs:
            raise VersionConflictError("proposed version reference is already active")

        # Validate all conditions before mutating the active projection.
        new_active = set(self.active_version_refs)
        new_active.difference_update(bundle.parent_version_refs)
        new_active.add(bundle.proposed_version_ref)

        self._active_version_refs = new_active
        self._transition(bundle_id, LifecycleState.COMMITTED, {
            "published_version_ref": bundle.proposed_version_ref,
            "replaced_parent_version_refs": list(bundle.parent_version_refs),
        })
        return bundle.proposed_version_ref

    def bundle(self, bundle_id: str) -> CandidateBundle:
        try:
            return self._bundles[bundle_id]
        except KeyError as exc:
            raise CandidateStateError("unknown bundle_id") from exc

    def receipt(self, receipt_id: str) -> ValidationReceipt:
        try:
            return self._receipts[receipt_id]
        except KeyError as exc:
            raise CandidateStateError("unknown receipt_id") from exc
