"""Atomic CSG-GCR → E09 evidence → E12-A6/ZPCM ingestion path."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from prototype.csg_gcr_e12a6_adapter import CSGGCRLifecycleProjection, adapt_typed_candidate
from prototype.e09_e12a6_evidence_bridge import resolve_e09_reveal
from prototype.e12a6_lifecycle_contract import Evidence
from prototype.e12a6_zpcm_persistence import LifecycleBundleReceipt, PersistentLifecycleLedger
from prototype.shared_evidence_protocol import SQLiteEvidenceStore
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
    world_family_by_evidence: Mapping[str, str],
    measurement_cost_by_evidence: Mapping[str, float] | None = None,
) -> PersistentCSGGCRIngestion:
    """Verify evidence refs, project one candidate, and atomically persist bundle.

    Cross-branch candidates are rejected until BranchMergeAuthorization has an
    authenticated E09 issuer-verification contract. Branch-delta and
    authorization provenance remains preserved in the projected candidate,
    but this adapter will not treat those refs as verified E09 reveal events.
    """
    if not isinstance(ledger, PersistentLifecycleLedger):
        raise TypeError("ledger must be PersistentLifecycleLedger")
    if not isinstance(e09_store, SQLiteEvidenceStore):
        raise TypeError("e09_store must be SQLiteEvidenceStore")
    if not isinstance(coordinated, TypedCoordinatedCandidate):
        raise TypeError("coordinated must be TypedCoordinatedCandidate")
    if not isinstance(world_family_by_evidence, Mapping):
        raise TypeError("world_family_by_evidence must be a mapping")
    costs = measurement_cost_by_evidence or {}
    if not isinstance(costs, Mapping):
        raise TypeError("measurement_cost_by_evidence must be a mapping")

    branch_ids = tuple(coordinated.coordinated.branch_ids)
    if len(set(branch_ids)) > 1:
        raise CSGGCRIngestionError(
            "cross-branch candidate ingestion is blocked until E09 authorization issuer verification exists"
        )

    refs = tuple(coordinated.coordinated.evidence_refs)
    if len(refs) != len(set(refs)):
        raise CSGGCRIngestionError("candidate evidence references must be unique")
    if set(world_family_by_evidence) != set(refs):
        raise CSGGCRIngestionError(
            "world_family_by_evidence must provide exactly one explicit world family per E09 evidence ref"
        )
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
            world_family=world_family_by_evidence[ref],
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
