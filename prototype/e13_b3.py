"""E13-B3 bounded candidate discovery for explicit cross-domain bridges.

This finite hypothesis enumerator is not a semantic oracle. It enumerates
injective type/relation maps and target-role permutations, then delegates
acceptance to the independent B2 validator. Budget exhaustion fails closed.
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
    """Enumerate finite injective maps and validate every complete hypothesis.

    The budget counts complete hypotheses. If another hypothesis exists after
    the budget is consumed, partial accepted candidates are withheld.
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
    target_schema_by_name = {s.relation_type: s for s in target_schemas}
    relation_options = []
    for mapping in _injective_maps(
        tuple(s.relation_type for s in source_schemas),
        tuple(s.relation_type for s in target_schemas),
    ):
        if all(
            ss.arity == target_schema_by_name[dst].arity
            for src, dst in mapping
            for ss in source_schemas if ss.relation_type == src
        ):
            relation_options.append(mapping)

    valid: list[tuple[BridgeHypothesis, BridgeValidation]] = []
    examined = 0
    rejected = 0
    candidate_id = 0

    for type_mapping in type_options:
        for relation_mapping in relation_options:
            relation_dict = dict(relation_mapping)
            role_option_sets = []
            for ss in source_schemas:
                target_schema = target_schema_by_name[relation_dict[ss.relation_type]]
                role_option_sets.append(tuple(permutations(target_schema.role_names)))

            for role_permutations in product(*role_option_sets):
                if examined >= max_candidates:
                    return CandidateSearchResult(
                        "BUDGET_EXHAUSTED", examined, (), rejected,
                        "SEARCH_TRUNCATED_ACCEPTED_CANDIDATES_WITHHELD"
                    )

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
