"""Bounded newest-first reader for M2 semantic-unit lifecycle events."""
from __future__ import annotations

from typing import Iterator

from prototype.evidence_ref_resolver import SQLiteEvidenceRefResolver
from prototype.stream_budget import ScanBudgetExceeded
from prototype.m2_semantic_unit_store import (
    EVENT_SCHEMA, EVENT_TYPE, SemanticUnitStoreError, _candidate_from_dict,
)
from prototype.observation_contract import ContractError, SemanticUnitCandidate, record_digest
from prototype.zpcm_memory import ZPCMError, ZPCMMemory


class PersistentM2SemanticUnitReader:
    """Read current candidate versions without restoring the entire history.

    The stream is ordered by the newest lifecycle event first. A bounded set
    tracks roots encountered within the configured scan budget; no corpus-sized
    candidate/history dictionaries are created.
    """

    def __init__(self, memory: ZPCMMemory, resolver: SQLiteEvidenceRefResolver, *,
                 scope: str, page_size: int = 128):
        if not isinstance(memory, ZPCMMemory):
            raise TypeError("memory must be ZPCMMemory")
        if not isinstance(resolver, SQLiteEvidenceRefResolver):
            raise TypeError("resolver must be SQLiteEvidenceRefResolver")
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("scope must be non-empty")
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 4096:
            raise ValueError("page_size must be an integer in [1, 4096]")
        self._memory, self._resolver, self.scope = memory, resolver, scope
        self.page_size = page_size

    def _verify_candidate(self, candidate: SemanticUnitCandidate) -> None:
        if candidate.envelope.scope != self.scope:
            raise SemanticUnitStoreError("candidate scope does not match reader scope")
        refs = list(candidate.envelope.source_refs)
        for attribute in candidate.typed_attributes:
            refs.extend(attribute.source_refs)
        seen = set()
        for ref in refs:
            key = (ref.document_id, ref.chunk_id, ref.content_sha256,
                   ref.byte_start, ref.byte_end, ref.source_version)
            if key not in seen:
                self._resolver.resolve(ref)
                seen.add(key)

    def _candidate_event(self, record_id: str):
        event = self._memory.get_domain_event(
            event_type=EVENT_TYPE, scope=self.scope,
            event_id=f"m2:semantic-unit:{record_id}",
        )
        if event is None:
            raise SemanticUnitStoreError("candidate predecessor is missing from the event log")
        payload = event["payload"]
        if payload.get("schema_version") != EVENT_SCHEMA:
            raise SemanticUnitStoreError("unsupported semantic-unit event schema")
        kind = payload.get("kind")
        if kind not in ("candidate_recorded", "candidate_revised"):
            raise SemanticUnitStoreError("semantic-unit predecessor is not a candidate event")
        body = payload.get("body")
        if not isinstance(body, dict):
            raise SemanticUnitStoreError("candidate event body must be an object")
        candidate = _candidate_from_dict(body)
        self._verify_candidate(candidate)
        if candidate.envelope.record_id != record_id or record_digest(candidate) != payload.get("body_digest"):
            raise SemanticUnitStoreError("candidate event identity or digest mismatch")
        if event["event_id"] != f"m2:semantic-unit:{record_id}":
            raise SemanticUnitStoreError("candidate event ID mismatch")
        previous = payload.get("previous_record_id") if kind == "candidate_revised" else None
        if kind == "candidate_revised":
            if not isinstance(previous, str) or not previous.strip():
                raise SemanticUnitStoreError("revision event has no predecessor")
            if candidate.envelope.derivation_refs.count(previous) != 1:
                raise SemanticUnitStoreError("revision must cite its predecessor exactly once")
        return event, candidate, kind, previous

    def _root_record_id(self, record_id: str) -> str:
        visited = set()
        current = record_id
        for _ in range(1024):
            if current in visited:
                raise SemanticUnitStoreError("semantic-unit revision chain contains a cycle")
            visited.add(current)
            _, candidate, kind, previous = self._candidate_event(current)
            if kind == "candidate_recorded":
                if previous is not None:
                    raise SemanticUnitStoreError("initial candidate cannot name a predecessor")
                return current
            _, predecessor, _, _ = self._candidate_event(previous)
            if predecessor.envelope.scope != candidate.envelope.scope:
                raise SemanticUnitStoreError("revision chain crosses scopes")
            current = previous
        raise SemanticUnitStoreError("semantic-unit revision chain exceeds depth limit")

    def get_current_candidate(
        self, record_id: str, *, max_events: int = 4096,
    ) -> SemanticUnitCandidate | None:
        """Resolve one candidate ID to its latest active version using indexed reads."""
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("record_id must be non-empty")
        if isinstance(max_events, bool) or not isinstance(max_events, int) or not 1 <= max_events <= 65536:
            raise ValueError("max_events must be an integer in [1, 65536]")
        root = self._root_record_id(record_id)
        scanned = 0
        for event in self._memory.iter_domain_events_reverse(
            event_type=EVENT_TYPE, scope=self.scope, page_size=self.page_size,
        ):
            scanned += 1
            if scanned > max_events:
                raise ScanBudgetExceeded(scanned - 1)
            payload = event["payload"]
            if payload.get("schema_version") != EVENT_SCHEMA:
                raise SemanticUnitStoreError("unsupported semantic-unit event schema")
            kind = payload.get("kind")
            if kind in ("candidate_recorded", "candidate_revised"):
                body = payload.get("body")
                if not isinstance(body, dict):
                    raise SemanticUnitStoreError("candidate event body must be an object")
                candidate = _candidate_from_dict(body)
                if candidate.envelope.record_id != event["event_id"].removeprefix("m2:semantic-unit:"):
                    raise SemanticUnitStoreError("candidate event identity mismatch")
                if self._root_record_id(candidate.envelope.record_id) == root:
                    self._verify_candidate(candidate)
                    if record_digest(candidate) != payload.get("body_digest"):
                        raise SemanticUnitStoreError("candidate event digest mismatch")
                    return candidate
            elif kind == "candidate_retracted":
                target_id = payload.get("record_id")
                if not isinstance(target_id, str) or not target_id.strip():
                    raise SemanticUnitStoreError("invalid candidate retraction event")
                if self._root_record_id(target_id) == root:
                    return None
            else:
                raise SemanticUnitStoreError("unknown semantic-unit event kind")
        return None

    def iter_current_candidates(self, *, max_events: int = 4096) -> Iterator[SemanticUnitCandidate]:
        """Yield current, non-retracted candidate versions newest lifecycle event first.

        Raises MemoryScanBudgetExceeded rather than silently treating a truncated
        scan as a complete or not-found result.
        """
        if isinstance(max_events, bool) or not isinstance(max_events, int) or not 1 <= max_events <= 65536:
            raise ValueError("max_events must be an integer in [1, 65536]")
        seen_roots: set[str] = set()
        scanned = 0
        try:
            events = self._memory.iter_domain_events_reverse(
                event_type=EVENT_TYPE, scope=self.scope, page_size=self.page_size,
            )
            for event in events:
                scanned += 1
                if scanned > max_events:
                    raise ScanBudgetExceeded(scanned - 1)
                payload = event["payload"]
                if payload.get("schema_version") != EVENT_SCHEMA:
                    raise SemanticUnitStoreError("unsupported semantic-unit event schema")
                kind = payload.get("kind")
                if kind in ("candidate_recorded", "candidate_revised"):
                    body = payload.get("body")
                    if not isinstance(body, dict):
                        raise SemanticUnitStoreError("candidate event body must be an object")
                    candidate = _candidate_from_dict(body)
                    self._verify_candidate(candidate)
                    record_id = candidate.envelope.record_id
                    if event["event_id"] != f"m2:semantic-unit:{record_id}" or record_digest(candidate) != payload.get("body_digest"):
                        raise SemanticUnitStoreError("candidate event identity or digest mismatch")
                    root = self._root_record_id(record_id)
                    if root in seen_roots:
                        continue
                    seen_roots.add(root)
                    yield candidate
                elif kind == "candidate_retracted":
                    record_id = payload.get("record_id")
                    reason = payload.get("reason")
                    if not isinstance(record_id, str) or not record_id.strip() or not isinstance(reason, str) or not reason.strip():
                        raise SemanticUnitStoreError("invalid candidate retraction event")
                    if event["event_id"] != f"m2:semantic-unit:{record_id}:retracted":
                        raise SemanticUnitStoreError("retraction event identity mismatch")
                    root = self._root_record_id(record_id)
                    if root in seen_roots:
                        raise SemanticUnitStoreError("duplicate or out-of-order candidate retraction")
                    seen_roots.add(root)
                else:
                    raise SemanticUnitStoreError("unknown semantic-unit event kind")
        except (ZPCMError, ContractError, SemanticUnitStoreError, ScanBudgetExceeded):
            raise
        except Exception as exc:
            raise SemanticUnitStoreError(f"semantic-unit stream read failed: {exc}") from exc
