"""Bounded lexical retrieval over the append-only M2 candidate stream.

This is an explicit lexical baseline, not semantic/vector retrieval. It keeps
only top-k candidates in memory and reports scan truncation conservatively.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import islice
import re

from prototype.m2_memory_packet import (
    MemoryPacket,
    MemoryQuery,
    PacketCompleteness,
    _matches,
    build_memory_packet,
)
from prototype.observation_contract import SemanticUnitCandidate, canonical_json


class LexicalRetrievalError(ValueError):
    """Invalid lexical retrieval request or source."""


def _terms(text: str) -> frozenset[str]:
    terms: set[str] = set()
    # Keep CJK runs separate: bigrams must not cross whitespace or punctuation.
    for match in re.finditer(r"[a-z0-9]+|[\u3400-\u9fff]+", text.casefold()):
        piece = match.group(0)
        if piece[0] >= "\u3400":
            terms.update(piece)
            terms.update(piece[index:index + 2] for index in range(len(piece) - 1))
        else:
            terms.add(piece)
    return frozenset(terms)


def _candidate_text(candidate: SemanticUnitCandidate) -> str:
    fields = list(candidate.surface_forms)
    for attribute in candidate.typed_attributes:
        fields.extend((attribute.name, attribute.value_type, str(attribute.value)))
        if attribute.unit:
            fields.append(attribute.unit)
    for role in candidate.role_bindings:
        fields.extend((role.role_name, role.target_ref))
    if candidate.canonical_key:
        fields.append(candidate.canonical_key)
    return " ".join(fields)


@dataclass(frozen=True)
class LexicalRetrievalReport:
    packet: MemoryPacket
    candidates_scanned: int
    candidates_matched: int
    candidates_ranked: int
    scan_budget_exhausted: bool
    ranking_policy: str = "lexical-overlap-v1"


def retrieve_lexical_memory(
    reader,
    query: MemoryQuery,
) -> LexicalRetrievalReport:
    """Retrieve lexical top-k with O(max_records) candidate retention.

    Query matching uses CJK unigrams/bigrams and case-folded Latin/digit terms.
    Score is unique query-term coverage, so it is deterministic and bounded in
    [0, 1]. Ties break by immutable record_id. The append-only M2 store enforces
    immutable event IDs derived from record_id, so duplicate record IDs cannot
    be appended with distinct content. Scan-budget exhaustion is conservative
    when the exact cap is reached because the iterator is not advanced beyond
    the configured budget.
    """
    if not isinstance(query, MemoryQuery):
        raise TypeError("query must be MemoryQuery")
    if getattr(reader, "scope", None) != query.scope:
        raise LexicalRetrievalError("candidate reader scope does not match query scope")
    query_terms = _terms(query.query_goal)
    if not query_terms:
        raise LexicalRetrievalError("query_goal must contain searchable terms")

    iterator = getattr(reader, "iter_candidates", None)
    if not callable(iterator):
        raise LexicalRetrievalError("reader must expose iter_candidates(page_size=...)")

    ranked: list[tuple[float, str, SemanticUnitCandidate]] = []
    scanned = matched = 0
    candidates = iterator(page_size=128)
    for candidate in islice(candidates, query.max_scan_events):
        scanned += 1
        if not isinstance(candidate, SemanticUnitCandidate):
            raise LexicalRetrievalError("candidate stream contains a non-candidate record")
        if not _matches(candidate, query):
            continue
        matched += 1
        record_id = candidate.envelope.record_id
        candidate_terms = _terms(_candidate_text(candidate))
        score = len(query_terms & candidate_terms) / len(query_terms)
        ranked.append((score, record_id, candidate))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        if len(ranked) > query.max_records:
            ranked.pop()

    # Conservative by design: an exact-cap scan may have more rows remaining.
    scan_exhausted = scanned >= query.max_scan_events
    ordered = [entry[2] for entry in ranked]
    for candidate in ordered:
        canonical_json(candidate)
    packet = build_memory_packet(ordered, replace(query, ranking_policy="lexical-overlap-v1"))
    packet = replace(
        packet,
        completeness=(
            PacketCompleteness.BUDGET_EXHAUSTED
            if scan_exhausted else packet.completeness
        ),
        records_scanned=scanned,
    )
    return LexicalRetrievalReport(
        packet=packet,
        candidates_scanned=scanned,
        candidates_matched=matched,
        candidates_ranked=len(ranked),
        scan_budget_exhausted=scan_exhausted,
    )
