"""Signed, short-lived E09 verification receipts for cross-process E12-A6 handoff."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Any, Callable

from prototype.e12a6_lifecycle_contract import Evidence, SplitRole
from prototype.shared_evidence_protocol import canonical_json


RECEIPT_SCHEMA = "e09_verification_receipt@2"
RECEIPT_AUDIENCE = "e12a6-lifecycle-writer"
RECEIPT_DOMAIN = "zhouyi:e09:verification-receipt:v2"
RECEIPT_FIELDS = {
    "schema_version", "receipt_id", "nonce", "audience", "verifier_id",
    "episode_id", "authorization_ref", "scope", "parent_state_ref",
    "branch_ids", "authorization_evidence_refs", "evidence_refs", "issuer_id", "authorization_event_digest",
    "issued_at", "expires_at", "evidence", "signature_algorithm", "signature",
}
EVIDENCE_FIELDS = {
    "evidence_id", "episode_id", "world_family", "split_role", "observation_id",
    "outcome", "model_version", "measurement_cost", "prediction_commit_step",
    "label_visibility_step", "provenance", "domain_id",
    "domain_registry_id", "domain_registry_version",
}


class E09VerificationReceiptError(ValueError):
    """A signed E09 verification receipt is malformed, invalid or out of scope."""


@dataclass(frozen=True)
class VerifiedE09VerificationReceipt:
    """In-process result after a receipt signature and all bindings are checked."""

    receipt_id: str
    nonce: str
    episode_id: str
    authorization_ref: str
    scope: str
    parent_state_ref: str
    branch_ids: tuple[str, ...]
    authorization_evidence_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    issuer_id: str
    authorization_event_digest: str
    verifier_id: str
    issued_at: datetime
    expires_at: datetime
    evidence: tuple[Evidence, ...]


def verification_receipt_signing_bytes(receipt: dict[str, Any]) -> bytes:
    """Return canonical domain-separated bytes, excluding only signature bytes."""
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS:
        raise E09VerificationReceiptError("receipt must use the exact v1 closed schema")
    unsigned = {key: value for key, value in receipt.items() if key != "signature"}
    return canonical_json({"domain": RECEIPT_DOMAIN, "receipt": unsigned}).encode("utf-8")


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise E09VerificationReceiptError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise E09VerificationReceiptError(f"{field} is invalid") from exc
    if parsed.tzinfo is None:
        raise E09VerificationReceiptError(f"{field} must include a timezone")
    return parsed


def verify_e09_verification_receipt(
    receipt: dict[str, Any],
    *,
    signature_verifier: Callable[[str, str, bytes, str], bool],
    trusted_verifier_id: str,
    now: datetime,
    expected_scope: str,
    expected_parent_state_ref: str,
    expected_branch_ids: tuple[str, ...] | list[str],
    expected_evidence_refs: tuple[str, ...] | list[str],
    expected_authorization_evidence_refs: tuple[str, ...] | list[str],
) -> VerifiedE09VerificationReceipt:
    """Validate a verifier-signed receipt without access to the E09 database."""
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS:
        raise E09VerificationReceiptError("receipt has missing or unknown fields")
    if receipt.get("schema_version") != RECEIPT_SCHEMA:
        raise E09VerificationReceiptError("unsupported receipt schema")
    if receipt.get("audience") != RECEIPT_AUDIENCE:
        raise E09VerificationReceiptError("receipt audience is not E12-A6 lifecycle writer")
    if receipt.get("verifier_id") != trusted_verifier_id:
        raise E09VerificationReceiptError("receipt verifier identity is not trusted")
    if receipt.get("signature_algorithm") != "Ed25519":
        raise E09VerificationReceiptError("receipt requires Ed25519")
    if not callable(signature_verifier):
        raise TypeError("signature_verifier must be callable")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise E09VerificationReceiptError("writer time must be timezone-aware")

    for field in (
        "receipt_id", "nonce", "episode_id", "authorization_ref", "scope",
        "parent_state_ref", "issuer_id", "authorization_event_digest", "signature",
    ):
        value = receipt.get(field)
        if not isinstance(value, str) or not value.strip():
            raise E09VerificationReceiptError(f"{field} must be a non-empty string")
    digest = receipt["authorization_event_digest"]
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise E09VerificationReceiptError("authorization_event_digest must be lowercase SHA-256")

    issued_at = _timestamp(receipt.get("issued_at"), "issued_at")
    expires_at = _timestamp(receipt.get("expires_at"), "expires_at")
    current = now
    if current < issued_at or current >= expires_at or expires_at <= issued_at:
        raise E09VerificationReceiptError("receipt is not currently valid")

    branches = receipt.get("branch_ids")
    authorization_refs = receipt.get("authorization_evidence_refs")
    refs = receipt.get("evidence_refs")
    if (not isinstance(branches, list) or not branches
            or any(not isinstance(item, str) or not item.strip() for item in branches)
            or len(branches) != len(set(branches))):
        raise E09VerificationReceiptError("branch_ids must be a non-empty unique string list")
    for name, values in (("authorization_evidence_refs", authorization_refs), ("evidence_refs", refs)):
        if (not isinstance(values, list) or not values
                or any(not isinstance(item, str) or not item.strip() for item in values)
                or len(values) != len(set(values))):
            raise E09VerificationReceiptError(f"{name} must be a non-empty unique string list")
    if not set(authorization_refs).issubset(set(refs)):
        raise E09VerificationReceiptError("authorization evidence refs must be included in receipt evidence refs")
    if set(authorization_refs) != set(expected_authorization_evidence_refs):
        raise E09VerificationReceiptError("receipt authorization evidence set does not match grant")
    if receipt["scope"] != expected_scope:
        raise E09VerificationReceiptError("receipt scope does not match writer request")
    if receipt["parent_state_ref"] != expected_parent_state_ref:
        raise E09VerificationReceiptError("receipt parent state does not match writer request")
    if set(branches) != set(expected_branch_ids):
        raise E09VerificationReceiptError("receipt branch set does not match writer request")
    if set(refs) != set(expected_evidence_refs):
        raise E09VerificationReceiptError("receipt evidence set does not match writer request")

    signed_bytes = verification_receipt_signing_bytes(receipt)
    try:
        valid = signature_verifier(
            trusted_verifier_id, "Ed25519", signed_bytes, receipt["signature"]
        )
    except Exception as exc:
        raise E09VerificationReceiptError("receipt signature verifier failed") from exc
    if valid is not True:
        raise E09VerificationReceiptError("receipt signature is invalid")

    raw_evidence = receipt.get("evidence")
    if not isinstance(raw_evidence, list) or len(raw_evidence) != len(refs):
        raise E09VerificationReceiptError("receipt must contain one redacted evidence DTO per reference")
    evidence: list[Evidence] = []
    seen: set[str] = set()
    for item in raw_evidence:
        if not isinstance(item, dict) or set(item) != EVIDENCE_FIELDS:
            raise E09VerificationReceiptError("evidence DTO has missing or unknown fields")
        evidence_id = item.get("evidence_id")
        if (not isinstance(evidence_id, str) or evidence_id not in refs
                or evidence_id in seen or item.get("episode_id") != receipt["episode_id"]):
            raise E09VerificationReceiptError("evidence DTO identity does not match receipt references")
        seen.add(evidence_id)
        if item.get("outcome") != f"opaque-e09-evidence-ref:{evidence_id}":
            raise E09VerificationReceiptError("receipt evidence outcome is not redacted")
        provenance = item.get("provenance")
        if not isinstance(provenance, str) or not provenance.startswith("opaque-e09-event-digest:"):
            raise E09VerificationReceiptError("receipt evidence provenance is not redacted")
        try:
            dto = dict(item)
            dto["split_role"] = SplitRole(dto["split_role"])
            parsed = Evidence(**dto)
        except (KeyError, TypeError, ValueError) as exc:
            raise E09VerificationReceiptError("receipt evidence DTO violates E12-A6 contract") from exc
        if (isinstance(parsed.measurement_cost, bool)
                or not math.isfinite(float(parsed.measurement_cost))
                or parsed.measurement_cost < 0):
            raise E09VerificationReceiptError("receipt evidence measurement cost is invalid")
        if any(not getattr(parsed, field) for field in (
            "domain_id", "domain_registry_id", "domain_registry_version",
        )):
            raise E09VerificationReceiptError("receipt evidence lacks trusted domain registry provenance")
        evidence.append(parsed)
    if seen != set(refs):
        raise E09VerificationReceiptError("receipt evidence DTO set is incomplete")

    return VerifiedE09VerificationReceipt(
        receipt_id=receipt["receipt_id"],
        nonce=receipt["nonce"],
        episode_id=receipt["episode_id"],
        authorization_ref=receipt["authorization_ref"],
        scope=receipt["scope"],
        parent_state_ref=receipt["parent_state_ref"],
        branch_ids=tuple(sorted(branches)),
        authorization_evidence_refs=tuple(authorization_refs),
        evidence_refs=tuple(refs),
        issuer_id=receipt["issuer_id"],
        authorization_event_digest=digest,
        verifier_id=trusted_verifier_id,
        issued_at=issued_at,
        expires_at=expires_at,
        evidence=tuple(evidence),
    )
