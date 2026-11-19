"""Candidate-bound, verifier-signed E09 observation receipts for M2/Yixiang.

The receipt authenticates provenance and an exact candidate snapshot. It does
not assert that the candidate is semantically true or advance E12-A6.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from prototype.e09_domain_registry import E09DomainRegistry
from prototype.shared_evidence_protocol import canonical_json


OBSERVATION_RECEIPT_SCHEMA = "e09_observation_receipt@1"
OBSERVATION_RECEIPT_AUDIENCE = "zhouyi-m2-yixiang-adapter"
OBSERVATION_RECEIPT_DOMAIN = "zhouyi:e09:m2-observation-receipt:v1"
OBSERVATION_RECEIPT_FIELDS = {
    "schema_version", "receipt_id", "nonce", "audience", "verifier_id",
    "episode_id", "scope", "learner_track", "candidate_record_id",
    "candidate_record_digest", "domain_id", "world_family",
    "domain_registry_id", "domain_registry_version", "observations",
    "issued_at", "expires_at", "signature_algorithm", "signature",
}
OBSERVATION_FIELDS = {
    "event_id", "event_digest", "observation_id", "episode_id",
}


class E09ObservationReceiptError(ValueError):
    """A candidate-bound E09 observation receipt is invalid or out of scope."""


@dataclass(frozen=True)
class VerifiedObservationReceipt:
    receipt_id: str
    nonce: str
    verifier_id: str
    episode_id: str
    scope: str
    learner_track: str
    candidate_record_id: str
    candidate_record_digest: str
    domain_id: str
    world_family: str
    domain_registry_id: str
    domain_registry_version: str
    event_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    event_digests: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime


def observation_receipt_signing_bytes(receipt: dict[str, Any]) -> bytes:
    if not isinstance(receipt, dict) or set(receipt) != OBSERVATION_RECEIPT_FIELDS:
        raise E09ObservationReceiptError("receipt must use the exact closed schema")
    unsigned = {key: value for key, value in receipt.items() if key != "signature"}
    return canonical_json({
        "domain": OBSERVATION_RECEIPT_DOMAIN,
        "receipt": unsigned,
    }).encode("utf-8")


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise E09ObservationReceiptError(f"{field} must be an ISO timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise E09ObservationReceiptError(f"{field} is invalid") from exc
    if result.tzinfo is None:
        raise E09ObservationReceiptError(f"{field} must include a timezone")
    return result.astimezone(timezone.utc)


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str) and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


class E09ObservationReceiptVerifier:
    """Trusted adapter-side verifier configured with pinned E09 verifier keys."""

    def __init__(
        self,
        *,
        signature_verifier: Callable[[str, str, bytes, str], bool],
        trusted_verifier_id: str,
        domain_registry: E09DomainRegistry,
        clock: Callable[[], datetime],
    ) -> None:
        if not callable(signature_verifier):
            raise TypeError("signature_verifier must be callable")
        if not isinstance(trusted_verifier_id, str) or not trusted_verifier_id.strip():
            raise ValueError("trusted_verifier_id must be non-empty")
        if not callable(getattr(domain_registry, "resolve", None)):
            raise TypeError("domain_registry must implement resolve")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self._signature_verifier = signature_verifier
        self.trusted_verifier_id = trusted_verifier_id
        self._domain_registry = domain_registry
        self._clock = clock

    def verify(
        self,
        receipt: dict[str, Any],
        *,
        candidate_record_id: str,
        candidate_record_digest: str,
        expected_scope: str,
    ) -> VerifiedObservationReceipt:
        if not isinstance(receipt, dict) or set(receipt) != OBSERVATION_RECEIPT_FIELDS:
            raise E09ObservationReceiptError("receipt has missing or unknown fields")
        if receipt["schema_version"] != OBSERVATION_RECEIPT_SCHEMA:
            raise E09ObservationReceiptError("unsupported observation receipt schema")
        if receipt["audience"] != OBSERVATION_RECEIPT_AUDIENCE:
            raise E09ObservationReceiptError("receipt audience mismatch")
        if receipt["verifier_id"] != self.trusted_verifier_id:
            raise E09ObservationReceiptError("receipt verifier is not trusted")
        if receipt["signature_algorithm"] != "Ed25519":
            raise E09ObservationReceiptError("receipt requires Ed25519")
        if receipt["scope"] != expected_scope:
            raise E09ObservationReceiptError("receipt scope mismatch")
        if receipt["candidate_record_id"] != candidate_record_id:
            raise E09ObservationReceiptError("receipt candidate record ID mismatch")
        if receipt["candidate_record_digest"] != candidate_record_digest:
            raise E09ObservationReceiptError("receipt candidate body digest mismatch")
        for field in (
            "receipt_id", "nonce", "episode_id", "scope", "learner_track",
            "candidate_record_id", "domain_id", "world_family",
            "domain_registry_id", "domain_registry_version", "signature",
        ):
            if not isinstance(receipt[field], str) or not receipt[field].strip():
                raise E09ObservationReceiptError(f"{field} must be non-empty")
        if not _is_sha256(receipt["candidate_record_digest"]):
            raise E09ObservationReceiptError("candidate_record_digest must be lowercase SHA-256")
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise E09ObservationReceiptError("verifier clock must return timezone-aware time")
        issued_at = _parse_timestamp(receipt["issued_at"], "issued_at")
        expires_at = _parse_timestamp(receipt["expires_at"], "expires_at")
        current = now.astimezone(timezone.utc)
        if current < issued_at or current >= expires_at or expires_at <= issued_at:
            raise E09ObservationReceiptError("observation receipt is expired or not yet valid")
        try:
            binding = self._domain_registry.resolve(expected_scope)
        except Exception as exc:
            raise E09ObservationReceiptError("trusted domain registration is missing or revoked") from exc
        expected_domain = {
            "domain_id": binding.domain_id,
            "world_family": binding.world_family,
            "domain_registry_id": binding.registry_id,
            "domain_registry_version": binding.registry_version,
        }
        if not binding.active or any(receipt[key] != value for key, value in expected_domain.items()):
            raise E09ObservationReceiptError("receipt domain binding is stale, revoked or mismatched")
        observations = receipt["observations"]
        if not isinstance(observations, list) or not observations:
            raise E09ObservationReceiptError("observations must be a non-empty list")
        event_ids: list[str] = []
        observation_ids: list[str] = []
        event_digests: list[str] = []
        for item in observations:
            if not isinstance(item, dict) or set(item) != OBSERVATION_FIELDS:
                raise E09ObservationReceiptError("observation binding has missing or unknown fields")
            if item["episode_id"] != receipt["episode_id"]:
                raise E09ObservationReceiptError("observation episode mismatch")
            for field in ("event_id", "observation_id"):
                if not isinstance(item[field], str) or not item[field].strip():
                    raise E09ObservationReceiptError(f"observation {field} must be non-empty")
            if not _is_sha256(item["event_digest"]):
                raise E09ObservationReceiptError("observation event digest must be lowercase SHA-256")
            event_ids.append(item["event_id"])
            observation_ids.append(item["observation_id"])
            event_digests.append(item["event_digest"])
        if len(set(event_ids)) != len(event_ids) or len(set(observation_ids)) != len(observation_ids):
            raise E09ObservationReceiptError("observation event and observation IDs must be unique")
        try:
            valid = self._signature_verifier(
                self.trusted_verifier_id, "Ed25519",
                observation_receipt_signing_bytes(receipt), receipt["signature"],
            )
        except Exception as exc:
            raise E09ObservationReceiptError("receipt signature verifier failed") from exc
        if valid is not True:
            raise E09ObservationReceiptError("receipt signature is invalid")
        return VerifiedObservationReceipt(
            receipt_id=receipt["receipt_id"], nonce=receipt["nonce"],
            verifier_id=self.trusted_verifier_id, episode_id=receipt["episode_id"],
            scope=receipt["scope"], learner_track=receipt["learner_track"],
            candidate_record_id=candidate_record_id,
            candidate_record_digest=candidate_record_digest,
            domain_id=receipt["domain_id"], world_family=receipt["world_family"],
            domain_registry_id=receipt["domain_registry_id"],
            domain_registry_version=receipt["domain_registry_version"],
            event_ids=tuple(event_ids), observation_ids=tuple(observation_ids),
            event_digests=tuple(event_digests), issued_at=issued_at,
            expires_at=expires_at,
        )


def build_observation_receipt(
    *,
    signer: Any,
    verifier_id: str,
    episode_id: str,
    scope: str,
    learner_track: str,
    candidate_record_id: str,
    candidate_record_digest: str,
    domain_id: str,
    world_family: str,
    domain_registry_id: str,
    domain_registry_version: str,
    observations: list[dict[str, str]],
    issued_at: datetime,
    expires_at: datetime,
) -> dict[str, Any]:
    """Build/sign a receipt; callers must supply evidence resolved by E09 authority."""
    if not callable(getattr(signer, "sign", None)):
        raise TypeError("signer must implement sign")
    receipt = {
        "schema_version": OBSERVATION_RECEIPT_SCHEMA,
        "receipt_id": __import__("secrets").token_hex(16),
        "nonce": __import__("secrets").token_urlsafe(32),
        "audience": OBSERVATION_RECEIPT_AUDIENCE,
        "verifier_id": verifier_id,
        "episode_id": episode_id,
        "scope": scope,
        "learner_track": learner_track,
        "candidate_record_id": candidate_record_id,
        "candidate_record_digest": candidate_record_digest,
        "domain_id": domain_id,
        "world_family": world_family,
        "domain_registry_id": domain_registry_id,
        "domain_registry_version": domain_registry_version,
        "observations": observations,
        "issued_at": issued_at.astimezone(timezone.utc).isoformat(),
        "expires_at": expires_at.astimezone(timezone.utc).isoformat(),
        "signature_algorithm": "Ed25519",
        "signature": "",
    }
    signature = signer.sign(verifier_id, observation_receipt_signing_bytes(receipt))
    if not isinstance(signature, str) or not signature.strip():
        raise E09ObservationReceiptError("receipt signer returned an invalid signature")
    receipt["signature"] = signature
    return receipt
