"""E12-A10: Ed25519-signed evaluator receipts with replay protection."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

@dataclass(frozen=True)
class SignedEvaluatorReceipt:
    evaluator_id: str
    key_id: str
    evaluator_version: str
    dataset_version: str
    split_id: str
    candidate_ref: str
    scope_digest: str
    episode_id: str
    commit_digest: str
    sequence: int
    gold_label: int
    scored: bool
    correct: bool | None
    receipt_id: str
    signature_hex: str

    def payload(self) -> dict:
        return {
            "evaluator_id": self.evaluator_id, "key_id": self.key_id,
            "evaluator_version": self.evaluator_version,
            "dataset_version": self.dataset_version, "split_id": self.split_id,
            "candidate_ref": self.candidate_ref, "scope_digest": self.scope_digest,
            "episode_id": self.episode_id, "commit_digest": self.commit_digest,
            "sequence": self.sequence, "gold_label": self.gold_label,
            "scored": self.scored, "correct": self.correct,
        }

class EvaluatorSigner:
    """Private signing key must live only in the evaluator service."""
    def __init__(self, evaluator_id: str, key_id: str, private_key: Ed25519PrivateKey,
                 evaluator_version: str):
        for name, value in (("evaluator_id", evaluator_id), ("key_id", key_id),
                            ("evaluator_version", evaluator_version)):
            if not value or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        self.evaluator_id, self.key_id = evaluator_id, key_id
        self.evaluator_version = evaluator_version
        self.__private_key = private_key

    @classmethod
    def generate(cls, evaluator_id: str, key_id: str,
                 evaluator_version: str = "evaluator-v1") -> "EvaluatorSigner":
        return cls(evaluator_id, key_id, Ed25519PrivateKey.generate(), evaluator_version)

    def public_key_bytes(self) -> bytes:
        return self.__private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)

    def sign_verdict(self, commit, verdict, *, candidate_ref: str,
                     scope_digest: str, dataset_version: str, split_id: str,
                     sequence: int) -> SignedEvaluatorReceipt:
        if verdict.episode_id != commit.episode_id or verdict.commit_digest != commit.commit_digest:
            raise ValueError("verdict does not match prediction commit")
        if not candidate_ref or "@" not in candidate_ref:
            raise ValueError("candidate_ref must identify a version")
        if not all((scope_digest, dataset_version, split_id)):
            raise ValueError("scope_digest, dataset_version and split_id are required")
        if isinstance(sequence, bool) or sequence < 1:
            raise ValueError("sequence must be a positive integer")
        if verdict.scored:
            if commit.prediction is None or not commit.identifiable:
                raise ValueError("unidentifiable commit cannot be scored")
            if verdict.correct is not (commit.prediction == verdict.gold_label):
                raise ValueError("verdict correctness is inconsistent")
        elif verdict.correct is not None:
            raise ValueError("unscored verdict must not contain correctness")
        payload = {
            "evaluator_id": self.evaluator_id, "key_id": self.key_id,
            "evaluator_version": self.evaluator_version,
            "dataset_version": dataset_version, "split_id": split_id,
            "candidate_ref": candidate_ref, "scope_digest": scope_digest,
            "episode_id": commit.episode_id, "commit_digest": commit.commit_digest,
            "sequence": sequence, "gold_label": verdict.gold_label,
            "scored": verdict.scored, "correct": verdict.correct,
        }
        signature = self.__private_key.sign(_canonical(payload))
        receipt_id = _sha(_canonical(payload) + signature)
        return SignedEvaluatorReceipt(**payload, receipt_id=receipt_id,
                                       signature_hex=signature.hex())

class ReceiptReplayGuard:
    """Verifier-side state; persist this state in production."""
    def __init__(self):
        self._last_sequence: dict[tuple[str, str], int] = {}
        self._seen_commits: set[tuple[str, str, str]] = set()
        self._seen_receipts: set[str] = set()

    def accept(self, receipt: SignedEvaluatorReceipt) -> None:
        signer = (receipt.evaluator_id, receipt.key_id)
        expected = self._last_sequence.get(signer, 0) + 1
        if receipt.sequence != expected:
            raise ValueError(f"non-monotonic or missing evaluator sequence: expected {expected}")
        commit_key = (receipt.evaluator_id, receipt.key_id, receipt.commit_digest)
        if commit_key in self._seen_commits or receipt.receipt_id in self._seen_receipts:
            raise ValueError("replayed evaluator receipt or commit")
        self._last_sequence[signer] = receipt.sequence
        self._seen_commits.add(commit_key)
        self._seen_receipts.add(receipt.receipt_id)

def verify_receipt(receipt: SignedEvaluatorReceipt, public_key_bytes: bytes, *,
                   expected_context: Mapping[str, str] | None = None,
                   replay_guard: ReceiptReplayGuard | None = None) -> bool:
    payload = receipt.payload()
    signature = bytes.fromhex(receipt.signature_hex)
    if receipt.receipt_id != _sha(_canonical(payload) + signature):
        raise ValueError("receipt id does not match payload/signature")
    try:
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(signature, _canonical(payload))
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("invalid evaluator receipt signature") from exc
    if expected_context:
        for field, expected in expected_context.items():
            if payload.get(field) != expected:
                raise ValueError(f"evaluator receipt context mismatch: {field}")
    if replay_guard is not None:
        replay_guard.accept(receipt)
    return True
