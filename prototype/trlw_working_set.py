"""TRLW bounded working-set projection over typed M2 records.

This is an ephemeral, byte-bounded query projection. It is not an event log,
does not own durable memory, and does not turn grounding into truth. The
authoritative history remains in the configured persistence layer (ZPCM).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable

from prototype.stream_budget import ScanBudgetExceeded

from prototype.observation_contract import (
    GroundingStatus,
    Score,
    SemanticUnitCandidate,
    UnitKind,
    canonical_json,
)


class TRLWError(ValueError):
    """Invalid query, record, or ranking policy."""


class PacketStatus:
    COMPLETE = "COMPLETE"
    NOT_FOUND = "NOT_FOUND"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    SOURCE_INCOMPLETE = "SOURCE_INCOMPLETE"


def _nonempty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise TRLWError(f"{field} must be a non-empty string")


def _parse_utc(value: str, field: str) -> datetime:
    _nonempty(value, field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TRLWError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TRLWError(f"{field} must include a UTC offset")
    return parsed


@dataclass(frozen=True)
class TRLWQuery:
    query_goal: str
    scope: str
    max_records: int
    byte_budget: int
    required_types: tuple[UnitKind, ...] = ()
    allowed_grounding_statuses: tuple[GroundingStatus, ...] = (
        GroundingStatus.GROUNDED,
    )
    valid_time_start: str | None = None
    valid_time_end: str | None = None
    max_scan_events: int = 4096

    def __post_init__(self) -> None:
        _nonempty(self.query_goal, "query_goal")
        _nonempty(self.scope, "scope")
        for name, value in (("max_records", self.max_records), ("byte_budget", self.byte_budget)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise TRLWError(f"{name} must be a positive integer")
        if not isinstance(self.required_types, tuple) or any(
            not isinstance(item, UnitKind) for item in self.required_types
        ):
            raise TRLWError("required_types must be a tuple of UnitKind")
        if len(set(self.required_types)) != len(self.required_types):
            raise TRLWError("required_types must be unique")
        if (not isinstance(self.allowed_grounding_statuses, tuple)
                or not self.allowed_grounding_statuses
                or any(not isinstance(item, GroundingStatus)
                       for item in self.allowed_grounding_statuses)):
            raise TRLWError("allowed_grounding_statuses must be a non-empty typed tuple")
        if len(set(self.allowed_grounding_statuses)) != len(self.allowed_grounding_statuses):
            raise TRLWError("allowed_grounding_statuses must be unique")
        if (isinstance(self.max_scan_events, bool) or not isinstance(self.max_scan_events, int)
                or not 1 <= self.max_scan_events <= 65536):
            raise TRLWError("max_scan_events must be an integer in [1, 65536]")
        if (self.valid_time_start is None) != (self.valid_time_end is None):
            raise TRLWError("valid-time query endpoints must be supplied together")
        if self.valid_time_start is not None:
            start = _parse_utc(self.valid_time_start, "valid_time_start")
            end = _parse_utc(self.valid_time_end, "valid_time_end")
            if start >= end:
                raise TRLWError("valid-time query interval must be non-empty")


@dataclass(frozen=True)
class TRLWEntry:
    record: SemanticUnitCandidate
    ranking_score: Score
    serialized_bytes: int
    source_order: int = 0


@dataclass(frozen=True)
class MemoryPacket:
    query_goal: str
    scope: str
    entries: tuple[TRLWEntry, ...]
    status: str
    input_records_seen: int
    matched_records_seen: int
    returned_records: int
    serialized_bytes: int
    byte_budget: int
    max_records: int
    source_complete: bool
    budget_exhausted: bool

    @property
    def complete(self) -> bool:
        return self.status == PacketStatus.COMPLETE


Ranker = Callable[[SemanticUnitCandidate, TRLWQuery], Score]


def _default_ranker(record: SemanticUnitCandidate, query: TRLWQuery) -> Score:
    return Score(0.0, "trlw-ranking")


def _matches_time(record: SemanticUnitCandidate, query: TRLWQuery) -> bool:
    if query.valid_time_start is None:
        return True
    start = record.envelope.valid_time_start
    end = record.envelope.valid_time_end
    if start is None or end is None:
        return False
    record_start = _parse_utc(start, "record.valid_time_start")
    record_end = _parse_utc(end, "record.valid_time_end")
    query_start = _parse_utc(query.valid_time_start, "query.valid_time_start")
    query_end = _parse_utc(query.valid_time_end, "query.valid_time_end")
    if record_start >= record_end:
        raise TRLWError("record valid-time interval must be non-empty")
    return record_start < query_end and query_start < record_end


def build_trlw_working_set(
    records: Iterable[SemanticUnitCandidate],
    query: TRLWQuery,
    *,
    ranker: Ranker | None = None,
    source_complete: bool,
) -> MemoryPacket:
    """Select a bounded, ranked packet without retaining the full input history.

    The byte budget applies to canonical serialized record bytes, not Python
    heap/RSS. Peak process memory must still be measured separately. The
    upstream iterator must provide a stable, deduplicated ZPCM projection.
    """
    if not isinstance(query, TRLWQuery):
        raise TRLWError("query must be TRLWQuery")
    if not isinstance(source_complete, bool):
        raise TRLWError("source_complete must be bool")
    scorer = ranker or _default_ranker
    selected: list[TRLWEntry] = []
    selected_bytes = 0
    seen = 0
    matched = 0
    budget_exhausted = False
    effective_source_complete = source_complete

    try:
        for record in records:
            seen += 1
            if not isinstance(record, SemanticUnitCandidate):
                raise TRLWError("input records must be SemanticUnitCandidate values")
            if record.envelope.scope != query.scope:
                continue
            if query.required_types and record.kind not in query.required_types:
                continue
            if record.grounding_status not in query.allowed_grounding_statuses:
                continue
            if not _matches_time(record, query):
                continue
            matched += 1
    
            score = scorer(record, query)
            if not isinstance(score, Score) or score.semantics != "trlw-ranking":
                raise TRLWError("ranker must return Score with semantics='trlw-ranking'")
            encoded_size = len(canonical_json(record).encode("utf-8"))
            if encoded_size > query.byte_budget:
                budget_exhausted = True
                continue
    
            if any(entry.record.envelope.record_id == record.envelope.record_id for entry in selected):
                continue
            candidate = TRLWEntry(record, score, encoded_size, source_order=seen)
            selected.append(candidate)
            selected.sort(key=lambda item: (
                -float(item.ranking_score.value), item.source_order,
            ))
            selected_bytes += encoded_size
            while selected and (
                len(selected) > query.max_records or selected_bytes > query.byte_budget
            ):
                removed = selected.pop()
                selected_bytes -= removed.serialized_bytes
                budget_exhausted = True
    except ScanBudgetExceeded:
        effective_source_complete = False
        budget_exhausted = True

    if not effective_source_complete:
        status = PacketStatus.SOURCE_INCOMPLETE
    elif budget_exhausted:
        status = PacketStatus.BUDGET_EXHAUSTED
    elif not selected:
        status = PacketStatus.NOT_FOUND
    else:
        status = PacketStatus.COMPLETE
    return MemoryPacket(
        query_goal=query.query_goal,
        scope=query.scope,
        entries=tuple(selected),
        status=status,
        input_records_seen=seen,
        matched_records_seen=matched,
        returned_records=len(selected),
        serialized_bytes=selected_bytes,
        byte_budget=query.byte_budget,
        max_records=query.max_records,
        source_complete=effective_source_complete,
        budget_exhausted=budget_exhausted,
    )


def build_trlw_working_set_from_store(
    reader, query: TRLWQuery, *, ranker: Ranker | None = None,
) -> MemoryPacket:
    """Build a TRLW packet directly from the bounded persistent M2 reader."""
    if not isinstance(query, TRLWQuery):
        raise TRLWError("query must be TRLWQuery")
    if getattr(reader, "scope", None) != query.scope:
        raise TRLWError("semantic-unit reader scope does not match TRLW query")
    records = reader.iter_current_candidates(max_events=query.max_scan_events)
    return build_trlw_working_set(
        records, query, ranker=ranker, source_complete=True,
    )
