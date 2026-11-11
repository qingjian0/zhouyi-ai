"""YJ-10: autonomous structural-role induction over typed n-ary hypergraphs.

Caller-provided role names and concrete entity IDs are excluded from structural
signatures. Relation symmetry is explicit: ordered slots retain positional
semantics; unordered relations are permutation-invariant and expose equivalence
classes rather than invented slot identities. Structural roles are not semantic
or causal roles.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping

from prototype.yijing_hypergraph_induction import HypergraphState


class HypergraphRoleInductionError(ValueError):
    """Invalid role-induction policy, observation, or budget."""


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


@dataclass(frozen=True)
class RelationSymmetry:
    relation_type: str
    semantics: str  # ORDERED or UNORDERED

    def __post_init__(self) -> None:
        if not isinstance(self.relation_type, str) or not self.relation_type.strip():
            raise HypergraphRoleInductionError("relation_type is required")
        if self.semantics not in {"ORDERED", "UNORDERED"}:
            raise HypergraphRoleInductionError("semantics must be ORDERED or UNORDERED")


@dataclass(frozen=True)
class HypergraphRoleObservation:
    state: HypergraphState
    evidence_id: str
    domain: str

    def __post_init__(self) -> None:
        if not self.evidence_id or not self.evidence_id.strip():
            raise HypergraphRoleInductionError("evidence_id is required")
        if not self.domain or not self.domain.strip():
            raise HypergraphRoleInductionError("domain is required")


@dataclass(frozen=True)
class InferredHypergraphRole:
    entity_id: str
    role_id: str
    entity_type: str
    refinement_round: int
    structural_signature: str


@dataclass(frozen=True)
class RoleEquivalenceClass:
    role_id: str
    entity_type: str
    members: tuple[str, ...]
    structural_signature: str


@dataclass(frozen=True)
class HypergraphRoleResult:
    assignments: tuple[InferredHypergraphRole, ...]
    equivalence_classes: tuple[RoleEquivalenceClass, ...]
    refinement_rounds: int
    stabilized: bool


def _partition(colors: Mapping[str, str]) -> frozenset[frozenset[str]]:
    groups: dict[str, set[str]] = defaultdict(set)
    for entity_id, color in colors.items():
        groups[color].add(entity_id)
    return frozenset(frozenset(group) for group in groups.values())


def infer_hypergraph_roles(
    state: HypergraphState,
    relation_symmetry: Iterable[RelationSymmetry],
    *,
    max_rounds: int = 6,
) -> HypergraphRoleResult:
    """Bounded higher-order WL refinement over hyperedge incidence neighborhoods.

    ORDERED relations preserve each participant's argument index. UNORDERED
    relations sort co-participant colors and use a shared slot marker, making
    role inference invariant to participant permutations. Existing binding.role
    strings, edge IDs, evidence IDs, context values, and entity IDs are not
    used in structural colors.
    """
    if not isinstance(max_rounds, int) or not 0 <= max_rounds <= 12:
        raise HypergraphRoleInductionError("max_rounds must be between 0 and 12")
    policies: dict[str, str] = {}
    for item in relation_symmetry:
        if item.relation_type in policies:
            raise HypergraphRoleInductionError("duplicate relation symmetry policy")
        policies[item.relation_type] = item.semantics

    used_types = {edge.relation_type for edge in state.hyperedges}
    missing = used_types - set(policies)
    if missing:
        raise HypergraphRoleInductionError(
            "missing explicit symmetry policy for relation types: " + ", ".join(sorted(missing))
        )

    types = state.entity_types()
    colors = {entity_id: _digest(("entity", entity_type))
              for entity_id, entity_type in types.items()}
    stabilized = False
    rounds_done = 0

    for round_index in range(max_rounds):
        incidence: dict[str, list[tuple]] = defaultdict(list)
        for edge in state.hyperedges:
            semantics = policies[edge.relation_type]
            participants = tuple(binding.entity_id for binding in edge.bindings)
            for index, entity_id in enumerate(participants):
                others = tuple(
                    (other_index, colors[other_id])
                    for other_index, other_id in enumerate(participants)
                    if other_index != index
                )
                if semantics == "ORDERED":
                    slot = ("position", index)
                    neighborhood = others
                else:
                    slot = ("symmetric",)
                    neighborhood = tuple(sorted(color for _, color in others))
                incidence[entity_id].append((
                    edge.relation_type, len(participants), semantics, slot, neighborhood
                ))

        next_colors = {}
        for entity_id, entity_type in types.items():
            signature = (
                "hypergraph-wl-v1",
                entity_type,
                colors[entity_id],
                tuple(sorted(incidence[entity_id], key=repr)),
            )
            next_colors[entity_id] = _digest(signature)

        rounds_done = round_index + 1
        if _partition(next_colors) == _partition(colors):
            colors = next_colors
            stabilized = True
            break
        colors = next_colors

    groups: dict[str, list[str]] = defaultdict(list)
    for entity_id, color in colors.items():
        groups[color].append(entity_id)

    assignments = tuple(sorted((
        InferredHypergraphRole(
            entity_id=entity_id,
            role_id="hrole-" + color,
            entity_type=types[entity_id],
            refinement_round=rounds_done,
            structural_signature=color,
        )
        for entity_id, color in colors.items()
    ), key=lambda item: item.entity_id))

    equivalence_classes = tuple(sorted((
        RoleEquivalenceClass(
            role_id="hrole-" + color,
            entity_type=types[members[0]],
            members=tuple(sorted(members)),
            structural_signature=color,
        )
        for color, members in groups.items()
    ), key=lambda item: item.role_id))

    return HypergraphRoleResult(
        assignments, equivalence_classes, rounds_done, stabilized
    )


@dataclass(frozen=True)
class HyperedgeSchemaHypothesis:
    schema_id: str
    relation_type: str
    semantics: str
    arity: int
    role_pattern: tuple[tuple[str, str], ...]
    support_evidence_ids: tuple[str, ...]
    domains: tuple[str, ...]


@dataclass(frozen=True)
class HypergraphSchemaDiscoveryReport:
    hypotheses: tuple[HyperedgeSchemaHypothesis, ...]
    observations_seen: int
    hyperedges_seen: int
    budget_exhausted: bool


class HypergraphSchemaInducer:
    """Induce recurring n-ary schemas from inferred roles, not supplied role names."""

    def __init__(
        self, *, min_support: int = 2, max_hypotheses: int = 512, max_rounds: int = 6
    ) -> None:
        if min_support < 1 or max_hypotheses < 1:
            raise HypergraphRoleInductionError("support and hypothesis budgets must be positive")
        if not 0 <= max_rounds <= 12:
            raise HypergraphRoleInductionError("max_rounds must be between 0 and 12")
        self.min_support = min_support
        self.max_hypotheses = max_hypotheses
        self.max_rounds = max_rounds

    def discover(
        self,
        observations: Iterable[HypergraphRoleObservation],
        relation_symmetry: Iterable[RelationSymmetry],
    ) -> HypergraphSchemaDiscoveryReport:
        rows = tuple(observations)
        if not rows:
            raise HypergraphRoleInductionError("at least one observation is required")
        evidence_ids = [row.evidence_id for row in rows]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise HypergraphRoleInductionError("evidence IDs must be unique")
        policies = tuple(relation_symmetry)
        policy_map = {item.relation_type: item.semantics for item in policies}
        if len(policy_map) != len(policies):
            raise HypergraphRoleInductionError("duplicate relation symmetry policy")

        buckets: dict[tuple, dict[str, set[str]]] = {}
        edge_count = 0
        for row in rows:
            inferred = infer_hypergraph_roles(
                row.state, policies, max_rounds=self.max_rounds
            )
            role_by_entity = {item.entity_id: item for item in inferred.assignments}
            seen: set[tuple] = set()
            for edge in row.state.hyperedges:
                edge_count += 1
                semantics = policy_map[edge.relation_type]
                participants = [
                    (role_by_entity[binding.entity_id].role_id,
                     role_by_entity[binding.entity_id].entity_type)
                    for binding in edge.bindings
                ]
                if semantics == "UNORDERED":
                    pattern = tuple(sorted(participants))
                else:
                    pattern = tuple(participants)
                key = (edge.relation_type, semantics, len(participants), pattern)
                seen.add(key)
            for key in seen:
                bucket = buckets.setdefault(key, {"evidence": set(), "domains": set()})
                bucket["evidence"].add(row.evidence_id)
                bucket["domains"].add(row.domain)

        eligible = [
            (key, value) for key, value in sorted(buckets.items(), key=lambda item: item[0])
            if len(value["evidence"]) >= self.min_support
        ]
        exhausted = len(eligible) > self.max_hypotheses
        hypotheses = []
        for key, value in eligible[:self.max_hypotheses]:
            relation_type, semantics, arity, pattern = key
            hypotheses.append(HyperedgeSchemaHypothesis(
                schema_id="hschema-" + _digest(key),
                relation_type=relation_type,
                semantics=semantics,
                arity=arity,
                role_pattern=pattern,
                support_evidence_ids=tuple(sorted(value["evidence"])),
                domains=tuple(sorted(value["domains"])),
            ))
        return HypergraphSchemaDiscoveryReport(
            tuple(hypotheses), len(rows), edge_count, exhausted
        )
