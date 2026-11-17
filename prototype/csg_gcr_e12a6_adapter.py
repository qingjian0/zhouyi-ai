"""Project typed CSG-GCR candidates into the authoritative E12-A6 lifecycle.

The adapter is read-only: it creates an OBSERVED Candidate and CPG-EI
interchange DTOs. E12-A6 LifecycleLedger alone owns state transitions.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from prototype.cpg_interop import canonical_json, digest_json
from prototype.csg_branch_delta import MergeResult, MergeStatus, canonical_hash
from prototype.e12a6_interop_adapter import E12A6AdapterResult, adapt_candidate
from prototype.e12a6_lifecycle_contract import Candidate, CandidateState
from prototype.typed_csg_gcr import TypedCoordinatedCandidate


@dataclass(frozen=True)
class CSGGCRLifecycleProjection:
    native_candidate: Candidate
    interchange: E12A6AdapterResult
    raw_score: float
    score_semantics: str = "uncalibrated_ranking_score"


def _merge_definition(
    result: MergeResult,
    authorization_ref: str | None,
    authorization_evidence_refs: tuple[str, ...],
    event_evidence_refs: tuple[str, ...],
) -> dict:
    if not isinstance(result, MergeResult):
        raise TypeError("branch_merge must be MergeResult")
    if result.status not in (MergeStatus.MERGED, MergeStatus.NO_OP):
        raise ValueError("only successful structural branch merges can enter E12-A6")
    state_hash = canonical_hash(dict(result.state))
    return {
        "status": result.status.value,
        "state_digest": state_hash,
        "applied_event_ids": list(result.applied_event_ids),
        "authorization_ref": authorization_ref,
        "authorization_evidence_refs": list(authorization_evidence_refs),
        "event_evidence_refs": list(event_evidence_refs),
    }


def adapt_typed_candidate(
    coordinated: TypedCoordinatedCandidate,
    *,
    scope: str,
    grammar_version: str,
    version: int = 1,
) -> CSGGCRLifecycleProjection:
    """Create an E12-A6 OBSERVED candidate from one typed CSG-GCR result.

    The raw CSG-GCR score remains ranking metadata. It is never translated
    into E12-A6 uncertainty/confidence. Evidence references are preserved but
    are not authenticated or inserted into the lifecycle ledger here.
    """
    if not isinstance(coordinated, TypedCoordinatedCandidate):
        raise TypeError("coordinated must be TypedCoordinatedCandidate")
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("scope must be a non-empty string")
    if not isinstance(grammar_version, str) or not grammar_version.strip():
        raise ValueError("grammar_version must be a non-empty string")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("version must be a positive integer")

    candidate = coordinated.coordinated
    if coordinated.semantic_status == "HYPOTHESIS_ONLY" or any(
        "HYPOTHESIS_ONLY" in kind.upper() for kind in candidate.candidate_kinds
    ):
        raise ValueError("hypothesis-only candidates cannot be projected as OBSERVED")
    unified = coordinated.unification
    if candidate.parent_state_ref != unified.parent_state_ref:
        raise ValueError("coordinator and unifier parent state references differ")
    if tuple(candidate.proposal_ids) != tuple(unified.edge_ids):
        raise ValueError("coordinator proposal IDs and unifier edge IDs differ")
    if tuple(candidate.branch_ids) != tuple(unified.branch_ids):
        raise ValueError("coordinator and unifier branch IDs differ")
    if tuple(candidate.evidence_refs) != tuple(unified.evidence_refs):
        raise ValueError("coordinator and unifier evidence provenance differs")
    if not candidate.proposal_ids or not candidate.candidate_kinds:
        raise ValueError("typed candidate requires proposal IDs and candidate kinds")
    if not isinstance(candidate.score, (int, float)) or isinstance(candidate.score, bool) or not math.isfinite(candidate.score):
        raise ValueError("candidate score must be finite")
    if isinstance(candidate.cost, bool) or not isinstance(candidate.cost, int) or candidate.cost < 0:
        raise ValueError("candidate cost must be a non-negative integer")
    if not unified.variables:
        raise ValueError("typed candidate requires at least one unified variable")

    authorization_ref = coordinated.branch_merge_authorization_ref
    authorization_evidence = tuple(coordinated.branch_merge_authorization_evidence_refs)
    branch_evidence = tuple(coordinated.branch_merge_evidence_refs)
    if authorization_ref is not None and (
            not isinstance(authorization_ref, str) or not authorization_ref.strip()):
        raise ValueError("branch merge authorization reference must be non-empty")
    if authorization_evidence and authorization_ref is None:
        raise ValueError("authorization evidence requires an authorization reference")
    if any(not isinstance(ref, str) or not ref.strip()
           for ref in authorization_evidence + branch_evidence):
        raise ValueError("branch merge provenance references must be non-empty strings")
    if len(set(authorization_evidence)) != len(authorization_evidence):
        raise ValueError("authorization evidence references must be unique")
    if len(set(branch_evidence)) != len(branch_evidence):
        raise ValueError("branch merge evidence references must be unique")

    branch_merge_definition = None
    if coordinated.branch_merge is not None:
        if len(candidate.branch_ids) > 1 and (
            not isinstance(authorization_ref, str) or not authorization_ref.strip()
            or not authorization_evidence
        ):
            raise ValueError("cross-branch lifecycle candidate requires an authorization reference and evidence")
        branch_merge_definition = _merge_definition(
            coordinated.branch_merge, authorization_ref,
            authorization_evidence, branch_evidence,
        )
    elif authorization_ref is not None or authorization_evidence or branch_evidence:
        raise ValueError("branch merge provenance cannot exist without a branch merge result")

    evidence_refs = tuple(sorted(set(
        tuple(candidate.evidence_refs) + branch_evidence + authorization_evidence
    )))
    variables = [
        {
            "refs": [
                {"namespace": ref.namespace, "name": ref.name}
                for ref in item.refs
            ],
            "value_type": item.value_type,
            "member_id": item.member_id,
            "member_type": item.member_type,
        }
        for item in unified.variables
    ]
    identity_definition = {
        "parent_state_ref": candidate.parent_state_ref,
        "candidate_kinds": list(candidate.candidate_kinds),
        "bindings": [{"key": key, "value": value} for key, value in candidate.bindings],
        "unified_variables": variables,
        "active_from": unified.active_from,
        "active_until": unified.active_until,
        "branch_state_digest": (
            branch_merge_definition["state_digest"] if branch_merge_definition else None
        ),
    }
    candidate_id = "csg-gcr:" + digest_json(identity_definition)
    full_definition = {
        "schema": "csg-gcr-typed-candidate-v1",
        **identity_definition,
        "proposal_ids": list(candidate.proposal_ids),
        "branch_ids": list(candidate.branch_ids),
        "evidence_refs": list(evidence_refs),
        "branch_merge": branch_merge_definition,
    }
    canonical_expression = canonical_json(full_definition)
    operator = (
        candidate.candidate_kinds[0]
        if len(candidate.candidate_kinds) == 1
        else "typed-composition"
    )
    input_types = tuple(item.value_type for item in unified.variables)
    native = Candidate(
        candidate_id=candidate_id,
        version=version,
        canonical_expression=canonical_expression,
        proposer_family="csg-gcr",
        supporting_families=("csg-gcr",),
        input_types=input_types,
        operator=operator,
        conditions=(),
        uncertainty=1.0,
        complexity=max(1, len(candidate.proposal_ids) + len(unified.variables)),
        proposal_cost=float(candidate.cost),
        parent_refs=(candidate.parent_state_ref,),
        evidence_ids=evidence_refs,
        state=CandidateState.OBSERVED,
    )
    interchange = adapt_candidate(
        native, scope=scope, grammar_version=grammar_version,
    )
    return CSGGCRLifecycleProjection(
        native_candidate=native,
        interchange=interchange,
        raw_score=float(candidate.score),
    )
