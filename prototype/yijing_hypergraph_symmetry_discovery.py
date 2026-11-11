"""YJ-10.1: conservative, evidence-backed symmetry hypothesis discovery.

The analyzer asks which participant-slot permutations are compatible with
observed *external structural context*. It does not infer semantic symmetry
from a single arrangement. Results are explicitly WL-compatible hypotheses,
not proofs of relation semantics or full graph automorphisms.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import permutations
from typing import Iterable

from prototype.yijing_hypergraph_induction import HypergraphState
from prototype.yijing_hypergraph_role_induction import (
    HypergraphRoleInductionError,
    HypergraphRoleObservation,
    RelationSymmetry,
    infer_hypergraph_roles,
)


class SymmetryDiscoveryError(ValueError):
    """Invalid symmetry discovery evidence or computation budget."""


@dataclass(frozen=True)
class PermutationEvidence:
    permutation: tuple[int, ...]
    compatible_evidence_ids: tuple[str, ...]
    conflicting_evidence_ids: tuple[str, ...]
    status: str  # STRUCTURALLY_COMPATIBLE, CONTRADICTED, UNRESOLVED


@dataclass(frozen=True)
class SlotEquivalenceClass:
    positions: tuple[int, ...]
    supporting_evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class RelationSymmetryHypothesis:
    relation_type: str
    arity: int
    permutation_evidence: tuple[PermutationEvidence, ...]
    slot_equivalence_classes: tuple[SlotEquivalenceClass, ...]
    evidence_ids_seen: tuple[str, ...]
    semantic_status: str  # NOT_ESTABLISHED


@dataclass(frozen=True)
class SymmetryDiscoveryReport:
    hypotheses: tuple[RelationSymmetryHypothesis, ...]
    observations_seen: int
    target_edges_seen: int
    permutations_evaluated: int
    unresolved_permutations: int


def _permutation_groups(
    arity: int, permutations_by_tuple: dict[tuple[int, ...], PermutationEvidence]
) -> tuple[SlotEquivalenceClass, ...]:
    parent = list(range(arity))

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    supports: dict[tuple[int, int], set[str]] = {}
    for left in range(arity):
        for right in range(left + 1, arity):
            permutation = list(range(arity))
            permutation[left], permutation[right] = permutation[right], permutation[left]
            item = permutations_by_tuple.get(tuple(permutation))
            if item and item.status == "STRUCTURALLY_COMPATIBLE":
                parent[find(right)] = find(left)
                supports[(left, right)] = set(item.compatible_evidence_ids)

    groups: dict[int, list[int]] = defaultdict(list)
    for position in range(arity):
        groups[find(position)].append(position)

    result = []
    for members in groups.values():
        if len(members) < 2:
            continue
        evidence_sets = [
            supports[(left, right)]
            for offset, left in enumerate(members)
            for right in members[offset + 1:]
            if (left, right) in supports
        ]
        shared = set.intersection(*evidence_sets) if evidence_sets else set()
        result.append(SlotEquivalenceClass(tuple(members), tuple(sorted(shared))))
    return tuple(sorted(result, key=lambda item: item.positions))


def discover_relation_symmetry(
    observations: Iterable[HypergraphRoleObservation],
    target_relation_type: str,
    context_relation_symmetry: Iterable[RelationSymmetry],
    *,
    min_support: int = 2,
    max_arity: int = 6,
    max_permutations: int = 720,
    max_rounds: int = 6,
) -> SymmetryDiscoveryReport:
    """Find slot permutations compatible with external typed structure.

    For each target relation instance, remove every edge of the target relation
    type, infer bounded WL colors from the remaining context graph, then test
    whether a slot permutation only exchanges participants with equal context
    colors. Evidence is aggregated by distinct observation IDs.

    This is deliberately conservative: a permutation with any observed
    conflict is marked CONTRADICTED; one with insufficient support remains
    UNRESOLVED. No target relation's own slot ordering is used to color its
    participants, avoiding circular evidence.
    """
    if not isinstance(target_relation_type, str) or not target_relation_type.strip():
        raise SymmetryDiscoveryError("target_relation_type is required")
    if not isinstance(min_support, int) or min_support < 1:
        raise SymmetryDiscoveryError("min_support must be positive")
    if not isinstance(max_arity, int) or not 2 <= max_arity <= 8:
        raise SymmetryDiscoveryError("max_arity must be between 2 and 8")
    if not isinstance(max_permutations, int) or max_permutations < 1:
        raise SymmetryDiscoveryError("max_permutations must be positive")
    if not isinstance(max_rounds, int) or not 0 <= max_rounds <= 12:
        raise SymmetryDiscoveryError("max_rounds must be between 0 and 12")

    rows = tuple(observations)
    if not rows:
        raise SymmetryDiscoveryError("at least one observation is required")
    evidence_ids = [row.evidence_id for row in rows]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise SymmetryDiscoveryError("observation evidence IDs must be unique")

    context_policies = tuple(context_relation_symmetry)
    policy_map = {item.relation_type: item.semantics for item in context_policies}
    if len(policy_map) != len(context_policies):
        raise SymmetryDiscoveryError("duplicate context symmetry policy")
    if target_relation_type in policy_map:
        raise SymmetryDiscoveryError(
            "target relation policy must be excluded from external-context policies"
        )

    edges_by_arity: dict[int, list[tuple[HypergraphRoleObservation, object, dict[str, str]]]] = defaultdict(list)
    target_edges_seen = 0
    for row in rows:
        target_edges = [edge for edge in row.state.hyperedges
                        if edge.relation_type == target_relation_type]
        if not target_edges:
            continue
        context_edges = tuple(edge for edge in row.state.hyperedges
                              if edge.relation_type != target_relation_type)
        context_state = HypergraphState(
            entities=row.state.entities,
            hyperedges=context_edges,
            context=row.state.context,
            step=row.state.step,
            evidence_id=row.state.evidence_id,
            domain=row.state.domain,
            coverage_complete=row.state.coverage_complete,
        )
        try:
            role_result = infer_hypergraph_roles(
                context_state, context_policies, max_rounds=max_rounds
            )
        except HypergraphRoleInductionError as exc:
            raise SymmetryDiscoveryError(str(exc)) from exc
        colors = {item.entity_id: item.structural_signature
                  for item in role_result.assignments}
        for edge in target_edges:
            arity = len(edge.bindings)
            if arity > max_arity:
                raise SymmetryDiscoveryError(
                    f"target arity {arity} exceeds max_arity={max_arity}"
                )
            edges_by_arity[arity].append((row, edge, colors))
            target_edges_seen += 1

    if not target_edges_seen:
        raise SymmetryDiscoveryError("no target relation instances found")

    hypotheses = []
    total_permutations = 0
    unresolved = 0
    for arity, instances in sorted(edges_by_arity.items()):
        count = 1
        for value in range(2, arity + 1):
            count *= value
        if count > max_permutations:
            raise SymmetryDiscoveryError(
                f"arity {arity} requires {count} permutations; budget is {max_permutations}"
            )
        permutation_rows: dict[tuple[int, ...], dict[str, set[str]]] = {
            permutation: {"compatible": set(), "conflicting": set()}
            for permutation in permutations(range(arity))
        }
        for row, edge, colors in instances:
            participant_ids = tuple(binding.entity_id for binding in edge.bindings)
            for permutation, bucket in permutation_rows.items():
                compatible = all(
                    colors[participant_ids[position]]
                    == colors[participant_ids[permutation[position]]]
                    for position in range(arity)
                )
                bucket["compatible" if compatible else "conflicting"].add(row.evidence_id)

        evidence = []
        by_permutation = {}
        for permutation, bucket in sorted(permutation_rows.items()):
            compatible_ids = tuple(sorted(bucket["compatible"]))
            conflicting_ids = tuple(sorted(bucket["conflicting"]))
            if conflicting_ids:
                status = "CONTRADICTED"
            elif len(compatible_ids) >= min_support:
                status = "STRUCTURALLY_COMPATIBLE"
            else:
                status = "UNRESOLVED"
            item = PermutationEvidence(
                permutation, compatible_ids, conflicting_ids, status
            )
            evidence.append(item)
            by_permutation[permutation] = item
            if status == "UNRESOLVED":
                unresolved += 1
        total_permutations += len(evidence)
        slot_classes = _permutation_groups(arity, by_permutation)
        hypotheses.append(RelationSymmetryHypothesis(
            relation_type=target_relation_type,
            arity=arity,
            permutation_evidence=tuple(evidence),
            slot_equivalence_classes=slot_classes,
            evidence_ids_seen=tuple(sorted({row.evidence_id for row, _, _ in instances})),
            semantic_status="NOT_ESTABLISHED",
        ))

    return SymmetryDiscoveryReport(
        tuple(hypotheses), len(rows), target_edges_seen,
        total_permutations, unresolved,
    )
