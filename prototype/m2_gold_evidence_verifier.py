"""Verify gold annotation spans against immutable M1 source bytes."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Protocol

from prototype.m2_extraction_dataset import AnnotatedExtractionRecord
from prototype.observation_contract import EvidenceRef, record_digest


class GoldEvidenceVerificationError(ValueError):
    """A gold annotation cannot be proven against its referenced M1 source bytes."""


@dataclass(frozen=True)
class ResolvedEvidenceLike:
    reference: EvidenceRef
    text: str


class EvidenceResolver(Protocol):
    def resolve(self, reference: EvidenceRef) -> ResolvedEvidenceLike:
        """Resolve and integrity-check one immutable M1 evidence chunk."""
        ...


@dataclass(frozen=True)
class GoldEvidenceVerificationReceipt:
    case_id: str
    verified_span_count: int
    verified_unit_count: int
    resolved_evidence_refs: tuple[EvidenceRef, ...]
    record_sha256: str
    verification_sha256: str


def verify_gold_evidence_spans(
    record: AnnotatedExtractionRecord,
    resolver: EvidenceResolver,
) -> GoldEvidenceVerificationReceipt:
    """Resolve one M1 chunk at a time and verify every gold span digest.

    Gold span offsets are absolute source-byte offsets. The resolver authenticates
    each full EvidenceRef/chunk; this function then slices the UTF-8 bytes using
    offsets relative to that chunk. Source bytes are discarded before resolving
    the next chunk, so working memory is bounded by the largest referenced
    chunk plus the record's small span metadata.
    """
    if not isinstance(record, AnnotatedExtractionRecord):
        raise TypeError("record must be AnnotatedExtractionRecord")
    if not callable(getattr(resolver, "resolve", None)):
        raise TypeError("resolver must provide resolve(EvidenceRef)")

    spans_by_reference: dict[EvidenceRef, list] = {
        reference: [] for reference in record.evidence_refs
    }
    for span in record.gold_evidence_spans:
        spans_by_reference[span.evidence_ref].append(span)

    verified_span_material = []
    covered_units: set[int] = set()
    for reference in record.evidence_refs:
        try:
            resolved = resolver.resolve(reference)
        except Exception as exc:
            raise GoldEvidenceVerificationError(
                f"failed to resolve gold source evidence {reference.document_id}/{reference.chunk_id}: {exc}"
            ) from exc
        if getattr(resolved, "reference", None) != reference:
            raise GoldEvidenceVerificationError("resolver returned evidence for a different reference")
        text = getattr(resolved, "text", None)
        if not isinstance(text, str):
            raise GoldEvidenceVerificationError("resolver must return decoded UTF-8 source text")
        raw = text.encode("utf-8")
        if len(raw) != reference.byte_end - reference.byte_start:
            raise GoldEvidenceVerificationError("resolved UTF-8 byte length does not match EvidenceRef span")
        if hashlib.sha256(raw).hexdigest() != reference.content_sha256:
            raise GoldEvidenceVerificationError("resolved source bytes do not match EvidenceRef content hash")

        for span in spans_by_reference[reference]:
            local_start = span.byte_start - reference.byte_start
            local_end = span.byte_end - reference.byte_start
            source_slice = raw[local_start:local_end]
            if len(source_slice) != span.byte_end - span.byte_start:
                raise GoldEvidenceVerificationError("gold span offsets exceed resolved source bytes")
            actual_digest = hashlib.sha256(source_slice).hexdigest()
            if actual_digest != span.span_sha256:
                raise GoldEvidenceVerificationError(
                    f"gold evidence span digest mismatch for unit index {span.unit_index}"
                )
            covered_units.add(span.unit_index)
            verified_span_material.append({
                "unit_index": span.unit_index,
                "evidence_ref": span.evidence_ref,
                "byte_start": span.byte_start,
                "byte_end": span.byte_end,
                "span_sha256": actual_digest,
            })
        # Do not retain raw chunk bytes after its spans have been checked.
        del raw

    expected_units = set(range(len(record.case.expected_units)))
    if covered_units != expected_units:
        raise GoldEvidenceVerificationError("verified gold spans do not cover every positive gold unit")

    record_sha256 = record_digest(record)
    verification_material = {
        "case_id": record.case.case_id,
        "record_sha256": record_sha256,
        "resolved_evidence_refs": record.evidence_refs,
        "verified_spans": verified_span_material,
    }
    return GoldEvidenceVerificationReceipt(
        case_id=record.case.case_id,
        verified_span_count=len(verified_span_material),
        verified_unit_count=len(covered_units),
        resolved_evidence_refs=record.evidence_refs,
        record_sha256=record_sha256,
        verification_sha256=record_digest(verification_material),
    )
