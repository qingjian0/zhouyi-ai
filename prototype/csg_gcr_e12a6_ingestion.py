"""Atomic CSG-GCR → E09 evidence → E12-A6/ZPCM ingestion path."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from prototype.csg_gcr_e12a6_adapter import CSGGCRLifecycleProjection, adapt_typed_candidate
from prototype.csg_branch_delta import VerifiedBranchMergeAuthorization
from prototype.e09_e12a6_evidence_bridge import resolve_e09_reveal
from prototype.e12a6_lifecycle_contract import Evidence
from prototype.e12a6_zpcm_persistence import LifecycleBundleReceipt, PersistentLifecycleLedger
from prototype.shared_evidence_protocol import SQLiteEvidenceStore
from prototype.e09_domain_registry import E09DomainRegistry
from prototype.typed_csg_gcr import TypedCoordinatedCandidate


class CSGGCRIngestionError(ValueError):
    """A typed candidate cannot safely enter the persistent lifecycle."""


@dataclass(frozen=True)
class PersistentCSGGCRIngestion:
    projection: CSGGCRLifecycleProjection
    receipt: LifecycleBundleReceipt
    verified_evidence_refs: tuple[str, ...]


def ingest_typed_candidate(
    coordinated: TypedCoordinatedCandidate,
    *,
    ledger: PersistentLifecycleLedger,
    e09_store: SQLiteEvidenceStore,
    episode_id: str,
    scope: str,
    learner_track: str,
    grammar_version: str,
    domain_registry: E09DomainRegistry | None = None,
    world_family_by_evidence: Mapping[str, str] | None = None,
    measurement_cost_by_evidence: Mapping[str, float] | None = None,
    branch_merge_authorization: VerifiedBranchMergeAuthorization | None = None,
) -> PersistentCSGGCRIngestion:
    """Verify evidence refs, project one candidate, and atomically persist bundle.

    Cross-branch candidates require a VerifiedBranchMergeAuthorization returned
    by the E09 signed-grant resolver. Its issuer signature, parent, exact branch
    set, expiry and evidence reveal references must already have been verified.
    """
    if not isinstance(ledger, PersistentLifecycleLedger):
        raise TypeError("ledger must be PersistentLifecycleLedger")
    if not isinstance(e09_store, SQLiteEvidenceStore):
        raise TypeError("e09_store must be SQLiteEvidenceStore")
    if not isinstance(coordinated, TypedCoordinatedCandidate):
        raise TypeError("coordinated must be TypedCoordinatedCandidate")
    if domain_registry is None or not callable(getattr(domain_registry, "resolve", None)):
        raise CSGGCRIngestionError(
            "trusted domain registry is required; legacy v0.3 evidence is quarantined from lifecycle ingestion"
        )
    if world_family_by_evidence is not None:
        raise CSGGCRIngestionError("caller-supplied world-family overrides are forbidden")
    costs = {} if measurement_cost_by_evidence is None else measurement_cost_by_evidence
    if not isinstance(costs, Mapping):
        raise TypeError("measurement_cost_by_evidence must be a mapping")

    for name, value in (("episode_id", episode_id), ("scope", scope), ("learner_track", learner_track)):
        if not isinstance(value, str) or not value.strip():
            raise CSGGCRIngestionError(f"{name} must be a non-empty string")
    branch_ids = tuple(coordinated.coordinated.branch_ids)
    if len(set(branch_ids)) > 1:
        if not isinstance(branch_merge_authorization, VerifiedBranchMergeAuthorization):
            raise CSGGCRIngestionError(
                "cross-branch candidate ingestion requires a signature-verified E09 authorization"
            )
        if branch_merge_authorization.domain_provenance_verified is not True:
            raise CSGGCRIngestionError("cross-branch authorization lacks trusted domain provenance")
        if (
            branch_merge_authorization.authorization_ref != coordinated.branch_merge_authorization_ref
            or branch_merge_authorization.evidence_refs != coordinated.branch_merge_authorization_evidence_refs
            or branch_merge_authorization.parent_state_ref != coordinated.coordinated.parent_state_ref
            or set(branch_merge_authorization.branch_ids) != set(branch_ids)
        ):
            raise CSGGCRIngestionError(
                "verified E09 authorization does not match candidate parent, branches, or provenance"
            )
    elif branch_merge_authorization is not None:
        raise CSGGCRIngestionError("branch merge authorization supplied for a single-branch candidate")

    refs = tuple(coordinated.coordinated.evidence_refs)
    if len(refs) != len(set(refs)):
        raise CSGGCRIngestionError("candidate evidence references must be unique")
    if set(costs) - set(refs):
        raise CSGGCRIngestionError("measurement costs may only be supplied for candidate evidence refs")

    projection = adapt_typed_candidate(
        coordinated, scope=scope, grammar_version=grammar_version,
    )
    verified: list[Evidence] = []
    for ref in refs:
        verified.append(resolve_e09_reveal(
            e09_store,
            episode_id=episode_id,
            evidence_ref=ref,
            scope=scope,
            learner_track=learner_track,
            domain_registry=domain_registry,
            measurement_cost=costs.get(ref, 0.0),
        ))

    receipt = ledger.register_candidate_bundle(
        projection.native_candidate, tuple(verified),
    )
    return PersistentCSGGCRIngestion(
        projection=projection,
        receipt=receipt,
        verified_evidence_refs=refs,
    )
