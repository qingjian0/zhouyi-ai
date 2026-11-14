"""M28 evidence independence, source identity, and derivation audit.

This module audits declared provenance. It does not authenticate witnesses,
infer undocumented transmission, or decide whether evidence entails a claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class DerivationKind(str, Enum):
    TRANSCRIPTION = "transcription"
    QUOTATION = "quotation"
    PARAPHRASE = "paraphrase"
    COMMENTARY = "commentary"
    COLLATION = "collation"
    OCR = "ocr"
    TRANSLATION = "translation"
    COPY = "copy"
    REVISION = "revision"
    UNKNOWN = "unknown"


class EvidenceStance(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"


class ReviewState(str, Enum):
    UNREVIEWED = "unreviewed"
    REVIEWED = "reviewed"
    DISPUTED = "disputed"


@dataclass(frozen=True)
class SourceIdentity:
    source_id: str
    work_id: str
    source_type: str
    independence_group: str
    description: str


@dataclass(frozen=True)
class Witness:
    witness_id: str
    source_id: str
    edition_id: str
    witness_type: str
    locator: str
    text_layer: str
    verification_state: str
    lineage_complete: bool
    root_origin_id: str = ""


@dataclass(frozen=True)
class Derivation:
    derivation_id: str
    parent_witness_id: str
    child_witness_id: str
    kind: DerivationKind
    certainty: str
    note: str


@dataclass(frozen=True)
class EvidenceAssertion:
    evidence_id: str
    witness_id: str
    claim_id: str
    stance: EvidenceStance
    review_state: ReviewState
    reviewer_ids: Tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class EvidenceIndependence:
    claim_id: str
    reviewed_support_records: int
    distinct_witnesses: int
    distinct_source_identities: int
    declared_independence_groups: Tuple[str, ...]
    independent_support_pairs: Tuple[Tuple[str, str], ...]
    unresolved_lineage_witnesses: Tuple[str, ...]
    contradiction_evidence_ids: Tuple[str, ...]
    qualification_evidence_ids: Tuple[str, ...]
    unreviewed_evidence_ids: Tuple[str, ...]
    semantic_entailment_established: bool = False


@dataclass(frozen=True)
class ProvenanceAudit:
    witness_ids: Tuple[str, ...]
    root_witness_ids: Tuple[str, ...]
    derived_witness_ids: Tuple[str, ...]
    source_identity_ids: Tuple[str, ...]
    derivation_edges: int
    incomplete_lineage_witness_ids: Tuple[str, ...]
    cycle_free: bool = True
    authenticity_established: bool = False


def _nonempty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty")


def _unique_strings(values: Tuple[str, ...], field: str, allow_empty: bool = True) -> None:
    if not isinstance(values, tuple) or (not allow_empty and not values):
        raise ValueError(f"{field} must be a tuple")
    for value in values:
        _nonempty(value, field)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must be unique")


def audit_evidence_provenance(
    sources: Tuple[SourceIdentity, ...],
    witnesses: Tuple[Witness, ...],
    derivations: Tuple[Derivation, ...],
) -> ProvenanceAudit:
    if not isinstance(sources, tuple) or not sources:
        raise ValueError("sources must be a non-empty tuple")
    if not isinstance(witnesses, tuple) or not witnesses:
        raise ValueError("witnesses must be a non-empty tuple")
    if not isinstance(derivations, tuple):
        raise ValueError("derivations must be a tuple")

    source_map = {}
    for source in sources:
        if not isinstance(source, SourceIdentity):
            raise ValueError("source entries must be SourceIdentity")
        for field in ("source_id", "work_id", "source_type", "independence_group", "description"):
            _nonempty(getattr(source, field), field)
        if source.source_id in source_map:
            raise ValueError("duplicate source_id")
        source_map[source.source_id] = source

    witness_map = {}
    for witness in witnesses:
        if not isinstance(witness, Witness):
            raise ValueError("witness entries must be Witness")
        for field in ("witness_id", "source_id", "edition_id", "witness_type", "locator",
                      "text_layer", "verification_state"):
            _nonempty(getattr(witness, field), field)
        if not isinstance(witness.lineage_complete, bool):
            raise ValueError("lineage_complete must be bool")
        if witness.source_id not in source_map:
            raise ValueError(f"unknown source identity: {witness.source_id}")
        if witness.witness_id in witness_map:
            raise ValueError("duplicate witness_id")
        witness_map[witness.witness_id] = witness

    edge_map = {}
    parents = {wid: [] for wid in witness_map}
    children = {wid: [] for wid in witness_map}
    for edge in derivations:
        if not isinstance(edge, Derivation):
            raise ValueError("derivation entries must be Derivation")
        for field in ("derivation_id", "parent_witness_id", "child_witness_id", "certainty", "note"):
            _nonempty(getattr(edge, field), field)
        if not isinstance(edge.kind, DerivationKind):
            raise ValueError("invalid derivation kind")
        if edge.derivation_id in edge_map:
            raise ValueError("duplicate derivation_id")
        if edge.parent_witness_id not in witness_map or edge.child_witness_id not in witness_map:
            raise ValueError("unknown derivation endpoint")
        if edge.parent_witness_id == edge.child_witness_id:
            raise ValueError("self derivation")
        edge_map[edge.derivation_id] = edge
        parents[edge.child_witness_id].append(edge.parent_witness_id)
        children[edge.parent_witness_id].append(edge.child_witness_id)

    visiting, visited = set(), set()
    def visit(wid):
        if wid in visiting:
            raise ValueError("provenance graph contains a cycle")
        if wid in visited:
            return
        visiting.add(wid)
        for child in children[wid]:
            visit(child)
        visiting.remove(wid)
        visited.add(wid)
    for wid in witness_map:
        visit(wid)

    # A witness with an incoming derivation is derived. An unlinked witness is
    # only a declared root, not proof of historically independent origin.
    derived = tuple(sorted(wid for wid in witness_map if parents[wid]))
    roots = tuple(sorted(set(witness_map) - set(derived)))
    return ProvenanceAudit(
        tuple(sorted(witness_map)), roots, derived, tuple(sorted(source_map)),
        len(edge_map),
        tuple(sorted(wid for wid, w in witness_map.items() if not w.lineage_complete)),
    )


def assess_evidence_independence(
    claim_id: str,
    sources: Tuple[SourceIdentity, ...],
    witnesses: Tuple[Witness, ...],
    derivations: Tuple[Derivation, ...],
    evidence: Tuple[EvidenceAssertion, ...],
) -> EvidenceIndependence:
    _nonempty(claim_id, "claim_id")
    audit_evidence_provenance(sources, witnesses, derivations)
    source_map = {s.source_id: s for s in sources}
    witness_map = {w.witness_id: w for w in witnesses}
    parents = {wid: set() for wid in witness_map}
    for edge in derivations:
        parents[edge.child_witness_id].add(edge.parent_witness_id)

    ancestors_cache = {}
    def ancestors(wid):
        if wid not in ancestors_cache:
            result = set()
            for parent in parents[wid]:
                result.add(parent)
                result.update(ancestors(parent))
            ancestors_cache[wid] = result
        return ancestors_cache[wid]

    relevant = []
    seen = set()
    for item in evidence:
        if not isinstance(item, EvidenceAssertion):
            raise ValueError("evidence entries must be EvidenceAssertion")
        for field in ("evidence_id", "witness_id", "claim_id", "rationale"):
            _nonempty(getattr(item, field), field)
        _unique_strings(item.reviewer_ids, "reviewer_ids")
        if item.evidence_id in seen:
            raise ValueError("duplicate evidence_id")
        seen.add(item.evidence_id)
        if item.witness_id not in witness_map:
            raise ValueError("evidence references unknown witness")
        if not isinstance(item.stance, EvidenceStance) or not isinstance(item.review_state, ReviewState):
            raise ValueError("invalid evidence stance or review state")
        if item.review_state == ReviewState.REVIEWED:
            if not item.reviewer_ids or len(item.rationale.strip()) < 12:
                raise ValueError("reviewed evidence requires reviewers and substantive rationale")
        elif item.reviewer_ids:
            raise ValueError("unreviewed/disputed evidence cannot claim completed reviewers")
        if item.claim_id == claim_id:
            relevant.append(item)

    reviewed_support = [e for e in relevant
                        if e.review_state == ReviewState.REVIEWED and e.stance == EvidenceStance.SUPPORTS]
    pairs = []
    for i, left in enumerate(reviewed_support):
        for right in reviewed_support[i + 1:]:
            lw, rw = witness_map[left.witness_id], witness_map[right.witness_id]
            # Unknown lineage blocks positive independence claims.
            if not (lw.lineage_complete and rw.lineage_complete):
                continue
            # Ancestor/descendant or shared ancestor means derivational dependence.
            if left.witness_id in ancestors(right.witness_id) or right.witness_id in ancestors(left.witness_id):
                continue
            if ancestors(left.witness_id) & ancestors(right.witness_id):
                continue
            ls, rs = source_map[lw.source_id], source_map[rw.source_id]
            # Multiple mirrors/editions from one declared source family are not
            # independent support, even if their digital records are separate.
            if ls.source_id == rs.source_id or ls.independence_group == rs.independence_group:
                continue
            pairs.append(tuple(sorted((left.witness_id, right.witness_id))))

    unresolved = tuple(sorted({e.witness_id for e in relevant
                               if not witness_map[e.witness_id].lineage_complete}))
    return EvidenceIndependence(
        claim_id=claim_id,
        reviewed_support_records=len(reviewed_support),
        distinct_witnesses=len({e.witness_id for e in reviewed_support}),
        distinct_source_identities=len({witness_map[e.witness_id].source_id for e in reviewed_support}),
        declared_independence_groups=tuple(sorted({source_map[witness_map[e.witness_id].source_id].independence_group
                                                   for e in reviewed_support})),
        independent_support_pairs=tuple(sorted(set(pairs))),
        unresolved_lineage_witnesses=unresolved,
        contradiction_evidence_ids=tuple(sorted(e.evidence_id for e in relevant
            if e.review_state == ReviewState.REVIEWED and e.stance == EvidenceStance.CONTRADICTS)),
        qualification_evidence_ids=tuple(sorted(e.evidence_id for e in relevant
            if e.review_state == ReviewState.REVIEWED and e.stance == EvidenceStance.QUALIFIES)),
        unreviewed_evidence_ids=tuple(sorted(e.evidence_id for e in relevant
            if e.review_state != ReviewState.REVIEWED)),
    )
