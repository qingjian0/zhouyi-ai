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
    for name, value in (("min_relation_f1", min_relation_f1), ("min_entity_coverage", min_entity_coverage)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be a finite number in [0, 1]")
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
    if not candidate.source_relations or not candidate.target_relations:
        reasons.append("INSUFFICIENT_RELATION_DATA")
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

@dataclass(frozen=True)
class DiscoveredAnalogy:
    mapping: tuple[tuple[str, str], ...]
    assessment: AnalogyAssessment


@dataclass(frozen=True)
class AnalogyDiscoveryResult:
    candidates: tuple[DiscoveredAnalogy, ...]
    evaluated_mappings: int
    truncated: bool


def discover_analogy_mappings(
    *,
    source_domain: str,
    target_domain: str,
    source_entities: tuple[str, ...],
    target_entities: tuple[str, ...],
    source_relations: tuple[Relation, ...],
    target_relations: tuple[Relation, ...],
    dimensions: tuple[str, ...] = ("relation",),
    conditions: tuple[str, ...] = ("candidate mapping is evaluated under the supplied graph snapshot",),
    evidence: tuple[Evidence, ...] = (),
    validity_scope: str = "the supplied finite entity and relation graphs only",
    min_relation_f1: float = 0.8,
    max_evaluations: int = 10000,
    max_results: int = 20,
) -> AnalogyDiscoveryResult:
    """Enumerate and rank injective source-to-target mappings by relation fit.

    This bounded exhaustive baseline is useful for small symbolic graphs. It
    does not infer entities, relation labels, or domain semantics. A truncated
    search is explicitly reported; results must not be treated as exhaustive.
    """
    from itertools import islice, permutations

    if not source_domain.strip() or not target_domain.strip():
        raise ValueError("source_domain and target_domain must be non-empty")
    if not source_entities or not target_entities:
        raise ValueError("source_entities and target_entities must be non-empty")
    if not dimensions or len(set(dimensions)) != len(dimensions) or set(dimensions) - ANALOGY_DIMENSIONS:
        raise ValueError("dimensions must be non-empty, unique, and known")
    if isinstance(min_relation_f1, bool) or not isinstance(min_relation_f1, (int, float)) or not 0.0 <= min_relation_f1 <= 1.0:
        raise ValueError("min_relation_f1 must be a finite number in [0, 1]")
    if len(source_entities) > len(target_entities):
        raise ValueError("target graph must have at least as many entities as source graph")
    if len(set(source_entities)) != len(source_entities):
        raise ValueError("source entity ids must be unique")
    if len(set(target_entities)) != len(target_entities):
        raise ValueError("target entity ids must be unique")
    if type(max_evaluations) is not int or type(max_results) is not int or max_evaluations < 1 or max_results < 1:
        raise ValueError("max_evaluations and max_results must be positive integers")
    if not source_relations or not target_relations:
        raise ValueError("both graphs must contain relations for analogy discovery")

    ranked: list[DiscoveredAnalogy] = []
    evaluated = 0
    iterator = permutations(target_entities, len(source_entities))
    for targets in islice(iterator, max_evaluations):
        mapping = dict(zip(source_entities, targets))
        candidate = AnalogyCandidate(
            candidate_id=f"discovery-{evaluated + 1}",
            source_domain=source_domain,
            target_domain=target_domain,
            source_entities=source_entities,
            target_entities=target_entities,
            mapping=mapping,
            dimensions=dimensions,
            source_relations=source_relations,
            target_relations=target_relations,
            conditions=conditions,
            evidence=evidence,
            validity_scope=validity_scope,
        )
        assessment = assess_analogy(
            candidate, min_relation_f1=min_relation_f1,
            min_entity_coverage=1.0, require_evidence=True,
        )
        ranked.append(DiscoveredAnalogy(
            mapping=tuple(mapping.items()), assessment=assessment,
        ))
        evaluated += 1

    total_mappings = 1
    for factor in range(len(target_entities) - len(source_entities) + 1, len(target_entities) + 1):
        total_mappings *= factor
    truncated = evaluated < total_mappings
    ranked.sort(key=lambda item: (
        -item.assessment.relation_f1,
        -item.assessment.relation_precision,
        -item.assessment.relation_recall,
        item.mapping,
    ))
    return AnalogyDiscoveryResult(
        candidates=tuple(ranked[:max_results]),
        evaluated_mappings=evaluated,
        truncated=truncated,
    )

