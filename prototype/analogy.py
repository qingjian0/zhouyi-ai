"""Evidence-gated, relation-preserving analogy evaluation.

A deterministic baseline for one falsifiable part of 取象比类. This is not a
learned model and does not claim to implement all Zhouyi theory.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

ANALOGY_DIMENSIONS = frozenset({
    "morphology", "attribute", "function", "relation",
    "process", "spatiotemporal", "potential", "integrated",
})

@dataclass(frozen=True)
class Relation:
    source: str
    target: str
    kind: str

@dataclass(frozen=True)
class Evidence:
    reference: str
    supports: bool
    note: str = ""

@dataclass(frozen=True)
class AnalogyCandidate:
    candidate_id: str
    source_domain: str
    target_domain: str
    source_entities: tuple[str, ...]
    target_entities: tuple[str, ...]
    mapping: Mapping[str, str]
    dimensions: tuple[str, ...]
    source_relations: tuple[Relation, ...] = ()
    target_relations: tuple[Relation, ...] = ()
    conditions: tuple[str, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    counterexamples: tuple[Evidence, ...] = ()
    declared_confidence: float | None = None
    validity_scope: str = ""

@dataclass(frozen=True)
class AnalogyAssessment:
    candidate_id: str
    accepted: bool
    reason_codes: tuple[str, ...]
    relation_precision: float
    relation_recall: float
    relation_f1: float
    mapped_entity_coverage: float
    evidence_support_ratio: float
    counterexample_count: int
    threshold: float

def _f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2.0 * precision * recall / (precision + recall)

def assess_analogy(
    candidate: AnalogyCandidate, *,
    min_relation_f1: float = 0.8,
    min_entity_coverage: float = 1.0,
    require_evidence: bool = True,
    reject_on_counterexample: bool = False,
) -> AnalogyAssessment:
    """Check exact directed relation preservation under an explicit mapping.

    Relation kinds are exact and directed by default. Symmetry, inverse
    relations, and causal semantics must be modeled explicitly elsewhere.
    """
    if not 0.0 <= min_relation_f1 <= 1.0:
        raise ValueError("min_relation_f1 must be in [0, 1]")
    if not 0.0 <= min_entity_coverage <= 1.0:
        raise ValueError("min_entity_coverage must be in [0, 1]")
    if not candidate.candidate_id or not candidate.source_domain or not candidate.target_domain:
        raise ValueError("candidate id and both domains are required")
    if not candidate.dimensions:
        raise ValueError("at least one analogy dimension is required")
    unknown = set(candidate.dimensions) - ANALOGY_DIMENSIONS
    if unknown:
        raise ValueError(f"unknown analogy dimensions: {sorted(unknown)}")
    if len(set(candidate.dimensions)) != len(candidate.dimensions):
        raise ValueError("analogy dimensions must be unique")
    if len(set(candidate.source_entities)) != len(candidate.source_entities):
        raise ValueError("source entity ids must be unique")
    if len(set(candidate.target_entities)) != len(candidate.target_entities):
        raise ValueError("target entity ids must be unique")
    if any(s not in candidate.source_entities for s in candidate.mapping):
        raise ValueError("mapping contains an unknown source entity")
    if any(t not in candidate.target_entities for t in candidate.mapping.values()):
        raise ValueError("mapping points to an unknown target entity")
    if len(set(candidate.mapping.values())) != len(candidate.mapping):
        raise ValueError("mapping must be one-to-one for this baseline")
    if any(r.source not in candidate.source_entities or r.target not in candidate.source_entities for r in candidate.source_relations):
        raise ValueError("source relation references an unknown entity")
    if any(r.source not in candidate.target_entities or r.target not in candidate.target_entities for r in candidate.target_relations):
        raise ValueError("target relation references an unknown entity")
    if candidate.declared_confidence is not None and not 0.0 <= candidate.declared_confidence <= 1.0:
        raise ValueError("declared_confidence must be in [0, 1]")

    n = len(candidate.source_entities)
    coverage = len(candidate.mapping) / n if n else 0.0
    expected = {
        (candidate.mapping[r.source], candidate.mapping[r.target], r.kind)
        for r in candidate.source_relations
        if r.source in candidate.mapping and r.target in candidate.mapping
    }
    observed = {(r.source, r.target, r.kind) for r in candidate.target_relations}
    preserved = len(expected & observed)
    precision = preserved / len(observed) if observed else (1.0 if not expected else 0.0)
    recall = preserved / len(expected) if expected else (1.0 if not observed else 0.0)
    relation_f1 = _f1(precision, recall)
    support_count = sum(e.supports for e in candidate.evidence)
    evidence_count = len(candidate.evidence)
    evidence_ratio = support_count / evidence_count if evidence_count else 0.0
    counterexample_count = len(candidate.counterexamples)

    reasons = []
    if coverage < min_entity_coverage:
        reasons.append("INSUFFICIENT_ENTITY_COVERAGE")
    if relation_f1 < min_relation_f1:
        reasons.append("RELATION_STRUCTURE_NOT_PRESERVED")
    if require_evidence and (not evidence_count or not support_count):
        reasons.append("INSUFFICIENT_SUPPORTING_EVIDENCE")
    if reject_on_counterexample and counterexample_count:
        reasons.append("UNRESOLVED_COUNTEREXAMPLE")
    if not candidate.validity_scope.strip():
        reasons.append("MISSING_VALIDITY_SCOPE")
    if not candidate.conditions:
        reasons.append("MISSING_CONDITIONS")

    return AnalogyAssessment(
        candidate_id=candidate.candidate_id, accepted=not reasons,
        reason_codes=tuple(reasons), relation_precision=precision,
        relation_recall=recall, relation_f1=relation_f1,
        mapped_entity_coverage=coverage, evidence_support_ratio=evidence_ratio,
        counterexample_count=counterexample_count, threshold=min_relation_f1,
    )
