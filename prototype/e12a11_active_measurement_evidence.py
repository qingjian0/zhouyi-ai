"""E12-A11: authorized, budgeted and signed active-measurement evidence."""
from __future__ import annotations
import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


class MeasurementStatus(str, Enum):
    SELECT = "SELECT"
    NO_DISCRIMINATING_MEASUREMENT = "NO_DISCRIMINATING_MEASUREMENT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    INVALID_INPUT = "INVALID_INPUT"
    EXECUTION_FAILED = "EXECUTION_FAILED"


@dataclass(frozen=True)
class MeasurementRequest:
    request_id: str
    candidate_ref: str
    scope_id: str
    scope_digest: str
    protocol_id: str
    target_digest: str
    params_digest: str
    estimated_cost: float
    max_cost: float

    def payload(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

    @property
    def request_digest(self) -> str:
        return _sha(self.payload())


@dataclass(frozen=True)
class SignedMeasurementReceipt:
    executor_id: str
    key_id: str
    protocol_version: str
    request_digest: str
    request_id: str
    candidate_ref: str
    scope_id: str
    scope_digest: str
    protocol_id: str
    target_digest: str
    params_digest: str
    status: str
    outcome: str | None
    actual_cost: float
    sequence: int
    receipt_id: str
    signature_hex: str

    def payload(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__
                if k not in ("receipt_id", "signature_hex")}


@dataclass(frozen=True)
class MeasurementEvidence:
    evidence_id: str
    candidate_ref: str
    scope_id: str
    scope_digest: str
    request_digest: str
    receipt_id: str
    protocol_id: str
    outcome: str
    actual_cost: float


class MeasurementSigner:
    def __init__(self, executor_id: str, key_id: str, private_key: Ed25519PrivateKey,
                 protocol_version: str = "measurement-v1"):
        if not all(isinstance(x, str) and x.strip() for x in
                   (executor_id, key_id, protocol_version)):
            raise ValueError("executor identity and protocol version are required")
        self.executor_id, self.key_id = executor_id, key_id
        self.protocol_version, self.__private_key = protocol_version, private_key

    @classmethod
    def generate(cls, executor_id: str, key_id: str):
        return cls(executor_id, key_id, Ed25519PrivateKey.generate())

    def public_key_bytes(self) -> bytes:
        return self.__private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)

    def sign(self, request: MeasurementRequest, status: MeasurementStatus,
             outcome: str | None, actual_cost: float, sequence: int) -> SignedMeasurementReceipt:
        payload = dict(executor_id=self.executor_id, key_id=self.key_id,
            protocol_version=self.protocol_version, request_digest=request.request_digest,
            request_id=request.request_id, candidate_ref=request.candidate_ref,
            scope_id=request.scope_id, scope_digest=request.scope_digest,
            protocol_id=request.protocol_id, target_digest=request.target_digest,
            params_digest=request.params_digest, status=status.value, outcome=outcome,
            actual_cost=actual_cost, sequence=sequence)
        signature = self.__private_key.sign(_canonical(payload))
        return SignedMeasurementReceipt(**payload,
            receipt_id=hashlib.sha256(_canonical(payload) + signature).hexdigest(),
            signature_hex=signature.hex())


class MeasurementReplayGuard:
    """In-memory prototype. Production requires durable, transactional storage."""
    def __init__(self):
        self._last: dict[tuple[str, str], int] = {}
        self._requests: set[tuple[str, str, str]] = set()
        self._receipts: set[str] = set()

    def accept(self, receipt: SignedMeasurementReceipt):
        signer = (receipt.executor_id, receipt.key_id)
        if receipt.sequence != self._last.get(signer, 0) + 1:
            raise ValueError("measurement sequence gap or replay")
        request_key = (receipt.executor_id, receipt.key_id, receipt.request_digest)
        if request_key in self._requests or receipt.receipt_id in self._receipts:
            raise ValueError("measurement request or receipt replay")
        self._last[signer] = receipt.sequence
        self._requests.add(request_key)
        self._receipts.add(receipt.receipt_id)


def verify_receipt(receipt: SignedMeasurementReceipt, public_key_bytes: bytes, *,
                   expected_context: Mapping[str, str] | None = None,
                   replay_guard: MeasurementReplayGuard | None = None) -> bool:
    payload = receipt.payload()
    signature = bytes.fromhex(receipt.signature_hex)
    if receipt.receipt_id != hashlib.sha256(_canonical(payload) + signature).hexdigest():
        raise ValueError("measurement receipt digest mismatch")
    try:
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(signature, _canonical(payload))
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("invalid measurement executor signature") from exc
    if not math.isfinite(receipt.actual_cost) or receipt.actual_cost < 0:
        raise ValueError("invalid actual measurement cost")
    if expected_context:
        for key, expected in expected_context.items():
            if payload.get(key) != expected:
                raise ValueError(f"measurement context mismatch: {key}")
    if replay_guard:
        replay_guard.accept(receipt)
    return True


