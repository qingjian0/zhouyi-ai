"""Conservative source-lineage audit for classical-text evidence.

This module counts declared witness lineages, not URLs or database records.
It cannot authenticate manuscripts or prove historical independence.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class WitnessKind(str, Enum):
    MANUSCRIPT = "manuscript"
    INSCRIPTION = "inscription"
    PRINTED_EDITION = "printed_edition"
    EDITION_TRANSCRIPTION = "edition_transcription"
    SECONDARY_QUOTATION = "secondary_quotation"
    DIGITAL_TRANSCRIPTION = "digital_transcription"
    MODEL_GENERATED = "model_generated"


class LineageDecision(str, Enum):
    SUFFICIENT_DECLARED_LINEAGES = "sufficient_declared_lineages"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class TextWitness:
    witness_ref: str
    work_id: str
    witness_id: str
    lineage_root_id: str
    kind: WitnessKind
    derives_from: Tuple[str, ...] = ()


@dataclass(frozen=True)
class LineageAssessment:
    work_id: str
    decision: LineageDecision
    independent_lineage_count: int
    lineage_roots: Tuple[str, ...]
    ignored_refs: Tuple[str, ...]
    reason_codes: Tuple[str, ...]


def assess_witness_lineages(
    work_id: str,
    witnesses: Tuple[TextWitness, ...],
    minimum_independent_lineages: int = 2,
) -> LineageAssessment:
    """Count distinct declared roots; do not infer independence from URLs."""
    if not isinstance(work_id, str) or not work_id.strip():
        raise ValueError("work_id is required")
    if not isinstance(witnesses, tuple):
        raise ValueError("witnesses must be a tuple")
    if (not isinstance(minimum_independent_lineages, int)
            or isinstance(minimum_independent_lineages, bool)
            or minimum_independent_lineages < 1):
        raise ValueError("minimum_independent_lineages must be a positive integer")

    refs = set()
    witness_ids = set()
    roots = set()
    ignored = []
    reasons = []

    for item in witnesses:
        if not isinstance(item, TextWitness):
            raise ValueError("each witness must be a TextWitness")
        for name in ("witness_ref", "work_id", "witness_id", "lineage_root_id"):
            value = getattr(item, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(item.kind, WitnessKind):
            raise ValueError("kind must use WitnessKind")
        if not isinstance(item.derives_from, tuple) or any(
            not isinstance(ref, str) or not ref.strip() for ref in item.derives_from
        ):
            raise ValueError("derives_from must be a tuple of non-empty strings")
        if item.work_id != work_id:
            raise ValueError("all witnesses must refer to the requested work")
        if item.witness_ref in refs:
            raise ValueError("witness_ref values must be unique")
        if item.witness_id in witness_ids:
            raise ValueError("witness_id values must be unique")
        refs.add(item.witness_ref)
        witness_ids.add(item.witness_id)

        if item.kind == WitnessKind.MODEL_GENERATED:
            ignored.append(item.witness_ref)
            reasons.append("MODEL_GENERATED_MATERIAL_CANNOT_COUNT_AS_WITNESS")
            continue
        roots.add(item.lineage_root_id)

    if len(roots) < minimum_independent_lineages:
        reasons.append("INSUFFICIENT_DISTINCT_DECLARED_LINEAGES")
    decision = (
        LineageDecision.SUFFICIENT_DECLARED_LINEAGES
        if len(roots) >= minimum_independent_lineages and not ignored
        else LineageDecision.ABSTAIN
    )
    return LineageAssessment(
        work_id=work_id,
        decision=decision,
        independent_lineage_count=len(roots),
        lineage_roots=tuple(sorted(roots)),
        ignored_refs=tuple(sorted(ignored)),
        reason_codes=tuple(sorted(set(reasons))),
    )
