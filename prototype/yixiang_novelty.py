"""M6 residual-driven novelty proposals with explicit review and version history.

Inputs are already annotated residual cases. This module does not extract
features from raw text/perception and never promotes a proposal automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256


class ProposalStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class ResidualCase:
    residual_id: str
    observation_id: str
    domain: str
    signature: tuple[tuple[str, str, str], ...]
    context: tuple[tuple[str, str], ...]
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        for name, value in (("residual_id", self.residual_id),
                            ("observation_id", self.observation_id),
                            ("domain", self.domain)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.signature, tuple) or not self.signature:
            raise ValueError("signature must be a non-empty tuple")
        seen = set()
        for item in self.signature:
            if not isinstance(item, tuple) or len(item) != 3:
                raise ValueError("signature entries must be (dimension, relation, value)")
            if any(not isinstance(part, str) or not part.strip() for part in item):
                raise ValueError("signature fields must be non-empty strings")
            if item in seen:
                raise ValueError("signature entries must be unique")
            seen.add(item)
        if self.signature != tuple(sorted(self.signature)):
            raise ValueError("signature entries must be sorted for deterministic grouping")
        if not isinstance(self.context, tuple):
            raise ValueError("context must be a tuple")
        context_keys = set()
        for item in self.context:
            if (not isinstance(item, tuple) or len(item) != 2
                    or any(not isinstance(part, str) or not part.strip() for part in item)):
                raise ValueError("context entries must be non-empty (key, value) pairs")
            if item[0] in context_keys:
                raise ValueError("context keys must be unique")
            context_keys.add(item[0])
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("each residual requires evidence references")
        if any(not isinstance(ref, str) or not ref.strip() for ref in self.evidence_refs):
            raise ValueError("evidence references must be non-empty strings")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("evidence references must be unique within a residual")


@dataclass(frozen=True)
class NoveltyProposal:
    proposal_id: str
    signature: tuple[tuple[str, str, str], ...]
    support_residual_ids: tuple[str, ...]
    support_observation_ids: tuple[str, ...]
    domains: tuple[str, ...]
    context_values: tuple[tuple[str, tuple[str, ...]], ...]
    evidence_refs: tuple[str, ...]
    status: ProposalStatus = ProposalStatus.PROPOSED
    version: int = 1
    parent_version_id: str | None = None
    decision_note: str = ""


def propose_novel_structures(
    residuals: tuple[ResidualCase, ...],
    *,
    known_signatures: tuple[tuple[tuple[str, str, str], ...], ...] = (),
    min_support: int = 2,
    min_domains: int = 2,
    min_independent_evidence: int = 2,
) -> tuple[NoveltyProposal, ...]:
    """Group exact typed residual signatures; return review-only proposals."""
    if not isinstance(residuals, tuple):
        raise ValueError("residuals must be a tuple")
    for name, value in (("min_support", min_support), ("min_domains", min_domains),
                        ("min_independent_evidence", min_independent_evidence)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if not isinstance(known_signatures, tuple):
        raise ValueError("known_signatures must be a tuple")
    for signature in known_signatures:
        if not isinstance(signature, tuple):
            raise ValueError("known signatures must be tuples")
    for residual in residuals:
        if not isinstance(residual, ResidualCase):
            raise ValueError("residuals must contain ResidualCase values")
        residual.validate()
    residual_ids = [r.residual_id for r in residuals]
    observation_ids = [r.observation_id for r in residuals]
    if len(residual_ids) != len(set(residual_ids)):
        raise ValueError("residual ids must be unique")
    if len(observation_ids) != len(set(observation_ids)):
        raise ValueError("observation ids must be unique across residual cases")

    groups: dict[tuple[tuple[str, str, str], ...], list[ResidualCase]] = {}
    for residual in residuals:
        groups.setdefault(residual.signature, []).append(residual)

    proposals = []
    for signature, cases in groups.items():
        if signature in known_signatures:
            continue
        domains = tuple(sorted({case.domain for case in cases}))
        evidence_refs = tuple(sorted({ref for case in cases for ref in case.evidence_refs}))
        if (len(cases) < min_support or len(domains) < min_domains
                or len(evidence_refs) < min_independent_evidence):
            continue
        context_keys = sorted({key for case in cases for key, _ in case.context})
        context_values = tuple(
            (key, tuple(sorted({value for case in cases for k, value in case.context if k == key})))
            for key in context_keys
        )
        support_ids = tuple(sorted(case.residual_id for case in cases))
        # Stable content-derived ID; no time or random dependency.
        proposal_id = "novel-" + sha256(repr(signature).encode("utf-8")).hexdigest()
        proposals.append(NoveltyProposal(
            proposal_id, signature, support_ids,
            tuple(sorted(case.observation_id for case in cases)),
            domains, context_values, evidence_refs,
        ))
    return tuple(sorted(
        proposals,
        key=lambda p: (-len(p.support_residual_ids), -len(p.domains), p.proposal_id),
    ))


def review_proposal(
    proposal: NoveltyProposal,
    *,
    decision: ProposalStatus,
    reviewer: str,
    note: str,
) -> NoveltyProposal:
    """Create a new immutable review version; never mutate the prior version."""
    if not isinstance(proposal, NoveltyProposal):
        raise ValueError("proposal must be a NoveltyProposal")
    if proposal.status != ProposalStatus.PROPOSED:
        raise ValueError("only a proposed version can receive an initial review")
    if decision not in (ProposalStatus.ACCEPTED, ProposalStatus.REJECTED):
        raise ValueError("review decision must be accepted or rejected")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("reviewer is required")
    if not isinstance(note, str) or not note.strip():
        raise ValueError("review note is required")
    return NoveltyProposal(
        proposal.proposal_id, proposal.signature, proposal.support_residual_ids,
        proposal.support_observation_ids, proposal.domains, proposal.context_values,
        proposal.evidence_refs, decision, proposal.version + 1,
        f"{proposal.proposal_id}:v{proposal.version}", f"{reviewer}: {note}",
    )


def rollback_proposal(proposal: NoveltyProposal, *, reason: str) -> NoveltyProposal:
    """Create a new proposed version pointing at the prior version."""
    if not isinstance(proposal, NoveltyProposal):
        raise ValueError("proposal must be a NoveltyProposal")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("rollback reason is required")
    return NoveltyProposal(
        proposal.proposal_id, proposal.signature, proposal.support_residual_ids,
        proposal.support_observation_ids, proposal.domains, proposal.context_values,
        proposal.evidence_refs, ProposalStatus.PROPOSED, proposal.version + 1,
        f"{proposal.proposal_id}:v{proposal.version}", f"rollback: {reason}",
    )