class BudgetedMeasurementExecutor:
    """Trusted executor: learner supplies a request, never the observed outcome.

    Registered protocol callbacks run inside the executor boundary and return
    (outcome, actual_cost). A callback is trusted code, not an OS sandbox.
    """
    def __init__(self, signer: MeasurementSigner, protocols: Mapping[str, Callable],
                 *, allowed_candidate_scopes: set[tuple[str, str]], budget: float):
        if not math.isfinite(budget) or budget < 0:
            raise ValueError("budget must be finite and non-negative")
        self.signer, self.protocols = signer, dict(protocols)
        self.allowed = set(allowed_candidate_scopes)
        self.remaining_budget = float(budget)
        self._sequence = 0
        self._used_requests: set[str] = set()

    def execute(self, request: MeasurementRequest) -> SignedMeasurementReceipt:
        fields = (request.request_id, request.candidate_ref, request.scope_id,
                  request.scope_digest, request.protocol_id, request.target_digest,
                  request.params_digest)
        valid = all(isinstance(x, str) and x.strip() for x in fields)
        valid = valid and "@" in request.candidate_ref
        valid = valid and math.isfinite(request.estimated_cost) and request.estimated_cost >= 0
        valid = valid and math.isfinite(request.max_cost) and request.max_cost >= 0
        if (not valid or request.protocol_id not in self.protocols or
                (request.candidate_ref, request.scope_id) not in self.allowed):
            return self._receipt(request, MeasurementStatus.INVALID_INPUT, None, 0.0)
        if request.request_digest in self._used_requests:
            raise ValueError("measurement request already executed")
        if request.estimated_cost > request.max_cost or request.estimated_cost > self.remaining_budget:
            self._used_requests.add(request.request_digest)
            return self._receipt(request, MeasurementStatus.BUDGET_EXHAUSTED, None, 0.0)
        self._used_requests.add(request.request_digest)
        try:
            outcome, actual_cost = self.protocols[request.protocol_id](
                request.target_digest, request.params_digest)
            if not isinstance(outcome, str) or not outcome.strip():
                raise ValueError("protocol returned no observable outcome")
            if isinstance(actual_cost, bool) or not isinstance(actual_cost, (int, float)):
                raise ValueError("protocol returned invalid cost")
            actual_cost = float(actual_cost)
            if not math.isfinite(actual_cost) or actual_cost < 0 or actual_cost > request.max_cost:
                raise ValueError("actual cost violates request ceiling")
            if actual_cost > self.remaining_budget:
                return self._receipt(request, MeasurementStatus.BUDGET_EXHAUSTED, None, 0.0)
            self.remaining_budget -= actual_cost
            status = MeasurementStatus.NO_DISCRIMINATING_MEASUREMENT if outcome == "NO_DISCRIMINATION" else MeasurementStatus.SELECT
            return self._receipt(request, status, None if status != MeasurementStatus.SELECT else outcome, actual_cost)
        except Exception:
            return self._receipt(request, MeasurementStatus.EXECUTION_FAILED, None, 0.0)

    def _receipt(self, request, status, outcome, cost):
        self._sequence += 1
        return self.signer.sign(request, status, outcome, cost, self._sequence)


def receipt_to_evidence(receipt: SignedMeasurementReceipt, public_key_bytes: bytes, *,
                        expected_scope_digest: str,
                        replay_guard: MeasurementReplayGuard) -> MeasurementEvidence:
    verify_receipt(receipt, public_key_bytes, expected_context={
        "scope_digest": expected_scope_digest}, replay_guard=replay_guard)
    if receipt.status != MeasurementStatus.SELECT.value or not receipt.outcome:
        raise ValueError("only successful discriminating observations become evidence")
    identity = {"receipt_id": receipt.receipt_id, "request_digest": receipt.request_digest,
                "candidate_ref": receipt.candidate_ref, "scope_id": receipt.scope_id,
                "scope_digest": receipt.scope_digest, "outcome": receipt.outcome}
    return MeasurementEvidence("e12a11:" + _sha(identity), receipt.candidate_ref,
        receipt.scope_id, receipt.scope_digest, receipt.request_digest, receipt.receipt_id,
        receipt.protocol_id, receipt.outcome, receipt.actual_cost)
