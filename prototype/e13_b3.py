"""E13-B3 bounded candidate discovery for explicit cross-domain bridges.

This is a finite hypothesis enumerator, not a semantic oracle. It enumerates
injective type/relation/role maps from declared graph schemas, then delegates
all acceptance decisions to the independent B2 validator. Budget exhaustion
returns no accepted candidates so a truncated search cannot masquerade as proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations, product
from typing import Iterable

from .e13_bridge import BridgeHypothesis, BridgeValidation, propose_bridge, validate_bridge
from .e13_contract import RelationalGraph, RoleSemantics


@dataclass(frozen=True)
class CandidateSearchResult:
    status: str
    hypotheses_examined: int
    valid_candidates: tuple[tuple[BridgeHypothesis, BridgeValidation], ...]
    rejected_count: int
    reason: str | None = None


def _injective_maps(source: tuple[str, ...], target: tuple[str, ...]):
    if len(source) > len(target):
        return
    for selected in permutations(target, len(source)):
        yield tuple(zip(source, selected))


def enumerate_bridge_candidates(
    source: RelationalGraph,
    target: RelationalGraph,
    *,
    context_key_map: Iterable[tuple[str, str]],
    max_candidates: int = 10_000,
    provenance: str = "finite-schema-enumerator",
) -> CandidateSearchResult:
    """Enumerate finite injective maps; preserve all valid hypotheses.

    The budget counts complete hypotheses passed to the validator. If another
    candidate exists after the budget is consumed, the result is BUDGET_EXHAUSTED
    and valid_candidates is empty (fail closed).
    """
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")

    source_types = tuple(sorted({e.entity_type for e in source.entities}))
    target_types = tuple(sorted({e.entity_type for e in target.entities}))
    source_schemas = tuple(sorted(source.schemas, key=lambda x: x.relation_type))
    target_schemas = tuple(sorted(target.schemas, key=lambda x: x.relation_type))
    context_maps = tuple(context_key_map)

    if any(s.role_semantics != RoleSemantics.ORDERED_NAMED for s in source_schemas):
        return CandidateSearchResult("NO_CANDIDATES", 0, (), 0, "SOURCE_ROLE_SEMANTICS_UNSUPPORTED")
    if any(t.role_semantics != RoleSemantics.ORDERED_NAMED for t in target_schemas):
        return CandidateSearchResult("NO_CANDIDATES", 0, (), 0, "TARGET_ROLE_SEMANTICS_UNSUPPORTED")

    type_options = tuple(_injective_maps(source_types, target_types))
    relation_options = []
    for mapping in _injective_maps(
        tuple(s.relation_type for s in source_schemas),
        tuple(t.relation_type for t in target_schemas),
    ):
        mapped = dict(mapping)
        if all(
            next(s for s in source_schemas if s.relation_type == src).arity
            == next(t for t in target_schemas if t.relation_type == dst).arity
            for src, dst in mapping
        ):
            relation_options.append(mapping)

    valid = []
    examined = 0
    rejected = 0
    candidate_id = 0

    # Each role permutation is a distinct structural hypothesis; the validator
    # checks argument type patterns, symmetry, role coverage and graph instances.
    role_option_sets = []
    for ss in source_schemas:
        role_option_sets.append(tuple(permutations(ss.role_names)))

    search_space = product(type_options, relation_options, *role_option_sets)
    for combination in search_space:
        if examined >= max_candidates:
            return CandidateSearchResult(
                "BUDGET_EXHAUSTED", examined, (), rejected,
                "SEARCH_TRUNCATED_ACCEPTED_CANDIDATES_WITHHELD"
            )
        type_mapping, relation_mapping, *role_permutations = combination
        relation_dict = dict(relation_mapping)
        role_mapping = []
        for ss, target_roles in zip(source_schemas, role_permutations):
            target_relation = relation_dict[ss.relation_type]
            for source_role, target_role in zip(ss.role_names, target_roles):
                role_mapping.append((ss.relation_type, target_relation, source_role, target_role))
        candidate_id += 1
        hypothesis = propose_bridge(
            f"e13-b3-{candidate_id}",
            entity_types=type_mapping,
            relations=relation_mapping,
            roles=role_mapping,
            contexts=context_maps,
            provenance=provenance,
            rationale="enumerated finite typed-role mapping; validation is separate",
        )
        result = validate_bridge(source, target, hypothesis)
        examined += 1
        if result.status == "VALID":
            valid.append((hypothesis, result))
        else:
            rejected += 1

    return CandidateSearchResult(
        "COMPLETE" if valid else "NO_VALID_CANDIDATES",
        examined, tuple(valid), rejected,
        None if valid else "ALL_ENUMERATED_HYPOTHESES_REJECTED"
    )
