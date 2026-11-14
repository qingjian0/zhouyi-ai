"""Bounded, provenance-preserving M2 MemoryPacket construction.

The builder consumes a caller-ranked stream and never stores the candidate corpus.
It emits compact references and typed status metadata, never source text.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Iterator

from prototype.observation_contract import (
    EvidenceRef, GroundingStatus, SemanticUnitCandidate, TruthStatus,
    UnitKind, canonical_json,
)
from prototype.stream_budget import ScanBudgetExceeded


class MemoryPacketError(ValueError):
    """A query or packet violates the bounded retrieval contract."""


MemoryScanBudgetExceeded = ScanBudgetExceeded


class PacketCompleteness(str, Enum):
    COMPLETE = "COMPLETE"
    NOT_FOUND = "NOT_FOUND"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


def _time_key(value: str, field: str):
    if not isinstance(value, str) or not value.strip():
        raise MemoryPacketError(f"{field} must be a non-empty ISO-8601 date/time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MemoryPacketError(f"{field} must be a valid ISO-8601 date/time") from exc
    if parsed.tzinfo is None:
        return ("naive", parsed)
    return ("aware", parsed.astimezone(timezone.utc))


@dataclass(frozen=True)
class MemoryQuery:
    query_goal: str
    scope: str
    required_types: tuple[UnitKind, ...]
    max_records: int
    byte_budget: int
    ranking_policy: str
    valid_time_start: str | None = None
    valid_time_end: str | None = None
    max_scan_events: int = 4096

    def __post_init__(self) -> None:
        if not isinstance(self.query_goal, str) or not self.query_goal.strip():
            raise MemoryPacketError("query_goal must be non-empty")
        if not isinstance(self.scope, str) or not self.scope.strip():
            raise MemoryPacketError("scope must be non-empty")
        if not self.required_types or any(not isinstance(x, UnitKind) for x in self.required_types):
            raise MemoryPacketError("required_types must contain UnitKind values")
        if len(set(self.required_types)) != len(self.required_types):
            raise MemoryPacketError("required_types must not contain duplicates")
        if isinstance(self.max_records, bool) or not isinstance(self.max_records, int) or self.max_records < 1:
            raise MemoryPacketError("max_records must be a positive integer")
        if isinstance(self.byte_budget, bool) or not isinstance(self.byte_budget, int) or self.byte_budget < 1:
            raise MemoryPacketError("byte_budget must be a positive integer")
        if not isinstance(self.ranking_policy, str) or not self.ranking_policy.strip():
            raise MemoryPacketError("ranking_policy must be explicit")
        if (isinstance(self.max_scan_events, bool) or not isinstance(self.max_scan_events, int)
                or not 1 <= self.max_scan_events <= 65536):
            raise MemoryPacketError("max_scan_events must be an integer in [1, 65536]")
        if (self.valid_time_start is None) != (self.valid_time_end is None):
            raise MemoryPacketError("temporal filter endpoints must be supplied together")
        if self.valid_time_start is not None:
            start_mode, start = _time_key(self.valid_time_start, "valid_time_start")
            end_mode, end = _time_key(self.valid_time_end, "valid_time_end")
            if start_mode != end_mode:
                raise MemoryPacketError("temporal filter endpoints must use compatible timezone forms")
            if start > end:
                raise MemoryPacketError("valid_time_start must not be after valid_time_end")


@dataclass(frozen=True)
class MemoryPacketItem:
    record_id: str
    kind: UnitKind
    source_refs: tuple[EvidenceRef, ...]
    derivation_refs: tuple[str, ...]
    role_bindings: tuple[tuple[str, str], ...]
    grounding_status: GroundingStatus
    truth_status: TruthStatus
    valid_time_start: str | None
    valid_time_end: str | None


@dataclass(frozen=True)
class MemoryPacket:
    schema_version: str
    query_goal: str
    scope: str
    ranking_policy: str
    items: tuple[MemoryPacketItem, ...]
    completeness: PacketCompleteness
    serialized_bytes: int
    byte_budget: int
    records_scanned: int


def _matches(candidate: SemanticUnitCandidate, query: MemoryQuery) -> bool:
    env = candidate.envelope
    if env.scope != query.scope or candidate.kind not in query.required_types:
        return False
    if query.valid_time_start is not None:
        # Conservative overlap test. Missing candidate validity is not treated
        # as matching a bounded temporal query.
        if env.valid_time_start is None or env.valid_time_end is None:
            return False
        candidate_start_mode, candidate_start = _time_key(env.valid_time_start, "candidate.valid_time_start")
        candidate_end_mode, candidate_end = _time_key(env.valid_time_end, "candidate.valid_time_end")
        query_start_mode, query_start = _time_key(query.valid_time_start, "query.valid_time_start")
        query_end_mode, query_end = _time_key(query.valid_time_end, "query.valid_time_end")
        if candidate_start_mode != candidate_end_mode or candidate_start > candidate_end:
            raise MemoryPacketError("candidate valid-time interval is malformed")
        if query_start_mode != query_end_mode or candidate_start_mode != query_start_mode:
            raise MemoryPacketError("candidate and query valid-time timezone forms are incompatible")
        if candidate_end < query_start or candidate_start > query_end:
            return False
    return True


def _item(candidate: SemanticUnitCandidate) -> MemoryPacketItem:
    env = candidate.envelope
    return MemoryPacketItem(
        record_id=env.record_id,
        kind=candidate.kind,
        source_refs=env.source_refs,
        derivation_refs=env.derivation_refs,
        role_bindings=tuple((x.role_name, x.target_ref) for x in candidate.role_bindings),
        grounding_status=candidate.grounding_status,
        truth_status=candidate.truth_status,
        valid_time_start=env.valid_time_start,
        valid_time_end=env.valid_time_end,
    )


def build_memory_packet(candidates: Iterable[SemanticUnitCandidate],
                        query: MemoryQuery) -> MemoryPacket:
    """Build a packet from a pre-ranked stream under hard count/byte limits.

    The input stream's order is authoritative and must already reflect the
    declared ranking_policy. The builder deliberately does not materialize,
    sort, or rerank the candidate corpus.
    """
    if not isinstance(query, MemoryQuery):
        raise TypeError("query must be MemoryQuery")
    selected: list[MemoryPacketItem] = []
    scanned = 0
    completeness = PacketCompleteness.COMPLETE
    try:
        for candidate in candidates:
            scanned += 1
            if not isinstance(candidate, SemanticUnitCandidate):
                raise TypeError("candidate stream must contain SemanticUnitCandidate values")
            if not _matches(candidate, query):
                continue
            if len(selected) >= query.max_records:
                completeness = PacketCompleteness.BUDGET_EXHAUSTED
                break
            proposed = selected + [_item(candidate)]
            probe = {
                "schema_version": "m2-memory-packet-v1",
                "query_goal": query.query_goal,
                "scope": query.scope,
                "ranking_policy": query.ranking_policy,
                "items": proposed,
                "completeness": PacketCompleteness.COMPLETE,
                "byte_budget": query.byte_budget,
            }
            encoded_size = len(canonical_json(probe).encode("utf-8"))
            if encoded_size > query.byte_budget:
                completeness = PacketCompleteness.BUDGET_EXHAUSTED
                break
            selected.append(proposed[-1])
    except ScanBudgetExceeded as exc:
        scanned = max(scanned, exc.records_scanned)
        completeness = PacketCompleteness.BUDGET_EXHAUSTED
    if not selected and completeness == PacketCompleteness.COMPLETE:
        completeness = PacketCompleteness.NOT_FOUND
    def encoded_payload():
        return {
            "schema_version": "m2-memory-packet-v1",
            "query_goal": query.query_goal,
            "scope": query.scope,
            "ranking_policy": query.ranking_policy,
            "items": tuple(selected),
            "completeness": completeness,
            "byte_budget": query.byte_budget,
        }

    payload = encoded_payload()
    serialized_bytes = len(canonical_json(payload).encode("utf-8"))
    # The final completeness marker can be longer than COMPLETE. If that
    # pushes the packet over budget, drop tail items until the envelope fits.
    while serialized_bytes > query.byte_budget and selected:
        selected.pop()
        completeness = PacketCompleteness.BUDGET_EXHAUSTED
        payload = encoded_payload()
        serialized_bytes = len(canonical_json(payload).encode("utf-8"))
    if serialized_bytes > query.byte_budget:
        raise MemoryPacketError("byte_budget is too small for the packet envelope")
    return MemoryPacket(
        schema_version="m2-memory-packet-v1",
        query_goal=query.query_goal,
        scope=query.scope,
        ranking_policy=query.ranking_policy,
        items=tuple(selected),
        completeness=completeness,
        serialized_bytes=serialized_bytes,
        byte_budget=query.byte_budget,
        records_scanned=scanned,
    )

def build_memory_packet_from_store(reader, query: MemoryQuery) -> MemoryPacket:
    """Build a packet directly from a bounded semantic-unit event reader."""
    if not isinstance(query, MemoryQuery):
        raise TypeError("query must be MemoryQuery")
    if getattr(reader, "scope", None) != query.scope:
        raise MemoryPacketError("semantic-unit reader scope does not match query scope")
    if query.ranking_policy != "latest-lifecycle-event-desc-v1":
        raise MemoryPacketError("store reader requires latest-lifecycle-event-desc-v1 ranking")
    stream = reader.iter_current_candidates(max_events=query.max_scan_events)
    return build_memory_packet(stream, query)
