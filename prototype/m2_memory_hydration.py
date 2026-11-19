"""Bounded restoration of source evidence referenced by an M2 memory packet.

The packet remains a compact provenance projection. This module resolves only
its selected EvidenceRefs under independent count and byte budgets; it does
not rank candidates or adjudicate truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from prototype.m2_memory_packet import MemoryPacket, PacketCompleteness
from prototype.observation_contract import EvidenceRef


class EvidenceBatchResolver(Protocol):
    def resolve_many(self, references: list[EvidenceRef]):
        """Resolve references in input order within one consistent read snapshot."""


class MemoryHydrationError(ValueError):
    """A packet or resolver response violates the hydration contract."""


@dataclass(frozen=True)
class HydratedEvidence:
    record_id: str
    reference: EvidenceRef
    text: str
    ordinal: int


@dataclass(frozen=True)
class HydratedMemoryPacket:
    packet: MemoryPacket
    evidence: tuple[HydratedEvidence, ...]
    completeness: PacketCompleteness
    unique_references_seen: int
    resolved_references: int
    evidence_bytes: int
    evidence_byte_budget: int
    evidence_ref_budget: int


def hydrate_memory_packet(
    packet: MemoryPacket,
    resolver: EvidenceBatchResolver,
    *,
    max_evidence_refs: int = 128,
    max_evidence_bytes: int = 256 * 1024,
) -> HydratedMemoryPacket:
    """Restore referenced text under hard per-call reference and UTF-8 byte budgets.

    Duplicate EvidenceRefs are resolved once and associated with every packet
    record that cites them. Selection is deterministic: packet order, then
    source_refs order. If a budget prevents resolving every unique reference,
    completeness is BUDGET_EXHAUSTED rather than COMPLETE.
    """
    if not isinstance(packet, MemoryPacket):
        raise TypeError("packet must be MemoryPacket")
    if not callable(getattr(resolver, "resolve_many", None)):
        raise MemoryHydrationError("resolver must expose resolve_many(references)")
    for name, value, upper in (
        ("max_evidence_refs", max_evidence_refs, 4096),
        ("max_evidence_bytes", max_evidence_bytes, 4 * 1024 * 1024),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= upper:
            raise MemoryHydrationError(f"{name} must be an integer in [1, {upper}]")

    owners: dict[EvidenceRef, list[str]] = {}
    ordered: list[EvidenceRef] = []
    for item in packet.items:
        for reference in item.source_refs:
            if reference not in owners:
                owners[reference] = []
                ordered.append(reference)
            owners[reference].append(item.record_id)

    selected: list[EvidenceRef] = []
    selected_bytes = 0
    truncated = False
    for reference in ordered:
        span_bytes = reference.byte_end - reference.byte_start
        if len(selected) >= max_evidence_refs or selected_bytes + span_bytes > max_evidence_bytes:
            truncated = True
            break
        selected.append(reference)
        selected_bytes += span_bytes

    resolved = resolver.resolve_many(selected) if selected else []
    if not isinstance(resolved, list) or len(resolved) != len(selected):
        raise MemoryHydrationError("resolver must return one result per selected reference in order")

    hydrated: list[HydratedEvidence] = []
    actual_bytes = 0
    for expected, result in zip(selected, resolved):
        if getattr(result, "reference", None) != expected:
            raise MemoryHydrationError("resolver result reference/order mismatch")
        text = getattr(result, "text", None)
        ordinal = getattr(result, "ordinal", None)
        if not isinstance(text, str):
            raise MemoryHydrationError("resolver result text must be str")
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
            raise MemoryHydrationError("resolver result ordinal must be a non-negative integer")
        encoded_bytes = len(text.encode("utf-8"))
        if encoded_bytes != expected.byte_end - expected.byte_start:
            raise MemoryHydrationError("resolved UTF-8 byte length does not match EvidenceRef span")
        actual_bytes += encoded_bytes
        for record_id in owners[expected]:
            hydrated.append(HydratedEvidence(record_id, expected, text, ordinal))

    if actual_bytes > max_evidence_bytes:
        raise MemoryHydrationError("resolver output exceeded the evidence byte budget")
    completeness = packet.completeness
    if truncated:
        completeness = PacketCompleteness.BUDGET_EXHAUSTED
    return HydratedMemoryPacket(
        packet=packet,
        evidence=tuple(hydrated),
        completeness=completeness,
        unique_references_seen=len(ordered),
        resolved_references=len(selected),
        evidence_bytes=actual_bytes,
        evidence_byte_budget=max_evidence_bytes,
        evidence_ref_budget=max_evidence_refs,
    )
