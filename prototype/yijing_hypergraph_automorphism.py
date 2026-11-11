"""YJ-10.2: exact bounded automorphism oracle for typed hypergraphs.

This deliberately exponential oracle is intended for small benchmark instances.
It ignores entity/edge/evidence IDs and caller-provided role names, while
preserving entity types, relation types, arity, ordered argument positions,
unordered participant multisets, edge context/attributes, and validity bounds.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import permutations, product
from math import factorial
from typing import Iterable

from prototype.yijing_hypergraph_induction import HypergraphState
from prototype.yijing_hypergraph_role_induction import (
    HypergraphRoleInductionError,
    RelationSymmetry,
    infer_hypergraph_roles,
)


class AutomorphismOracleError(ValueError):
    """Invalid policy or exceeded exact-search budget."""


@dataclass(frozen=True)
class AutomorphismAudit:
    entity_count: int
    candidate_bijections: int
    automorphism_count: int
    exact_orbits: tuple[tuple[str, ...], ...]
    wl_classes: tuple[tuple[str, ...], ...]
    pairwise_true_positive: int
    pairwise_false_merge: int
    pairwise_false_split: int
    pairwise_true_negative: int
    wl_pairwise_precision: float
    wl_pairwise_recall: float
    automorphism_mappings: tuple[tuple[tuple[str, str], ...], ...]


def _edge_multiset(state: HypergraphState, mapping: dict[str, str],
                   policies: dict[str, str]) -> Counter:
    rows = []
    for edge in state.hyperedges:
        semantics = policies[edge.relation_type]
        participants = tuple(mapping[binding.entity_id] for binding in edge.bindings)
        if semantics == "UNORDERED":
            participants = tuple(sorted(participants))
        rows.append((
            edge.relation_type,
            semantics,
            len(edge.bindings),
            participants,
            edge.context,
            edge.attributes,
            edge.valid_from,
            edge.valid_until,
        ))
    return Counter(rows)


def exact_hypergraph_automorphism_audit(
    state: HypergraphState,
    relation_symmetry: Iterable[RelationSymmetry],
    *,
    max_candidate_bijections: int = 100_000,
    max_rounds: int = 6,
) -> AutomorphismAudit:
    """Enumerate all type-preserving entity bijections within a hard budget.

    The exact orbit partition is the ground truth for structural equivalence
    under this explicit contract. It is not semantic equivalence or causality.
    """
    if not isinstance(max_candidate_bijections, int) or max_candidate_bijections < 1:
        raise AutomorphismOracleError("max_candidate_bijections must be positive")
    policy_items = tuple(relation_symmetry)
    policies: dict[str, str] = {}
    for item in policy_items:
        if item.relation_type in policies:
            raise AutomorphismOracleError("duplicate relation symmetry policy")
        policies[item.relation_type] = item.semantics
    used = {edge.relation_type for edge in state.hyperedges}
    missing = used - policies.keys()
    if missing:
        raise AutomorphismOracleError(
            "missing explicit symmetry policy: " + ", ".join(sorted(missing))
        )

    entities_by_type: dict[str, list[str]] = {}
    for entity in state.entities:
        entities_by_type.setdefault(entity.entity_type, []).append(entity.entity_id)
    for ids in entities_by_type.values():
        ids.sort()

    candidate_count = 1
    for ids in entities_by_type.values():
        candidate_count *= factorial(len(ids))
        if candidate_count > max_candidate_bijections:
            raise AutomorphismOracleError(
                f"exact search requires {candidate_count} candidate bijections; "
                f"budget is {max_candidate_bijections}"
            )

    original = _edge_multiset(
        state, {entity.entity_id: entity.entity_id for entity in state.entities}, policies
    )
    orbits = {entity.entity_id: {entity.entity_id} for entity in state.entities}
    automorphism_count = 0
    automorphism_mappings = []
    groups = [tuple(permutations(ids)) for _, ids in sorted(entities_by_type.items())]
    type_groups = [ids for _, ids in sorted(entities_by_type.items())]

    for choices in product(*groups):
        mapping: dict[str, str] = {}
        for source_ids, target_ids in zip(type_groups, choices):
            mapping.update(zip(source_ids, target_ids))
        if _edge_multiset(state, mapping, policies) != original:
            continue
        automorphism_count += 1
        automorphism_mappings.append(tuple(sorted(mapping.items())))
        for source_id, target_id in mapping.items():
            orbits[source_id].add(target_id)

    # Grouping by reachability under the automorphism group action.
    remaining = set(orbits)
    exact_groups = []
    while remaining:
        seed = min(remaining)
        members = set(orbits[seed])
        changed = True
        while changed:
            expanded = set().union(*(orbits[item] for item in members))
            changed = expanded != members
            members = expanded
        group = tuple(sorted(members))
        exact_groups.append(group)
        remaining.difference_update(members)
    exact_groups.sort()

    try:
        inferred = infer_hypergraph_roles(
            state, policy_items, max_rounds=max_rounds
        )
    except HypergraphRoleInductionError as exc:
        raise AutomorphismOracleError(str(exc)) from exc

    wl_buckets: dict[str, list[str]] = {}
    for assignment in inferred.assignments:
        wl_buckets.setdefault(assignment.structural_signature, []).append(assignment.entity_id)
    wl_groups = tuple(sorted(tuple(sorted(items)) for items in wl_buckets.values()))

    exact_label = {entity_id: index for index, group in enumerate(exact_groups)
                   for entity_id in group}
    wl_label = {entity_id: index for index, group in enumerate(wl_groups)
                for entity_id in group}
    ids = sorted(exact_label)
    tp = fm = fs = tn = 0
    for offset, left in enumerate(ids):
        for right in ids[offset + 1:]:
            exact_same = exact_label[left] == exact_label[right]
            wl_same = wl_label[left] == wl_label[right]
            if exact_same and wl_same:
                tp += 1
            elif not exact_same and wl_same:
                fm += 1
            elif exact_same and not wl_same:
                fs += 1
            else:
                tn += 1

    precision = tp / (tp + fm) if tp + fm else 1.0
    recall = tp / (tp + fs) if tp + fs else 1.0
    return AutomorphismAudit(
        entity_count=len(ids),
        candidate_bijections=candidate_count,
        automorphism_count=automorphism_count,
        exact_orbits=tuple(exact_groups),
        wl_classes=wl_groups,
        pairwise_true_positive=tp,
        pairwise_false_merge=fm,
        pairwise_false_split=fs,
        pairwise_true_negative=tn,
        wl_pairwise_precision=precision,
        wl_pairwise_recall=recall,
        automorphism_mappings=tuple(automorphism_mappings),
    )
