"""Persisted M2 → TRLW → Yixiang/SROK → typed CSG-GCR read path."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from prototype.csg_gcr_coordinator import GlobalConstraints
from prototype.m2_semantic_unit_reader import PersistentM2SemanticUnitReader
from prototype.observation_contract import SemanticUnitCandidate
from prototype.trlw_working_set import (
    MemoryPacket, Ranker, TRLWQuery, build_trlw_working_set_from_store,
)
from prototype.yixiang_csg_gcr_adapter import (
    YixiangCsgGcrResult, coordinate_yixiang_compositions,
)
from prototype.yixiang_role_transform import RoleTransform
from prototype.m2_yixiang_grounding_adapter import (
    GroundedYixiangComposition, compose_grounded_yixiang_hypotheses,
)


class M2YixiangRuntimeError(RuntimeError):
    """Persisted M2 inputs are insufficient for a bounded Yixiang search."""


@dataclass(frozen=True)
class PersistedYixiangRuntimeResult:
    working_set: MemoryPacket
    relation_candidate: SemanticUnitCandidate
    composition: GroundedYixiangComposition
    coordination: YixiangCsgGcrResult

    @property
    def semantic_status(self) -> str:
        return self.coordination.semantic_status


def run_persisted_yixiang_search(
    reader: PersistentM2SemanticUnitReader,
    query: TRLWQuery,
    *,
    relation_record_id: str,
    relation_type: str,
    e09_event_refs_by_record: Mapping[str, Sequence[str]],
    transform: RoleTransform,
    parent_state_ref: str,
    branch_id: str,
    constraints: GlobalConstraints = GlobalConstraints(),
    ranker: Ranker | None = None,
    limit: int = 16,
    max_candidates_per_role: int = 32,
    max_expansions: int = 10_000,
) -> PersistedYixiangRuntimeResult:
    """Run a bounded hypothesis search over persisted, currently active M2 units.

    The reader supplies current candidate versions from ZPCM. TRLW creates a
    bounded working set; Yixiang/SROK then composes hypotheses and typed
    CSG-GCR coordinates them. Incomplete source scans fail closed. This path
    never advances E12-A6 or writes facts to ZPCM.
    """
    if not isinstance(reader, PersistentM2SemanticUnitReader):
        raise TypeError("reader must be PersistentM2SemanticUnitReader")
    if not isinstance(query, TRLWQuery):
        raise TypeError("query must be TRLWQuery")
    if reader.scope != query.scope:
        raise M2YixiangRuntimeError("reader and TRLW query scopes differ")
    working_set = build_trlw_working_set_from_store(reader, query, ranker=ranker)
    if not working_set.source_complete:
        raise M2YixiangRuntimeError(
            "TRLW source scan is incomplete; refusing to present partial hypotheses as a complete search"
        )
    relation = reader.get_current_candidate(
        relation_record_id, max_events=query.max_scan_events,
    )
    if relation is None:
        raise M2YixiangRuntimeError("requested relation candidate is missing or retracted")
    workspace = tuple(
        entry.record for entry in working_set.entries
        if entry.record.envelope.record_id != relation.envelope.record_id
    )
    if not workspace:
        raise M2YixiangRuntimeError("TRLW working set contains no role candidates")
    composition = compose_grounded_yixiang_hypotheses(
        relation, relation_type=relation_type,
        workspace_candidates=workspace,
        e09_event_refs_by_record=e09_event_refs_by_record,
        transform=transform, limit=limit,
        max_candidates_per_role=max_candidates_per_role,
        max_expansions=max_expansions,
    )
    coordination = coordinate_yixiang_compositions(
        composition.composition, parent_state_ref=parent_state_ref,
        branch_id=branch_id, constraints=constraints,
    )
    if coordination.semantic_status != "HYPOTHESIS_ONLY":
        raise M2YixiangRuntimeError("Yixiang output lost its hypothesis-only semantic status")
    return PersistedYixiangRuntimeResult(
        working_set=working_set, relation_candidate=relation,
        composition=composition, coordination=coordination,
    )
