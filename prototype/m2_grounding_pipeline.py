"""Bounded M2 entity-grounding boundary over immutable semantic candidates.

The resolver is injected. This module records identity-resolution decisions;
it does not adjudicate truth, mutate observations, or create a second ledger.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Protocol

from prototype.m2_semantic_unit_store import (
    PersistentSemanticUnitCandidateStore,
    SemanticUnitReceipt,
)
from prototype.observation_contract import (
    EvidenceRef,
    GroundingStatus,
    SemanticUnitCandidate,
    TruthStatus,
    record_digest,
)


class GroundingError(ValueError):
    """A grounding decision violates the typed provenance contract."""


@dataclass(frozen=True)
class GroundingResolution:
    """One resolver decision tied to one immutable candidate and its evidence."""

    candidate_record_id: str
    status: GroundingStatus
    resolver_id: str
    resolver_version: str
    source_refs: tuple[EvidenceRef, ...]
    canonical_key: str | None = None
    matched_surface_form: str | None = None

    def __post_init__(self) -> None:
        for name in ("candidate_record_id", "resolver_id", "resolver_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise GroundingError(f"{name} must be a non-empty string")
        if not isinstance(self.status, GroundingStatus):
            raise GroundingError("status must be GroundingStatus")
        if not isinstance(self.source_refs, tuple) or not self.source_refs:
            raise GroundingError("source_refs must be a non-empty tuple")
        if any(not isinstance(ref, EvidenceRef) for ref in self.source_refs):
            raise GroundingError("source_refs must contain EvidenceRef values")
        if self.status is GroundingStatus.GROUNDED:
            if not isinstance(self.canonical_key, str) or not self.canonical_key.strip():
                raise GroundingError("GROUNDED requires a non-empty canonical_key")
            if not isinstance(self.matched_surface_form, str) or not self.matched_surface_form.strip():
                raise GroundingError("GROUNDED requires the matched source surface form")
        elif self.canonical_key is not None or self.matched_surface_form is not None:
            raise GroundingError(
                "only GROUNDED decisions may carry canonical_key or matched_surface_form"
            )


class EntityGroundingResolver(Protocol):
    """Resolve a candidate against a versioned, scope-authorized entity registry."""

    def resolve(self, candidate: SemanticUnitCandidate) -> GroundingResolution:
        """Return a decision; never infer truth from identity resolution."""
        ...


@dataclass(frozen=True)
class GroundingItemReceipt:
    input_record_id: str
    output_record_id: str
    status: GroundingStatus
    canonical_key: str | None
    persisted_receipt: SemanticUnitReceipt | None


@dataclass(frozen=True)
class GroundingBatchReceipt:
    input_count: int
    grounded_count: int
    unresolved_count: int
    persisted_count: int
    items: tuple[GroundingItemReceipt, ...]


class SemanticUnitGroundingPipeline:
    """Validate a bounded resolver batch, then append immutable revisions.

    All resolver outputs are validated before the first write. A persistence
    failure can still leave a durable prefix because ZPCM appends candidates
    individually; deterministic revision IDs make identical retries idempotent.
    """

    def __init__(
        self,
        resolver: EntityGroundingResolver,
        candidate_store: PersistentSemanticUnitCandidateStore,
        *,
        max_candidates_per_batch: int = 128,
    ) -> None:
        if not callable(getattr(resolver, "resolve", None)):
            raise TypeError("resolver must provide resolve(candidate)")
        if not callable(getattr(candidate_store, "record_candidate", None)):
            raise TypeError("candidate_store must provide record_candidate(candidate)")
        if not isinstance(getattr(candidate_store, "scope", None), str):
            raise TypeError("candidate_store must expose a scope")
        if (isinstance(max_candidates_per_batch, bool)
                or not isinstance(max_candidates_per_batch, int)
                or max_candidates_per_batch < 1):
            raise ValueError("max_candidates_per_batch must be a positive integer")
        self._resolver = resolver
        self._store = candidate_store
        self._limit = max_candidates_per_batch

    def ground_and_persist(
        self, candidates: Iterable[SemanticUnitCandidate],
    ) -> GroundingBatchReceipt:
        try:
            iterator = iter(candidates)
        except TypeError as exc:
            raise GroundingError("candidates must be iterable") from exc

        inputs: list[SemanticUnitCandidate] = []
        seen_ids: set[str] = set()
        for candidate in iterator:
            if len(inputs) >= self._limit:
                raise GroundingError(
                    f"grounding batch exceeded candidate limit ({self._limit})"
                )
            if not isinstance(candidate, SemanticUnitCandidate):
                raise GroundingError("input must contain SemanticUnitCandidate values")
            if candidate.envelope.scope != self._store.scope:
                raise GroundingError("candidate scope does not match candidate store")
            if candidate.grounding_status is not GroundingStatus.UNRESOLVED:
                raise GroundingError("only UNRESOLVED candidates may enter this grounding pass")
            record_id = candidate.envelope.record_id
            if record_id in seen_ids:
                raise GroundingError("grounding batch contains duplicate candidate record_id")
            seen_ids.add(record_id)
            inputs.append(candidate)

        decisions: list[tuple[SemanticUnitCandidate, GroundingResolution, SemanticUnitCandidate | None]] = []
        for candidate in inputs:
            try:
                decision = self._resolver.resolve(candidate)
            except Exception as exc:
                raise GroundingError(
                    f"resolver failed for candidate {candidate.envelope.record_id}: {exc}"
                ) from exc
            if not isinstance(decision, GroundingResolution):
                raise GroundingError("resolver must return GroundingResolution")
            if decision.candidate_record_id != candidate.envelope.record_id:
                raise GroundingError("resolver decision identifies a different candidate")
            if decision.source_refs != candidate.envelope.source_refs:
                raise GroundingError("grounding decision must preserve exact M1 source_refs")
            if (decision.status is GroundingStatus.GROUNDED
                    and decision.matched_surface_form not in candidate.surface_forms):
                raise GroundingError("matched_surface_form must occur in the candidate source forms")

            if decision.status is GroundingStatus.UNRESOLVED:
                revised = None
            else:
                derivation = (
                    f"m2:semantic-unit:{candidate.envelope.record_id}",
                    f"grounding:{decision.resolver_id}:{decision.resolver_version}",
                )
                revision_id = "m2-grounded:" + record_digest({
                    "candidate_digest": record_digest(candidate),
                    "resolver_id": decision.resolver_id,
                    "resolver_version": decision.resolver_version,
                    "status": decision.status.value,
                    "canonical_key": decision.canonical_key,
                    "matched_surface_form": decision.matched_surface_form,
                    "source_refs": decision.source_refs,
                })
                envelope = replace(
                    candidate.envelope,
                    record_id=revision_id,
                    producer=decision.resolver_id,
                    producer_version=decision.resolver_version,
                    derivation_refs=tuple(dict.fromkeys(
                        (*candidate.envelope.derivation_refs, *derivation)
                    )),
                )
                revised = replace(
                    candidate,
                    envelope=envelope,
                    canonical_key=decision.canonical_key,
                    grounding_status=decision.status,
                )
                if (revised.envelope.source_refs != candidate.envelope.source_refs
                        or revised.envelope.scope != candidate.envelope.scope
                        or revised.truth_status is not candidate.truth_status):
                    raise GroundingError("grounding revision changed immutable provenance or truth state")
            decisions.append((candidate, decision, revised))

        items: list[GroundingItemReceipt] = []
        grounded_count = 0
        unresolved_count = 0
        persisted_count = 0
        for candidate, decision, revised in decisions:
            if decision.status is GroundingStatus.GROUNDED:
                grounded_count += 1
            if decision.status is GroundingStatus.UNRESOLVED:
                unresolved_count += 1
            receipt = self._store.record_candidate(revised) if revised is not None else None
            if receipt is not None:
                persisted_count += 1
            output_id = revised.envelope.record_id if revised is not None else candidate.envelope.record_id
            items.append(GroundingItemReceipt(
                input_record_id=candidate.envelope.record_id,
                output_record_id=output_id,
                status=decision.status,
                canonical_key=decision.canonical_key,
                persisted_receipt=receipt,
            ))
        return GroundingBatchReceipt(
            input_count=len(inputs),
            grounded_count=grounded_count,
            unresolved_count=unresolved_count,
            persisted_count=persisted_count,
            items=tuple(items),
        )
