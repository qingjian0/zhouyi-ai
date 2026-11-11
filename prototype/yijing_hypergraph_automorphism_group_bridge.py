"""Bridge exact entity automorphisms to induced relation-slot permutations.

The bridge only derives structural slot actions from exact mappings returned
by the bounded oracle. It does not assign semantic meaning to those actions.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from prototype.yijing_hypergraph_automorphism import AutomorphismAudit, AutomorphismOracleError
from prototype.yijing_hypergraph_induction import HypergraphState
from prototype.yijing_hypergraph_permutation_groups import SlotPermutationEvidence
from prototype.yijing_hypergraph_role_induction import RelationSymmetry


@dataclass(frozen=True)
class InducedSlotPermutation:
    relation_type: str
    evidence: SlotPermutationEvidence
    source_edge_id: str
    target_edge_id: str
    automorphism_index: int


def derive_slot_permutation_evidence(
    state: HypergraphState,
    audit: AutomorphismAudit,
    relation_symmetry: Iterable[RelationSymmetry],
) -> tuple[InducedSlotPermutation, ...]:
    """Derive slot permutations witnessed by exact entity automorphisms.

    Only UNORDERED relations can yield non-identity slot actions under the
    current oracle contract. Repeated participants are skipped because their
    slot correspondence would be ambiguous.
    """
    policies = {}
    for item in tuple(relation_symmetry):
        if item.relation_type in policies:
            raise AutomorphismOracleError("duplicate relation symmetry policy")
        policies[item.relation_type] = item.semantics

    edges_by_relation = defaultdict(list)
    for edge in state.hyperedges:
        if edge.relation_type not in policies:
            raise AutomorphismOracleError("missing relation symmetry policy")
        edges_by_relation[edge.relation_type].append(edge)

    output = []
    for mapping_index, pairs in enumerate(audit.automorphism_mappings):
        mapping = dict(pairs)
        for relation, edges in sorted(edges_by_relation.items()):
            if policies[relation] != "UNORDERED":
                continue
            for source in edges:
                source_ids = tuple(binding.entity_id for binding in source.bindings)
                if len(set(source_ids)) != len(source_ids):
                    continue
                mapped_ids = tuple(mapping[item] for item in source_ids)
                for target in edges:
                    target_ids = tuple(binding.entity_id for binding in target.bindings)
                    if len(target_ids) != len(set(target_ids)) or set(mapped_ids) != set(target_ids):
                        continue
                    if (source.context, source.attributes, source.valid_from, source.valid_until) != (
                        target.context, target.attributes, target.valid_from, target.valid_until
                    ):
                        continue
                    permutation = tuple(target_ids.index(item) for item in mapped_ids)
                    evidence_id = (
                        f"automorphism:{mapping_index}:edge:{source.edge_id}->{target.edge_id}"
                    )
                    output.append(InducedSlotPermutation(
                        relation,
                        SlotPermutationEvidence(permutation, evidence_id, True),
                        source.edge_id,
                        target.edge_id,
                        mapping_index,
                    ))
    return tuple(output)


def group_evidence_by_relation(
    induced: Iterable[InducedSlotPermutation],
) -> dict[str, tuple[SlotPermutationEvidence, ...]]:
    grouped = defaultdict(list)
    for item in induced:
        grouped[item.relation_type].append(item.evidence)
    return {key: tuple(value) for key, value in sorted(grouped.items())}
