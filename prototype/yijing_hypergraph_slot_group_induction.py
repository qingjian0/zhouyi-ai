"""YJ-10.4: induce relation-slot permutation groups from exact automorphisms.

The exact entity-automorphism oracle supplies witnesses. For each hyperedge,
we restrict the global automorphism group to the setwise stabilizer of that
edge's participant set, then map the stabilizer action into slot coordinates.
This is a structural group action, not semantic or causal symmetry.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import permutations
from typing import Iterable

from prototype.yijing_hypergraph_automorphism import (
    AutomorphismAudit,
    AutomorphismOracleError,
    exact_hypergraph_automorphism_audit,
)
from prototype.yijing_hypergraph_permutation_groups import (
    PermutationGroupError,
    PermutationGroupHypothesis,
    SlotPermutationEvidence,
    SymmetryGroupTransition,
    compare_symmetry_groups,
    learn_slot_permutation_group,
)
from prototype.yijing_hypergraph_role_induction import (
    HypergraphRoleObservation,
    RelationSymmetry,
)


class ExactSlotGroupInductionError(ValueError):
    """Invalid slot frame, evidence, or exact automorphism witness."""


@dataclass(frozen=True)
class ExactSlotGroupHypothesis:
    relation_type: str
    arity: int
    slot_frame: tuple[str, ...]
    entity_type_frame: tuple[str, ...]
    context: tuple[tuple[str, str], ...]
    attributes: tuple[tuple[str, str], ...]
    valid_from: int | None
    valid_until: int | None
    semantics: str
    group: PermutationGroupHypothesis


@dataclass(frozen=True)
class ExactSlotGroupObservation:
    evidence_id: str
    relation_type: str
    arity: int
    slot_frame: tuple[str, ...]
    entity_type_frame: tuple[str, ...]
    context: tuple[tuple[str, str], ...]
    attributes: tuple[tuple[str, str], ...]
    valid_from: int | None
    valid_until: int | None
    semantics: str
    exact_group: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class ExactSlotGroupTransition:
    from_evidence_id: str
    to_evidence_id: str
    relation_type: str
    slot_frame: tuple[str, ...]
    transition: SymmetryGroupTransition


@dataclass(frozen=True)
class ExactSlotGroupDiscoveryReport:
    observations_seen: int
    automorphism_audits: tuple[AutomorphismAudit, ...]
    observation_groups: tuple[ExactSlotGroupObservation, ...]
    transitions: tuple[ExactSlotGroupTransition, ...]
    hypotheses: tuple[ExactSlotGroupHypothesis, ...]


def _schema_key(edge, entity_types: dict[str, str], semantics: str) -> tuple:
    return (
        edge.relation_type,
        len(edge.bindings),
        tuple(binding.role for binding in edge.bindings),
        tuple(entity_types[binding.entity_id] for binding in edge.bindings),
        edge.context,
        edge.attributes,
        edge.valid_from,
        edge.valid_until,
        semantics,
    )


def induce_exact_slot_permutation_groups(
    observations: Iterable[HypergraphRoleObservation],
    relation_symmetry: Iterable[RelationSymmetry],
    *,
    min_support: int = 1,
    max_candidate_bijections: int = 100_000,
    max_group_elements: int = 100_000,
    max_rounds: int = 6,
) -> ExactSlotGroupDiscoveryReport:
    """Infer exact slot groups using automorphism stabilizers.

    Slot-role labels are used only as an explicit coordinate-frame contract
    across observations. They are not treated as discovered semantic roles.
    Observations with different slot frames or typed/contextual schemas are
    kept separate. Within one snapshot, repeated matching edge instances are
    intersected conservatively before contributing one evidence record.
    """
    rows = tuple(observations)
    if not rows:
        raise ExactSlotGroupInductionError("at least one observation is required")
    evidence_ids = [row.evidence_id for row in rows]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ExactSlotGroupInductionError("observation evidence IDs must be unique")

    policies = tuple(relation_symmetry)
    policy_map = {item.relation_type: item.semantics for item in policies}
    if len(policy_map) != len(policies):
        raise ExactSlotGroupInductionError("duplicate relation symmetry policy")

    # key -> observation evidence ID -> common exact stabilizer
    evidence_by_schema: dict[tuple, dict[str, set[tuple[int, ...]]]] = defaultdict(dict)
    audits = []

    for observation in rows:
        state = observation.state
        if state.coverage_complete is not True:
            raise ExactSlotGroupInductionError(
                "complete coverage is required for exact slot-group induction"
            )
        try:
            audit = exact_hypergraph_automorphism_audit(
                state,
                policies,
                max_candidate_bijections=max_candidate_bijections,
                max_rounds=max_rounds,
                include_automorphism_mappings=True,
            )
        except AutomorphismOracleError as exc:
            raise ExactSlotGroupInductionError(str(exc)) from exc
        audits.append(audit)
        if len(audit.automorphism_mappings) != audit.automorphism_count:
            raise ExactSlotGroupInductionError(
                "exact oracle did not return every automorphism witness"
            )

        entity_types = state.entity_types()
        groups_in_snapshot: dict[tuple, list[set[tuple[int, ...]]]] = defaultdict(list)
        for edge in state.hyperedges:
            semantics = policy_map[edge.relation_type]
            # ORDERED relations provide positional context; the discovery target
            # is a relation whose slot permutations are not fixed in advance.
            if semantics != "UNORDERED":
                continue
            participant_ids = tuple(binding.entity_id for binding in edge.bindings)
            if len(participant_ids) != len(set(participant_ids)):
                raise ExactSlotGroupInductionError(
                    "repeated entity within one hyperedge has ambiguous slot action"
                )
            slot_index = {entity_id: index
                          for index, entity_id in enumerate(participant_ids)}
            identity = tuple(range(len(participant_ids)))
            stabilizer = {identity}

            for witness in audit.automorphism_mappings:
                mapping = dict(witness)
                mapped_participants = tuple(mapping[item] for item in participant_ids)
                if set(mapped_participants) != set(participant_ids):
                    continue
                induced = tuple(slot_index[item] for item in mapped_participants)
                stabilizer.add(induced)

            key = _schema_key(edge, entity_types, semantics)
            groups_in_snapshot[key].append(stabilizer)

        for key, instance_groups in groups_in_snapshot.items():
            common = set.intersection(*instance_groups)
            if not common:
                raise ExactSlotGroupInductionError(
                    "intersection of exact edge stabilizers lost identity"
                )
            evidence_by_schema[key][observation.evidence_id] = common

    hypotheses = []
    observation_groups = []
    transitions = []
    for key, evidence_groups in sorted(evidence_by_schema.items(), key=lambda item: repr(item[0])):
        (relation_type, arity, slot_frame, entity_type_frame, context,
         attributes, valid_from, valid_until, semantics) = key
        ordered_groups = list(evidence_groups.items())
        for evidence_id, exact_group in ordered_groups:
            observation_groups.append(ExactSlotGroupObservation(
                evidence_id=evidence_id,
                relation_type=relation_type,
                arity=arity,
                slot_frame=slot_frame,
                entity_type_frame=entity_type_frame,
                context=context,
                attributes=attributes,
                valid_from=valid_from,
                valid_until=valid_until,
                semantics=semantics,
                exact_group=tuple(sorted(exact_group)),
            ))
        for (before_id, before_group), (after_id, after_group) in zip(
            ordered_groups, ordered_groups[1:]
        ):
            try:
                transition = compare_symmetry_groups(before_group, after_group)
            except PermutationGroupError as exc:
                raise ExactSlotGroupInductionError(str(exc)) from exc
            transitions.append(ExactSlotGroupTransition(
                before_id, after_id, relation_type, slot_frame, transition
            ))

        permutation_evidence = []
        for candidate in permutations(range(arity)):
            candidate = tuple(candidate)
            for evidence_id, group in ordered_groups:
                permutation_evidence.append(SlotPermutationEvidence(
                    candidate, evidence_id, candidate in group
                ))
        try:
            learned = learn_slot_permutation_group(
                arity,
                permutation_evidence,
                min_support=min_support,
                max_group_elements=max_group_elements,
            )
        except PermutationGroupError as exc:
            raise ExactSlotGroupInductionError(str(exc)) from exc

        hypotheses.append(ExactSlotGroupHypothesis(
            relation_type=relation_type,
            arity=arity,
            slot_frame=slot_frame,
            entity_type_frame=entity_type_frame,
            context=context,
            attributes=attributes,
            valid_from=valid_from,
            valid_until=valid_until,
            semantics=semantics,
            group=learned,
        ))

    return ExactSlotGroupDiscoveryReport(
        observations_seen=len(rows),
        automorphism_audits=tuple(audits),
        observation_groups=tuple(observation_groups),
        transitions=tuple(transitions),
        hypotheses=tuple(hypotheses),
    )
