"""Grounded M2 semantic units into a provenance-safe Yixiang/SROK hypothesis search.

This adapter consumes already-extracted M2 candidates. It does not parse raw
text, adjudicate truth, or grant evidence authority. Each source record must
be paired with E09 observation-event references; M1 byte-span references stay
as source provenance and are never impersonated as E09 evidence events.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from prototype.trlw_working_set import MemoryPacket, PacketStatus
from prototype.observation_contract import (
    EvidenceRef,
    GroundingStatus,
    SemanticUnitCandidate,
    UnitKind,
    record_digest,
)
from prototype.srok0_kernel import Node as SrokNode
from prototype.yixiang_analogy import Relation
from prototype.yixiang_csg_gcr_adapter import (
    YixiangCsgGcrResult,
    coordinate_yixiang_compositions,
)
from prototype.yixiang_role_transform import RoleTransform
from prototype.yixiang_srok_adapter import (
    YixiangCompositionResult,
    propose_yixiang_compositions,
)


class GroundedYixiangInputError(ValueError):
    """M2 inputs cannot safely enter the Yixiang hypothesis search."""


@dataclass(frozen=True)
class GroundedYixiangComposition:
    composition: YixiangCompositionResult
    relation_record_id: str
    workspace_record_ids: tuple[str, ...]
    m1_source_ref_digests: tuple[str, ...]
    e09_observation_event_refs: tuple[str, ...]
    semantic_status: str = "HYPOTHESIS_ONLY"


@dataclass(frozen=True)
class TRLWYixiangComposition:
    grounded: GroundedYixiangComposition
    working_set_status: str
    working_set_source_complete: bool
    working_set_budget_exhausted: bool
    working_set_serialized_bytes: int
    search_exhaustive: bool


def _e09_refs(record_id: str, refs_by_record: Mapping[str, Sequence[str]]) -> tuple[str, ...]:
    refs = refs_by_record.get(record_id)
    if not isinstance(refs, (tuple, list)) or not refs:
        raise GroundedYixiangInputError(
            f"record {record_id!r} has no E09 observation-event references"
        )
    if any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise GroundedYixiangInputError("E09 event refs must be non-empty strings")
    if len(refs) != len(set(refs)):
        raise GroundedYixiangInputError("E09 event refs must be unique per record")
    return tuple(sorted(refs))


def compose_grounded_yixiang_hypotheses(
    relation_candidate: SemanticUnitCandidate,
    *,
    relation_type: str,
    workspace_candidates: Sequence[SemanticUnitCandidate],
    e09_event_refs_by_record: Mapping[str, Sequence[str]],
    transform: RoleTransform,
    limit: int = 16,
    max_candidates_per_role: int = 32,
    max_expansions: int = 10_000,
) -> GroundedYixiangComposition:
    """Build an ordered relation from grounded role bindings and search alternatives.

    The relation candidate's role-binding order is authoritative. All workspace
    candidates must be GROUNDED and in the same scope, but GROUNDED is not
    interpreted as TRUE. The SROK score is neutral (0.0) unless a separately
    calibrated scoring contract is introduced.
    """
    if not isinstance(relation_candidate, SemanticUnitCandidate):
        raise GroundedYixiangInputError("relation_candidate must be a SemanticUnitCandidate")
    if relation_candidate.grounding_status is not GroundingStatus.GROUNDED:
        raise GroundedYixiangInputError("relation candidate must be GROUNDED")
    if relation_candidate.kind not in (UnitKind.EVENT, UnitKind.ACTION, UnitKind.STATE):
        raise GroundedYixiangInputError("relation candidate kind must be EVENT, ACTION, or STATE")
    if not isinstance(relation_type, str) or not relation_type.strip():
        raise GroundedYixiangInputError("relation_type must be a non-empty string")
    if not isinstance(transform, RoleTransform):
        raise GroundedYixiangInputError("transform must be a RoleTransform")
    if not isinstance(workspace_candidates, (tuple, list)) or not workspace_candidates:
        raise GroundedYixiangInputError("workspace_candidates must be a non-empty sequence")
    if not isinstance(e09_event_refs_by_record, Mapping):
        raise GroundedYixiangInputError("e09_event_refs_by_record must be a mapping")

    relation_roles = relation_candidate.role_bindings
    if len(relation_roles) < 2:
        raise GroundedYixiangInputError("grounded relation requires at least two role bindings")
    role_names = [item.role_name for item in relation_roles]
    if len(role_names) != len(set(role_names)):
        raise GroundedYixiangInputError("relation role names must be unique")
    source_member_ids = [item.target_ref for item in relation_roles]
    if len(source_member_ids) != len(set(source_member_ids)):
        raise GroundedYixiangInputError(
            "SROK-0 currently requires distinct source members for relation roles"
        )

    rows = tuple(workspace_candidates)
    if any(not isinstance(item, SemanticUnitCandidate) for item in rows):
        raise GroundedYixiangInputError("workspace must contain SemanticUnitCandidate values")
    by_id = {item.envelope.record_id: item for item in rows}
    if len(by_id) != len(rows):
        raise GroundedYixiangInputError("workspace candidate record IDs must be unique")
    missing = tuple(member_id for member_id in source_member_ids if member_id not in by_id)
    if missing:
        raise GroundedYixiangInputError("grounded relation references missing workspace candidates")

    scope = relation_candidate.envelope.scope
    if any(item.envelope.scope != scope for item in rows):
        raise GroundedYixiangInputError("relation and workspace candidates must share one scope")
    for item in rows:
        if item.grounding_status is not GroundingStatus.GROUNDED:
            raise GroundedYixiangInputError(
                f"workspace candidate {item.envelope.record_id!r} is not GROUNDED"
            )
        if item.kind is UnitKind.UNKNOWN:
            raise GroundedYixiangInputError("UNKNOWN semantic units cannot fill typed relation roles")

    if transform.source_relation_type != relation_type:
        raise GroundedYixiangInputError("relation_type does not match XSL transform source type")
    if transform.arity != len(relation_roles):
        raise GroundedYixiangInputError("XSL transform arity does not match grounded relation roles")

    expected_record_ids = {relation_candidate.envelope.record_id, *by_id.keys()}
    if set(e09_event_refs_by_record) != expected_record_ids:
        raise GroundedYixiangInputError(
            "E09 event-ref mapping must cover exactly the relation and workspace records"
        )

    srok_nodes = []
    source_ref_digests = set()
    all_e09_refs = set()
    for item in rows:
        record_id = item.envelope.record_id
        event_refs = _e09_refs(record_id, e09_event_refs_by_record)
        all_e09_refs.update(event_refs)
        source_ref_digests.update(record_digest(ref) for ref in item.envelope.source_refs)
        tags = frozenset(attribute.name for attribute in item.typed_attributes)
        srok_nodes.append(SrokNode(
            node_id=record_id,
            node_type=item.kind.value,
            tags=tags,
            score=0.0,
            evidence_ids=event_refs,
        ))

    relation_record_id = relation_candidate.envelope.record_id
    relation_event_refs = _e09_refs(relation_record_id, e09_event_refs_by_record)
    all_e09_refs.update(relation_event_refs)
    source_ref_digests.update(
        record_digest(ref) for ref in relation_candidate.envelope.source_refs
    )

    relation = Relation(
        relation_type,
        tuple(binding.target_ref for binding in relation_roles),
    )
    result = propose_yixiang_compositions(
        relation,
        transform,
        tuple(srok_nodes),
        limit=limit,
        max_candidates_per_role=max_candidates_per_role,
        max_expansions=max_expansions,
        source_relation_evidence_refs=relation_event_refs,
    )
    return GroundedYixiangComposition(
        composition=result,
        relation_record_id=relation_record_id,
        workspace_record_ids=tuple(sorted(by_id)),
        m1_source_ref_digests=tuple(sorted(source_ref_digests)),
        e09_observation_event_refs=tuple(sorted(all_e09_refs)),
    )


def compose_trlw_grounded_yixiang_hypotheses(
    packet: MemoryPacket,
    *,
    relation_record_id: str,
    relation_type: str,
    e09_event_refs_by_record: Mapping[str, Sequence[str]],
    transform: RoleTransform,
    limit: int = 16,
    max_candidates_per_role: int = 32,
    max_expansions: int = 10_000,
) -> TRLWYixiangComposition:
    """Compose hypotheses only from the bounded candidates selected by TRLW.

    A truncated or incomplete packet can still produce useful hypotheses, but
    the result explicitly marks search_exhaustive=False. It must never be
    interpreted as a complete search of the durable ZPCM history.
    """
    if not isinstance(packet, MemoryPacket):
        raise GroundedYixiangInputError("packet must be a TRLW MemoryPacket")
    if not isinstance(relation_record_id, str) or not relation_record_id.strip():
        raise GroundedYixiangInputError("relation_record_id must be non-empty")
    if not packet.entries:
        raise GroundedYixiangInputError("TRLW packet contains no candidates")
    records = tuple(entry.record for entry in packet.entries)
    if any(record.envelope.scope != packet.scope for record in records):
        raise GroundedYixiangInputError("TRLW packet contains a cross-scope candidate")
    by_id = {record.envelope.record_id: record for record in records}
    if len(by_id) != len(records):
        raise GroundedYixiangInputError("TRLW packet contains duplicate record IDs")
    relation_candidate = by_id.get(relation_record_id)
    if relation_candidate is None:
        raise GroundedYixiangInputError(
            "relation candidate is absent from the bounded TRLW packet"
        )
    grounded = compose_grounded_yixiang_hypotheses(
        relation_candidate,
        relation_type=relation_type,
        workspace_candidates=records,
        e09_event_refs_by_record=e09_event_refs_by_record,
        transform=transform,
        limit=limit,
        max_candidates_per_role=max_candidates_per_role,
        max_expansions=max_expansions,
    )
    exhaustive = (
        packet.status == PacketStatus.COMPLETE
        and packet.source_complete
        and not packet.budget_exhausted
    )
    return TRLWYixiangComposition(
        grounded=grounded,
        working_set_status=packet.status,
        working_set_source_complete=packet.source_complete,
        working_set_budget_exhausted=packet.budget_exhausted,
        working_set_serialized_bytes=packet.serialized_bytes,
        search_exhaustive=exhaustive,
    )


@dataclass(frozen=True)
class TRLWYixiangCsgGcrResult:
    working_set: TRLWYixiangComposition
    csg_gcr: YixiangCsgGcrResult
    lifecycle_advanced: bool = False


def coordinate_trlw_grounded_yixiang_csg_gcr(
    packet: MemoryPacket,
    *,
    relation_record_id: str,
    relation_type: str,
    e09_event_refs_by_record: Mapping[str, Sequence[str]],
    transform: RoleTransform,
    parent_state_ref: str,
    branch_id: str,
    limit: int = 16,
    max_candidates_per_role: int = 32,
    max_expansions: int = 10_000,
) -> TRLWYixiangCsgGcrResult:
    """Run bounded TRLW → grounded XSL/Yixiang → SROK → typed CSG-GCR.

    This function proposes and coordinates hypotheses only. It deliberately
    does not consume an E09 verification receipt or advance E12-A6 lifecycle.
    """
    working_set = compose_trlw_grounded_yixiang_hypotheses(
        packet,
        relation_record_id=relation_record_id,
        relation_type=relation_type,
        e09_event_refs_by_record=e09_event_refs_by_record,
        transform=transform,
        limit=limit,
        max_candidates_per_role=max_candidates_per_role,
        max_expansions=max_expansions,
    )
    coordinated = coordinate_yixiang_compositions(
        working_set.grounded.composition,
        parent_state_ref=parent_state_ref,
        branch_id=branch_id,
    )
    return TRLWYixiangCsgGcrResult(
        working_set=working_set,
        csg_gcr=coordinated,
    )
