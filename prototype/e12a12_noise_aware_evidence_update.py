"""E12-A12: noise-aware, pre-registered likelihood evidence updates."""
from __future__ import annotations
import hashlib, json, math
from dataclasses import dataclass
from typing import Mapping
from prototype.e12a7_orthogonal_lifecycle import EpistemicStatus, EventKind, LifecycleEvent, OrthogonalLifecycleLedger
from prototype.e12a11_active_measurement_evidence import MeasurementReplayGuard, MeasurementStatus, SignedMeasurementReceipt, verify_receipt

def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()

@dataclass(frozen=True)
class LikelihoodModel:
    model_id: str
    model_version: str
    candidate_ref: str
    scope_id: str
    scope_digest: str
    protocol_id: str
    candidate_probabilities: tuple[tuple[str, float], ...]
    alternative_probabilities: tuple[tuple[str, float], ...]
    alpha: float = 0.05
    beta: float = 0.05

    def __post_init__(self):
        required = (self.model_id, self.model_version, self.candidate_ref,
                    self.scope_id, self.scope_digest, self.protocol_id)
        if not all(isinstance(x, str) and x.strip() for x in required):
            raise ValueError("model identity and binding fields are required")
        if "@" not in self.candidate_ref:
            raise ValueError("candidate_ref must identify an immutable version")
        if not (0 < self.alpha < 1 and 0 < self.beta < 1 and self.alpha + self.beta < 1):
            raise ValueError("alpha and beta must be in (0,1) and sum to less than 1")
        for distribution in (self.candidate_probabilities, self.alternative_probabilities):
            if not distribution or tuple(sorted(distribution)) != distribution:
                raise ValueError("likelihood distributions must be non-empty and canonically sorted")
            if len({name for name, _ in distribution}) != len(distribution):
                raise ValueError("likelihood outcome labels must be unique")
            if any(not isinstance(name, str) or not name or isinstance(p, bool)
                   or not isinstance(p, (int, float)) or not math.isfinite(p) or p <= 0 or p > 1
                   for name, p in distribution):
                raise ValueError("likelihood probabilities must be finite and in (0,1]")
            if not math.isclose(sum(p for _, p in distribution), 1.0,
                                rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError("likelihood probabilities must sum to one")
        if tuple(name for name, _ in self.candidate_probabilities) != tuple(
                name for name, _ in self.alternative_probabilities):
            raise ValueError("hypotheses must define the same outcome space")

    @classmethod
    def create(cls, *, model_id: str, model_version: str, candidate_ref: str,
               scope_id: str, scope_digest: str, protocol_id: str,
               candidate_probabilities: Mapping[str, float],
               alternative_probabilities: Mapping[str, float],
               alpha: float = 0.05, beta: float = 0.05):
        if not all(isinstance(x, str) and x.strip() for x in
                   (model_id, model_version, candidate_ref, scope_id, scope_digest, protocol_id)):
            raise ValueError("model identity and binding fields are required")
        if "@" not in candidate_ref:
            raise ValueError("candidate_ref must identify an immutable version")
        if not (0 < alpha < 1 and 0 < beta < 1 and alpha + beta < 1):
            raise ValueError("alpha and beta must be in (0,1) and sum to less than 1")
        if not candidate_probabilities or set(candidate_probabilities) != set(alternative_probabilities):
            raise ValueError("both hypotheses must define the same non-empty outcome space")
        def normalize(source):
            items = []
            for outcome, probability in source.items():
                if not isinstance(outcome, str) or not outcome:
                    raise ValueError("outcome labels must be non-empty strings")
                if isinstance(probability, bool) or not isinstance(probability, (int, float)):
                    raise ValueError("probabilities must be numeric")
                p = float(probability)
                if not math.isfinite(p) or p <= 0 or p > 1:
                    raise ValueError("probabilities must be finite and in (0,1]")
                items.append((outcome, p))
            if not math.isclose(sum(p for _, p in items), 1.0, rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError("outcome probabilities must sum to one")
            return tuple(sorted(items))
        return cls(model_id, model_version, candidate_ref, scope_id, scope_digest,
                   protocol_id, normalize(candidate_probabilities),
                   normalize(alternative_probabilities), float(alpha), float(beta))

    @property
    def model_digest(self):
        return _sha({"model_id": self.model_id, "model_version": self.model_version,
            "candidate_ref": self.candidate_ref, "scope_id": self.scope_id,
            "scope_digest": self.scope_digest, "protocol_id": self.protocol_id,
            "candidate_probabilities": self.candidate_probabilities,
            "alternative_probabilities": self.alternative_probabilities,
            "alpha": self.alpha, "beta": self.beta})

    @property
    def upper_threshold(self):
        return math.log((1.0 - self.beta) / self.alpha)

    @property
    def lower_threshold(self):
        return math.log(self.beta / (1.0 - self.alpha))

@dataclass(frozen=True)
class EvidenceUpdate:
    evidence_id: str
    model_digest: str
    candidate_ref: str
    scope_id: str
    receipt_id: str
    observation: str
    log_likelihood_ratio: float
    cumulative_log_likelihood_ratio: float
    observation_count: int
    epistemic_status: EpistemicStatus
    lifecycle_event_id: str

class SequentialEvidenceUpdater:
    """Consumes verified receipts; appends scope-local A7 epistemic events."""
    def __init__(self, model: LikelihoodModel, public_key_bytes: bytes, *,
                 executor_id: str, key_id: str, ledger: OrthogonalLifecycleLedger,
                 replay_guard: MeasurementReplayGuard | None = None):
        if not executor_id or not key_id:
            raise ValueError("trusted executor and key identity are required")
        self.model, self.public_key_bytes = model, public_key_bytes
        self.executor_id, self.key_id, self.ledger = executor_id, key_id, ledger
        self.replay_guard = replay_guard or MeasurementReplayGuard()
        self._llr, self._count, self._receipt_ids = 0.0, 0, []
        self._decision: EpistemicStatus | None = None

    @property
    def cumulative_log_likelihood_ratio(self):
        return self._llr

    @property
    def observation_count(self):
        return self._count

    def update(self, receipt: SignedMeasurementReceipt) -> EvidenceUpdate:
        if self._decision is not None:
            raise ValueError("sequential test has crossed a stopping boundary")
        if receipt.status != MeasurementStatus.SELECT.value or not receipt.outcome:
            raise ValueError("only SELECT observations can update likelihood evidence")
        expected = {"executor_id": self.executor_id, "key_id": self.key_id,
            "candidate_ref": self.model.candidate_ref, "scope_id": self.model.scope_id,
            "scope_digest": self.model.scope_digest, "protocol_id": self.model.protocol_id}
        verify_receipt(receipt, self.public_key_bytes, expected_context=expected)
        candidate_probs = dict(self.model.candidate_probabilities)
        alternative_probs = dict(self.model.alternative_probabilities)
        if receipt.outcome not in candidate_probs:
            raise ValueError("observation is outside the pre-registered outcome space")
        self.replay_guard.accept(receipt)
        increment = math.log(candidate_probs[receipt.outcome] / alternative_probs[receipt.outcome])
        next_llr = self._llr + increment
        if next_llr >= self.model.upper_threshold:
            status = EpistemicStatus.SUPPORTED
        elif next_llr <= self.model.lower_threshold:
            status = EpistemicStatus.REFUTED_IN_SCOPE
        else:
            status = EpistemicStatus.UNDERDETERMINED
        next_receipts = self._receipt_ids + [receipt.receipt_id]
        evidence_id = "e12a12:" + _sha({"model_digest": self.model.model_digest,
            "candidate_ref": self.model.candidate_ref, "scope_id": self.model.scope_id,
            "receipt_ids": next_receipts, "cumulative_llr": format(next_llr, ".17g"),
            "status": status.value})
        event_id = "e12a12-event:" + receipt.receipt_id
        event = LifecycleEvent(sequence=len(self.ledger.events) + 1, event_id=event_id,
            candidate_ref=self.model.candidate_ref, kind=EventKind.EPISTEMIC_ASSESSMENT,
            scope_id=self.model.scope_id, epistemic_status=status,
            evidence_ids=(evidence_id,),
            reason=(f"E12-A12 model={self.model.model_id}@{self.model.model_version}; "
                    f"n={self._count + 1}; increment={increment:.9g}; "
                    f"cumulative_llr={next_llr:.9g}; status={status.value}"))
        self.ledger.append(event)
        self._llr, self._count = next_llr, self._count + 1
        self._receipt_ids.append(receipt.receipt_id)
        if status in (EpistemicStatus.SUPPORTED, EpistemicStatus.REFUTED_IN_SCOPE):
            self._decision = status
        return EvidenceUpdate(evidence_id, self.model.model_digest, self.model.candidate_ref,
            self.model.scope_id, receipt.receipt_id, receipt.outcome, increment, self._llr,
            self._count, status, event_id)
