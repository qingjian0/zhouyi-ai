"""Authenticated sole-writer facade for receipt-authorized E12-A6 CSG-GCR merges."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Protocol

from prototype.csg_branch_delta import BranchSnapshot, _issue_verified_branch_merge_authorization
from prototype.csg_gcr_e12a6_adapter import CSGGCRLifecycleProjection, adapt_typed_candidate
from prototype.csg_gcr_coordinator import GlobalConstraints
from prototype.e09_authority_services import E09Clock, SystemUTCClock
from prototype.e09_verification_receipt import (
    VerifiedE09VerificationReceipt,
    verify_e09_verification_receipt,
)
from prototype.e12a6_zpcm_persistence import LifecycleBundleReceipt, PersistentLifecycleLedger
from prototype.typed_csg_gcr import TypedCandidateCoordinator, TypedCandidateProposal


class E12A6WriterError(PermissionError):
    """An E12-A6 writer request is unauthenticated or violates the write policy."""


class E12A6AuthenticationError(E12A6WriterError):
    """The configured E12-A6 workload authenticator rejected the caller."""


class E12A6AuthorizationError(E12A6WriterError):
    """The authenticated workload lacks the required E12-A6 permission."""


@dataclass(frozen=True)
class E12A6AuthenticatedWorkload:
    workload_id: str
    roles: frozenset[str]
    scopes: frozenset[str]
    identity_provider: str
    authentication_method: str
    credential_fingerprint: str

    def __post_init__(self) -> None:
        for field in (
            "workload_id", "identity_provider", "authentication_method",
            "credential_fingerprint",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")
        fingerprint = self.credential_fingerprint
        if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
            raise ValueError("credential_fingerprint must be lowercase SHA-256")
        for field in ("roles", "scopes"):
            values = getattr(self, field)
            if not isinstance(values, (set, frozenset, tuple, list)):
                raise TypeError(f"{field} must be a collection of strings")
            if not values or any(not isinstance(item, str) or not item.strip() for item in values):
                raise ValueError(f"{field} must contain non-empty strings")
            if len(values) != len(set(values)):
                raise ValueError(f"{field} must not contain duplicates")
            object.__setattr__(self, field, frozenset(values))


class E12A6WorkloadAuthenticator(Protocol):
    """Authenticate an IPC credential and return server-derived workload claims."""

    def authenticate(self, credential: object) -> E12A6AuthenticatedWorkload:
        ...


@dataclass(frozen=True)
class E12A6WriterResult:
    projection: CSGGCRLifecycleProjection
    lifecycle_receipt: LifecycleBundleReceipt
    authorization_receipt_id: str
    submitter_workload_id: str
    proposal_ids: tuple[str, ...]


class E12A6WriterService:
    """Narrow writer API; it never opens E09 and never accepts a verified object from callers.

    The service verifies the signed JSON receipt, derives the internal E09 merge
    capability, runs typed CSG-GCR coordination itself, and atomically commits
    candidate/evidence/receipt consumption through PersistentLifecycleLedger.
    """

    def __init__(
        self,
        ledger: PersistentLifecycleLedger,
        *,
        authenticator: E12A6WorkloadAuthenticator,
        receipt_signature_verifier: Callable[[str, str, bytes, str], bool],
        trusted_verifier_id: str,
        clock: E09Clock | None = None,
        coordinator: TypedCandidateCoordinator | None = None,
    ) -> None:
        if not isinstance(ledger, PersistentLifecycleLedger):
            raise TypeError("ledger must be PersistentLifecycleLedger")
        if not callable(getattr(authenticator, "authenticate", None)):
            raise TypeError("authenticator must implement authenticate")
        if not callable(receipt_signature_verifier):
            raise TypeError("receipt_signature_verifier must be callable")
        if not isinstance(trusted_verifier_id, str) or not trusted_verifier_id.strip():
            raise ValueError("trusted_verifier_id must be a non-empty string")
        self._ledger = ledger
        self._authenticator = authenticator
        self._receipt_signature_verifier = receipt_signature_verifier
        self._trusted_verifier_id = trusted_verifier_id
        self._clock = clock or SystemUTCClock()
        self._coordinator = coordinator or TypedCandidateCoordinator()

    def _principal(self, credential: object, scope: str) -> E12A6AuthenticatedWorkload:
        try:
            principal = self._authenticator.authenticate(credential)
        except Exception as exc:
            raise E12A6AuthenticationError("E12-A6 workload authentication failed") from exc
        if not isinstance(principal, E12A6AuthenticatedWorkload):
            raise E12A6AuthenticationError("authenticator returned an invalid workload identity")
        if "candidate_submitter" not in principal.roles:
            raise E12A6AuthorizationError("workload lacks candidate_submitter role")
        if scope not in principal.scopes:
            raise E12A6AuthorizationError("workload is not authorized for the requested scope")
        return principal

    def submit_authorized_merge_candidate(
        self,
        credential: object,
        *,
        proposals: Iterable[TypedCandidateProposal],
        base_state: Mapping[str, object],
        branch_snapshots: Iterable[BranchSnapshot],
        receipt: dict[str, Any],
        scope: str,
        grammar_version: str,
        selected_proposal_ids: tuple[str, ...] | list[str] | None = None,
        constraints: GlobalConstraints = GlobalConstraints(),
    ) -> E12A6WriterResult:
        """Verify receipt, recompute the merge and atomically persist one selected candidate."""
        if not isinstance(scope, str) or not scope.strip():
            raise E12A6AuthorizationError("scope must be a non-empty string")
        principal = self._principal(credential, scope)
        if self._ledger.scope != scope:
            raise E12A6AuthorizationError("writer ledger scope does not match request scope")
        rows = tuple(proposals)
        snapshots = tuple(branch_snapshots)
        if not rows or any(not isinstance(row, TypedCandidateProposal) for row in rows):
            raise E12A6AuthorizationError("proposals must contain TypedCandidateProposal values")
        parent_refs = {row.proposal.parent_state_ref for row in rows}
        branch_ids = tuple(sorted({row.proposal.branch_id for row in rows}))
        if len(parent_refs) != 1 or len(branch_ids) < 2:
            raise E12A6AuthorizationError("authorized writer endpoint requires one parent and at least two branches")
        parent_state_ref = next(iter(parent_refs))
        if not isinstance(receipt, dict):
            raise E12A6AuthorizationError("signed verifier receipt must be an object")
        raw_evidence_refs = receipt.get("evidence_refs")
        raw_authorization_refs = receipt.get("authorization_evidence_refs")
        if not isinstance(raw_evidence_refs, list) or not isinstance(raw_authorization_refs, list):
            raise E12A6AuthorizationError("receipt evidence bindings are missing")

        current = self._clock.now()
        if not isinstance(current, datetime) or current.tzinfo is None:
            raise E12A6AuthenticationError("writer clock must return a timezone-aware datetime")
        current = current.astimezone(timezone.utc)
        verified: VerifiedE09VerificationReceipt = verify_e09_verification_receipt(
            receipt,
            signature_verifier=self._receipt_signature_verifier,
            trusted_verifier_id=self._trusted_verifier_id,
            now=current,
            expected_scope=scope,
            expected_parent_state_ref=parent_state_ref,
            expected_branch_ids=branch_ids,
            expected_evidence_refs=tuple(raw_evidence_refs),
            expected_authorization_evidence_refs=tuple(raw_authorization_refs),
        )
        capability = _issue_verified_branch_merge_authorization(
            verified.authorization_ref,
            verified.parent_state_ref,
            verified.branch_ids,
            verified.authorization_evidence_refs,
            verified.issuer_id,
            verified.authorization_event_digest,
            verified.verifier_id,
            domain_provenance_verified=True,
        )
        report = self._coordinator.coordinate(
            rows,
            constraints,
            base_state=base_state,
            branch_snapshots=snapshots,
            branch_merge_authorization=capability,
        )
        if selected_proposal_ids is None:
            if len(report.candidates) != 1:
                raise E12A6AuthorizationError(
                    "candidate selection is ambiguous; provide selected_proposal_ids"
                )
            coordinated = report.candidates[0]
        else:
            if (not isinstance(selected_proposal_ids, (tuple, list)) or not selected_proposal_ids
                    or any(not isinstance(item, str) or not item.strip() for item in selected_proposal_ids)
                    or len(selected_proposal_ids) != len(set(selected_proposal_ids))):
                raise E12A6AuthorizationError("selected_proposal_ids must be a non-empty unique sequence")
            wanted = set(selected_proposal_ids)
            matches = [
                item for item in report.candidates
                if set(item.coordinated.proposal_ids) == wanted
            ]
            if len(matches) != 1:
                available = [tuple(sorted(item.coordinated.proposal_ids)) for item in report.candidates]
                raise E12A6AuthorizationError(
                    f"selected proposal set is not one unique feasible coordinator result; "
                    f"status={report.status}; available={available}"
                )
            coordinated = matches[0]

        if coordinated.branch_merge is None:
            raise E12A6AuthorizationError("selected candidate has no validated branch merge")
        if (coordinated.branch_merge_authorization_ref != verified.authorization_ref
                or set(coordinated.branch_merge_authorization_evidence_refs)
                != set(verified.authorization_evidence_refs)
                or set(coordinated.coordinated.branch_ids) != set(verified.branch_ids)
                or coordinated.coordinated.parent_state_ref != verified.parent_state_ref):
            raise E12A6AuthorizationError("signed receipt does not bind the recomputed branch merge")
        projection = adapt_typed_candidate(
            coordinated, scope=scope, grammar_version=grammar_version,
        )
        if set(projection.native_candidate.evidence_ids) != set(verified.evidence_refs):
            raise E12A6AuthorizationError("signed receipt evidence set does not cover the projected candidate")

        lifecycle_receipt = self._ledger.register_candidate_bundle(
            projection.native_candidate,
            verified.evidence,
            authorization_receipt=verified,
            consumed_at=current,
            writer_identity={
                "workload_id": principal.workload_id,
                "identity_provider": principal.identity_provider,
                "authentication_method": principal.authentication_method,
                "credential_fingerprint": principal.credential_fingerprint,
            },
        )
        return E12A6WriterResult(
            projection=projection,
            lifecycle_receipt=lifecycle_receipt,
            authorization_receipt_id=verified.receipt_id,
            submitter_workload_id=principal.workload_id,
            proposal_ids=tuple(sorted(coordinated.coordinated.proposal_ids)),
        )
