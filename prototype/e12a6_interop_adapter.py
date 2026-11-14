"""Read-only adapter from E12-A6 candidate versions to CPG-EI v1 DTOs.

E12-A6 remains the sole owner of candidate lifecycle transitions. This module
projects immutable candidate definitions into interchange contracts; it does
not copy, replay, or mutate the lifecycle ledger.
"""
from __future__ import annotations

from dataclasses import dataclass

from prototype.cpg_interop import CandidateProposal, StructureVersion, digest_json
from prototype.e12a6_lifecycle_contract import Candidate


@dataclass(frozen=True)
class E12A6AdapterResult:
    proposal: CandidateProposal
    structure: StructureVersion


def _canonical_refs(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{name} must be a tuple")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{name} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(sorted(values))


def adapt_candidate(
    candidate: Candidate,
    *,
    scope: str,
    grammar_version: str,
) -> E12A6AdapterResult:
    """Project one immutable E12-A6 candidate version into shared DTOs.

    Scope and grammar version are explicit inputs because the native E12-A6
    Candidate type intentionally does not own either cross-track concept.
    """
    if not isinstance(candidate, Candidate):
        raise TypeError("candidate must be an E12-A6 Candidate")
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("scope must be a non-empty string")
    if not isinstance(grammar_version, str) or not grammar_version.strip():
        raise ValueError("grammar_version must be a non-empty string")

    evidence_refs = _canonical_refs(candidate.evidence_ids, "evidence_ids")
    parent_refs = _canonical_refs(candidate.parent_refs, "parent_refs")
    definition = {
        "canonical_expression": candidate.canonical_expression,
        "conditions": list(candidate.conditions),
        "input_types": list(candidate.input_types),
        "operator": candidate.operator,
    }
    definition_digest = digest_json(definition)
    candidate_ref = f"{candidate.candidate_id}@{candidate.version}"

    proposal = CandidateProposal(
        candidate_ref=candidate_ref,
        track_id="e12a6",
        scope=scope,
        grammar_version=grammar_version,
        definition_digest=definition_digest,
        evidence_refs=evidence_refs,
        estimated_cost=float(candidate.proposal_cost),
        complexity=candidate.complexity,
    )
    structure = StructureVersion(
        structure_id=candidate.candidate_id,
        version=candidate.version,
        track_id="e12a6",
        scope=scope,
        grammar_version=grammar_version,
        definition_digest=definition_digest,
        parent_refs=parent_refs,
        evidence_refs=evidence_refs,
    )
    return E12A6AdapterResult(proposal=proposal, structure=structure)
