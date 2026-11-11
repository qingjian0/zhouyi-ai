"""YJ-04: bounded discovery of typed relational transition hypotheses.

This is a transparent structural-delta baseline. It proposes mechanisms from
observed transitions; it does not infer causality from correlation or discover
unbounded semantics from raw language.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Iterable, Sequence


class DiscoveryError(ValueError):
    """Invalid relational state, evidence, or search configuration."""


class EvidenceKind(str, Enum):
    OBSERVATIONAL = "OBSERVATIONAL"
    INTERVENTIONAL = "INTERVENTIONAL"


class CandidateStatus(str, Enum):
    PROPOSED = "PROPOSED"
    INTERVENTION_SUPPORTED = "INTERVENTION_SUPPORTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, order=True)
class Node:
    entity_id: str
    entity_type: str
    role: str

    def __post_init__(self):
        if not all((self.entity_id, self.entity_type, self.role)):
            raise DiscoveryError("node id, type and role are required")


@dataclass(frozen=True, order=True)
class Relation:
    source: str
    target: str
    relation_type: str
    attributes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        if not all((self.source, self.target, self.relation_type)):
            raise DiscoveryError("relation endpoints and type are required")
        if tuple(sorted(self.attributes)) != self.attributes:
            raise DiscoveryError("relation attributes must be sorted")


@dataclass(frozen=True)
class RelationalState:
    nodes: tuple[Node, ...]
    relations: tuple[Relation, ...]
    context: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        ids = [node.entity_id for node in self.nodes]
        roles = [node.role for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise DiscoveryError("entity ids must be unique")
        if len(roles) != len(set(roles)):
            raise DiscoveryError("role bindings must be unique within a state")
        if tuple(sorted(self.context)) != self.context:
            raise DiscoveryError("context fields must be sorted")
        known = set(ids)
        if any(r.source not in known or r.target not in known for r in self.relations):
            raise DiscoveryError("relation references an unknown entity")
        if len(set(self.relations)) != len(self.relations):
            raise DiscoveryError("duplicate relations are not allowed")


@dataclass(frozen=True)
class TransitionObservation:
    before: RelationalState
    after: RelationalState
    intervention: str
    evidence_id: str
    evidence_kind: EvidenceKind
    domain: str

    def __post_init__(self):
        if not self.intervention or not self.evidence_id or not self.domain:
            raise DiscoveryError("intervention, evidence id and domain are required")
        if {n.role: n.entity_type for n in self.before.nodes} != {
            n.role: n.entity_type for n in self.after.nodes
        }:
            raise DiscoveryError("before/after role and type signatures must match")


# A relation pattern is expressed over roles, never concrete entity ids.
Pattern = tuple[str, str, str, tuple[tuple[str, str], ...]]


def _role_map(state: RelationalState) -> dict[str, str]:
    return {node.entity_id: node.role for node in state.nodes}


def _patterns(state: RelationalState) -> set[Pattern]:
    roles = _role_map(state)
    return {
        (roles[r.source], roles[r.target], r.relation_type, r.attributes)
        for r in state.relations
    }


def _signature(state: RelationalState) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((node.role, node.entity_type) for node in state.nodes))


def _context(state: RelationalState) -> dict[str, str]:
    return dict(state.context)


@dataclass(frozen=True)
class MechanismCandidate:
    candidate_id: str
    version: int
    intervention: str
    role_signature: tuple[tuple[str, str], ...]
    required_patterns: tuple[Pattern, ...]
    remove_patterns: tuple[Pattern, ...]
    add_patterns: tuple[Pattern, ...]
    required_context: tuple[tuple[str, str], ...]
    evidence_ids: tuple[str, ...]
    evidence_kinds: tuple[EvidenceKind, ...]
    domains: tuple[str, ...]
    status: CandidateStatus

    @property
    def has_interventional_support(self) -> bool:
        return EvidenceKind.INTERVENTIONAL in self.evidence_kinds

    def predict(
        self, state: RelationalState, intervention: str, *, domain: str
    ) -> RelationalState | None:
        """Apply only within an observed domain and matching structural context."""
        if (
            not domain or domain not in self.domains
            or intervention != self.intervention
            or _signature(state) != self.role_signature
        ):
            return None
        context = _context(state)
        if any(context.get(k) != v for k, v in self.required_context):
            return None
        current = _patterns(state)
        if not set(self.required_patterns).issubset(current):
            return None
        if not set(self.remove_patterns).issubset(current):
            return None
        next_patterns = (current - set(self.remove_patterns)) | set(self.add_patterns)
        roles_to_ids = {node.role: node.entity_id for node in state.nodes}
        relations = tuple(sorted(
            Relation(roles_to_ids[src], roles_to_ids[dst], kind, attrs)
            for src, dst, kind, attrs in next_patterns
        ))
        return RelationalState(state.nodes, relations, state.context)


@dataclass(frozen=True)
class DiscoveryReport:
    candidates: tuple[MechanismCandidate, ...]
    observations_seen: int
    transitions_with_delta: int
    candidate_groups: int
    budget_exhausted: bool


class RelationalOperatorInducer:
    """Group repeated typed relation deltas into bounded candidate hypotheses."""

    def __init__(self, *, min_support: int = 2, max_candidates: int = 256):
        if min_support < 1 or max_candidates < 1:
            raise DiscoveryError("support and candidate budgets must be positive")
        self.min_support = min_support
        self.max_candidates = max_candidates

    @staticmethod
    def _key(row: TransitionObservation):
        before = _patterns(row.before)
        after = _patterns(row.after)
        removed = tuple(sorted(before - after))
        added = tuple(sorted(after - before))
        return (
            row.intervention, _signature(row.before), removed, added
        )

    @staticmethod
    def _common_patterns(rows: Sequence[TransitionObservation]) -> tuple[Pattern, ...]:
        if not rows:
            return ()
        common = _patterns(rows[0].before)
        for row in rows[1:]:
            common.intersection_update(_patterns(row.before))
        return tuple(sorted(common))

    @staticmethod
    def _common_context(rows: Sequence[TransitionObservation]):
        contexts = [_context(row.before) for row in rows]
        if not contexts:
            return ()
        common = {
            key: value for key, value in contexts[0].items()
            if all(other.get(key) == value for other in contexts[1:])
        }
        return tuple(sorted(common.items()))

    def discover(self, observations: Iterable[TransitionObservation]) -> DiscoveryReport:
        rows = tuple(observations)
        if not rows:
            raise DiscoveryError("at least one transition observation is required")
        groups: dict[tuple, list[TransitionObservation]] = {}
        changed = 0
        for row in rows:
            key = self._key(row)
            if not key[2] and not key[3]:
                continue
            changed += 1
            groups.setdefault(key, []).append(row)

        candidates = []
        ordered = sorted(groups.items(), key=lambda item: repr(item[0]))
        exhausted = len(ordered) > self.max_candidates
        for key, support in ordered[:self.max_candidates]:
            intervention, signature, removed, added = key
            kinds = tuple(sorted({r.evidence_kind for r in support}, key=lambda x: x.value))
            status = (
                CandidateStatus.INTERVENTION_SUPPORTED
                if EvidenceKind.INTERVENTIONAL in kinds and len(support) >= self.min_support
                else CandidateStatus.PROPOSED
            )
            payload = json.dumps(
                [intervention, signature, removed, added],
                ensure_ascii=False, separators=(",", ":"), default=str,
            )
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
            candidates.append(MechanismCandidate(
                candidate_id="relop-" + digest,
                version=1,
                intervention=intervention,
                role_signature=signature,
                required_patterns=self._common_patterns(support),
                remove_patterns=removed,
                add_patterns=added,
                required_context=self._common_context(support),
                evidence_ids=tuple(sorted({r.evidence_id for r in support})),
                evidence_kinds=kinds,
                domains=tuple(sorted({r.domain for r in support})),
                status=status,
            ))
        return DiscoveryReport(
            tuple(candidates), len(rows), changed, len(groups), exhausted
        )


@dataclass(frozen=True)
class ValidationResult:
    candidate_id: str
    support: int
    total: int
    mismatched_evidence_ids: tuple[str, ...]
    passed: bool


def validate_candidate(
    candidate: MechanismCandidate,
    held_out: Iterable[TransitionObservation],
) -> ValidationResult:
    """Evaluate on held-out transitions; never feeds results back into induction."""
    rows = tuple(held_out)
    if not rows:
        raise DiscoveryError("held-out transitions are required")
    mismatches = []
    support = 0
    for row in rows:
        predicted = candidate.predict(row.before, row.intervention, domain=row.domain)
        if predicted == row.after:
            support += 1
        else:
            mismatches.append(row.evidence_id)
    return ValidationResult(
        candidate.candidate_id, support, len(rows), tuple(mismatches),
        support == len(rows),
    )


@dataclass(frozen=True)
class ExperimentQuery:
    state: RelationalState
    intervention: str
    domain: str
    query_id: str


@dataclass(frozen=True)
class RankedExperiment:
    query_id: str
    disagreement_bits: float
    predicted_partitions: tuple[tuple[str, ...], ...]
    eligible_candidate_ids: tuple[str, ...]


def rank_experiments(
    candidates: Sequence[MechanismCandidate],
    queries: Iterable[ExperimentQuery],
) -> tuple[RankedExperiment, ...]:
    """Rank externally supplied experiments by candidate prediction disagreement.

    This is finite-pool predictive disagreement, not Bayesian expected
    information gain. The function selects queries; it never executes them.
    """
    ranked = []
    for query in queries:
        buckets: dict[str, list[str]] = {}
        eligible = []
        for candidate in candidates:
            prediction = candidate.predict(
                query.state, query.intervention, domain=query.domain
            )
            if prediction is None:
                continue
            eligible.append(candidate.candidate_id)
            key = repr((prediction.relations, prediction.context))
            buckets.setdefault(key, []).append(candidate.candidate_id)
        if len(buckets) < 2:
            continue
        counts = [len(ids) for ids in buckets.values()]
        total = sum(counts)
        entropy = -sum((n / total) * math.log2(n / total) for n in counts)
        ranked.append(RankedExperiment(
            query.query_id, entropy,
            tuple(sorted(tuple(sorted(ids)) for ids in buckets.values())),
            tuple(sorted(eligible)),
        ))
    ranked.sort(key=lambda item: (-item.disagreement_bits, item.query_id))
    return tuple(ranked)
