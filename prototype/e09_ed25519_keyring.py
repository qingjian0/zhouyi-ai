"""Pinned Ed25519 public-key verification for E09 authorization events.

Private keys never enter this module or the repository. Key rotation creates a
new keyring instance and verifier_id; revocation is explicit and fail-closed.
"""
from __future__ import annotations

import base64
import hashlib
from types import MappingProxyType
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from prototype.shared_evidence_protocol import canonical_json


class E09Ed25519IssuerKeyring:
    """Immutable issuer->public-key map implementing the E09 verifier callback."""

    def __init__(
        self,
        public_keys: Mapping[str, bytes],
        *,
        revoked_issuers: tuple[str, ...] = (),
    ) -> None:
        if not isinstance(public_keys, Mapping) or not public_keys:
            raise ValueError("public_keys must be a non-empty issuer mapping")
        normalized: dict[str, bytes] = {}
        for issuer_id, raw_key in public_keys.items():
            if not isinstance(issuer_id, str) or not issuer_id.strip():
                raise ValueError("issuer IDs must be non-empty strings")
            if not isinstance(raw_key, bytes) or len(raw_key) != 32:
                raise ValueError(f"issuer {issuer_id!r} must have a 32-byte Ed25519 public key")
            normalized[issuer_id] = bytes(raw_key)
        if len(set(revoked_issuers)) != len(revoked_issuers):
            raise ValueError("revoked_issuers must be unique")
        if any(not isinstance(item, str) or not item.strip() for item in revoked_issuers):
            raise ValueError("revoked issuer IDs must be non-empty strings")
        self._public_keys = MappingProxyType(normalized)
        self._revoked = frozenset(revoked_issuers)
        manifest = {
            "algorithm": "Ed25519",
            "issuers": {
                issuer: hashlib.sha256(key).hexdigest()
                for issuer, key in sorted(normalized.items())
            },
            "revoked_issuers": sorted(self._revoked),
        }
        self.verifier_id = "ed25519-keyring-v1:" + hashlib.sha256(
            canonical_json(manifest).encode("utf-8")
        ).hexdigest()

    def verify(self, issuer_id: str, algorithm: str, message: bytes, signature: str) -> bool:
        """Verify the callback contract used by resolve_branch_merge_authorization."""
        if algorithm != "Ed25519" or issuer_id in self._revoked:
            return False
        raw_key = self._public_keys.get(issuer_id)
        if raw_key is None or not isinstance(message, bytes) or not isinstance(signature, str):
            return False
        try:
            signature_bytes = base64.b64decode(signature, validate=True)
            Ed25519PublicKey.from_public_bytes(raw_key).verify(signature_bytes, message)
            return True
        except (ValueError, InvalidSignature):
            return False

    def __call__(self, issuer_id: str, algorithm: str, message: bytes, signature: str) -> bool:
        return self.verify(issuer_id, algorithm, message, signature)
