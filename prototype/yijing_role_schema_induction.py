"""YJ-07: bounded, alpha-invariant induction of structural roles and schemas.

The first baseline uses directed, edge-labelled Weisfeiler-Lehman refinement.
It ignores caller-supplied role names and concrete entity IDs. It proposes
structural equivalence classes and typed relation schemas; it does not infer
causal roles or claim that structural equivalence implies semantic identity.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from typing import Iterable

from prototype.yijing_operator_induction import RelationalState


class RoleSchemaInductionError(ValueError):
    """Invalid graph evidence or bounded-induction configuration."""


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


@dataclass(frozen=True)
class InferredRole:
    entity_id: str
    role_id: str
    entity_type: str
    refinement_round: int
    structural_signature: str


@dataclass(frozen=True)
class RoleInductionResult:
    assignments: tuple[InferredRole, ...]
    role_count: int
    refinement_rounds: int
    stabilized: bool


def infer_structural_roles(
    state: RelationalState, *, max_rounds: int = 3
) -> RoleInductionResult:
    """Infer alpha-invariant role classes using directed labelled neighborhoods.

    Existing Node.role values and entity IDs are deliberately excluded from
    role signatures. Context is also excluded in v0.1 to avoid turning
    transient episode context into an identity-defining role feature.
    """
    if max_rounds < 0 or max_rounds > 8:
        raise RoleSchemaInductionError("max_rounds must be between 0 and 8")
    nodes = {node.entity_id: node for node in state.nodes}
    outgoing: dict[str, list[tuple[str, str]]] = defaultdict(list)
    incoming: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for relation in state.relations:
        outgoing[relation.source].append((relation.relation_type, relation.target))
        incoming[relation.target].append((relation.relation_type, relation.source))

    colors = {node_id: _digest(("entity", node.entity_type)) for node_id, node in nodes.items()}
    def partition_signature(values):
        groups: dict[str, list[str]] = defaultdict(list)
        for entity_id, color in values.items():
            groups[color].append(entity_id)
        return tuple(sorted(tuple(sorted(group)) for group in groups.values()))

    stabilized = False
    previous_partition = partition_signature(colors)
    rounds_done = 0
    for round_index in range(max_rounds):
        next_colors = {}
        for node_id, node in nodes.items():
            out_profile = sorted(
                (relation_type, colors[target])
                for relation_type, target in outgoing[node_id]
            )
            in_profile = sorted(
                (relation_type, colors[source])
                for relation_type, source in incoming[node_id]
            )
            signature = (
                "wl-directed-v1", node.entity_type, colors[node_id],
                tuple(out_profile), tuple(in_profile),
            )
            next_colors[node_id] = _digest(signature)
        rounds_done = round_index + 1
        next_partition = partition_signature(next_colors)
        if next_partition == previous_partition:
            stabilized = True
        previous_partition = next_partition
        colors = next_colors

    assignments = tuple(sorted(
        (
            InferredRole(
                entity_id=node_id,
                role_id="role-" + colors[node_id],
                entity_type=node.entity_type,
                refinement_round=rounds_done,
                structural_signature=colors[node_id],
            )
            for node_id, node in nodes.items()
        ),
        key=lambda item: item.entity_id,
    ))
    return RoleInductionResult(
        assignments=assignments,
        role_count=len({item.role_id for item in assignments}),
        refinement_rounds=rounds_done,
        stabilized=stabilized,
    )


@dataclass(frozen=True)
class RoleSchemaObservation:
    state: RelationalState
    evidence_id: str
    domain: str

    def __post_init__(self):
        if not self.evidence_id or not self.domain:
            raise RoleSchemaInductionError("evidence_id and domain are required")


@dataclass(frozen=True)
class RelationSchemaHypothesis:
    schema_id: str
    relation_type: str
    source_role_id: str
    target_role_id: str
    source_entity_type: str
    target_entity_type: str
    support_evidence_ids: tuple[str, ...]
    domains: tuple[str, ...]


@dataclass(frozen=True)
class SchemaDiscoveryReport:
    hypotheses: tuple[RelationSchemaHypothesis, ...]
    observations_seen: int
    relation_instances_seen: int
    budget_exhausted: bool


@dataclass(frozen=True)
class SchemaStabilityReport:
    candidate_ids: tuple[str, ...]
    heldout_ids: tuple[str, ...]
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    relation_coverage: float


class StructuralSchemaInducer:
    """Discover repeated directed relation schemas over inferred structural roles."""

    def __init__(self, *, min_support: int = 2, max_hypotheses: int = 512, max_rounds: int = 3):
        if min_support < 1 or max_hypotheses < 1:
            raise RoleSchemaInductionError("support and hypothesis budgets must be positive")
        if max_rounds < 0 or max_rounds > 8:
            raise RoleSchemaInductionError("max_rounds must be between 0 and 8")
        self.min_support = min_support
        self.max_hypotheses = max_hypotheses
        self.max_rounds = max_rounds

    def discover(self, observations: Iterable[RoleSchemaObservation]) -> SchemaDiscoveryReport:
        rows = tuple(observations)
        if not rows:
            raise RoleSchemaInductionError("at least one observation is required")
        evidence_ids = [row.evidence_id for row in rows]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise RoleSchemaInductionError("evidence IDs must be unique within a discovery batch")

        grouped: dict[tuple[str, str, str, str, str], dict[str, set[str]]] = {}
        relation_instances = 0
        for row in rows:
            role_by_entity = {
                item.entity_id: item
                for item in infer_structural_roles(row.state, max_rounds=self.max_rounds).assignments
            }
            seen_in_observation = set()
            for relation in row.state.relations:
                source = role_by_entity[relation.source]
                target = role_by_entity[relation.target]
                key = (
                    relation.relation_type,
                    source.role_id,
                    target.role_id,
                    source.entity_type,
                    target.entity_type,
                )
                seen_in_observation.add(key)
                relation_instances += 1
            for key in seen_in_observation:
                bucket = grouped.setdefault(key, {"evidence": set(), "domains": set()})
                bucket["evidence"].add(row.evidence_id)
                bucket["domains"].add(row.domain)

        ordered = sorted(grouped.items(), key=lambda item: item[0])
        eligible = [
            (key, value) for key, value in ordered
            if len(value["evidence"]) >= self.min_support
        ]
        exhausted = len(eligible) > self.max_hypotheses
        hypotheses = []
        for key, value in eligible[:self.max_hypotheses]:
            relation_type, source_role, target_role, source_type, target_type = key
            schema_id = "schema-" + _digest(key)
            hypotheses.append(RelationSchemaHypothesis(
                schema_id=schema_id,
                relation_type=relation_type,
                source_role_id=source_role,
                target_role_id=target_role,
                source_entity_type=source_type,
                target_entity_type=target_type,
                support_evidence_ids=tuple(sorted(value["evidence"])),
                domains=tuple(sorted(value["domains"])),
            ))
        return SchemaDiscoveryReport(
            tuple(hypotheses), len(rows), relation_instances, exhausted
        )


def evaluate_schema_stability(
    candidates: Iterable[RelationSchemaHypothesis],
    heldout: Iterable[RoleSchemaObservation],
    *,
    max_rounds: int = 3,
) -> SchemaStabilityReport:
    """Compare candidate schema keys with independently induced held-out keys.

    This is structural recurrence/stability, not causal validation. The
    relation_coverage field measures the fraction of held-out relation
    instances represented by at least one candidate schema.
    """
    candidate_rows = tuple(candidates)
    heldout_rows = tuple(heldout)
    if not heldout_rows:
        raise RoleSchemaInductionError("held-out observations are required")
    candidate_keys = {
        (
            item.relation_type, item.source_role_id, item.target_role_id,
            item.source_entity_type, item.target_entity_type,
        )
        for item in candidate_rows
    }
    discovered = StructuralSchemaInducer(
        min_support=1, max_hypotheses=100000, max_rounds=max_rounds
    ).discover(heldout_rows)
    heldout_keys = {
        (
            item.relation_type, item.source_role_id, item.target_role_id,
            item.source_entity_type, item.target_entity_type,
        )
        for item in discovered.hypotheses
    }
    tp = len(candidate_keys & heldout_keys)
    fp = len(candidate_keys - heldout_keys)
    fn = len(heldout_keys - candidate_keys)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    candidate_schema_ids = {"schema-" + _digest(key) for key in candidate_keys}
    total_relations = 0
    covered_relations = 0
    for row in heldout_rows:
        roles = {
            item.entity_id: item
            for item in infer_structural_roles(row.state, max_rounds=max_rounds).assignments
        }
        nodes = {node.entity_id: node for node in row.state.nodes}
        for relation in row.state.relations:
            total_relations += 1
            source, target = roles[relation.source], roles[relation.target]
            key = (
                relation.relation_type, source.role_id, target.role_id,
                nodes[relation.source].entity_type, nodes[relation.target].entity_type,
            )
            if "schema-" + _digest(key) in candidate_schema_ids:
                covered_relations += 1
    return SchemaStabilityReport(
        tuple(sorted(candidate_schema_ids)),
        tuple(sorted("schema-" + _digest(key) for key in heldout_keys)),
        tp, fp, fn, precision, recall, f1,
        covered_relations / total_relations if total_relations else 0.0,
    )
