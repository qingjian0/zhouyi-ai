"""E12-A13: conservative control-vs-target drift diagnostics."""
from __future__ import annotations
import hashlib, json, math
from dataclasses import dataclass
from enum import Enum
from typing import Mapping
from prototype.e12a7_orthogonal_lifecycle import EventKind, LifecycleEvent, OrthogonalLifecycleLedger, ScopeStatus
from prototype.e12a11_active_measurement_evidence import MeasurementReplayGuard, MeasurementStatus, SignedMeasurementReceipt, verify_receipt

def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()

def _sha(value):
    return hashlib.sha256(_canonical(value)).hexdigest()

def _distribution(source: Mapping[str, float]):
    if not source:
        raise ValueError("reference distribution must not be empty")
    items = []
    for key, value in source.items():
        if not isinstance(key, str) or not key or isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("invalid outcome or probability")
        value = float(value)
        if not math.isfinite(value) or value <= 0 or value > 1:
            raise ValueError("probabilities must be finite and in (0,1]")
        items.append((key, value))
    if not math.isclose(sum(v for _, v in items), 1.0, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("probabilities must sum to one")
    return tuple(sorted(items))

class DriftDiagnosis(str, Enum):
    INSUFFICIENT_DATA = "insufficient_data"
    STABLE = "stable"
    CONTROL_SHIFT = "control_shift"
    TARGET_MISMATCH = "target_mismatch"
    JOINT_SHIFT = "joint_shift"

@dataclass(frozen=True)
class DriftAssessment:
    assessment_id: str
    diagnosis: DriftDiagnosis
    control_count: int
    target_count: int
    control_total_variation: float | None
    target_total_variation: float | None
    scope_id: str
    scope_status: ScopeStatus
    explanation: str

class DriftMismatchMonitor:
    """TV is an effect-size threshold, not a calibrated p-value."""
    def __init__(self, *, candidate_ref, scope_id, scope_digest, protocol_id,
                 candidate_reference: Mapping[str, float],
                 control_references: Mapping[str, Mapping[str, float]],
                 public_key_bytes, executor_id, key_id, ledger: OrthogonalLifecycleLedger,
                 protocol_version="measurement-v1", min_samples=20, window_size=100, tv_threshold=0.25,
                 replay_guard: MeasurementReplayGuard | None = None):
        if "@" not in candidate_ref or not all(isinstance(x, str) and x.strip()
                for x in (scope_id, scope_digest, protocol_id, executor_id, key_id)):
            raise ValueError("immutable candidate and context identities are required")
        if isinstance(min_samples, bool) or not isinstance(min_samples, int) or min_samples < 2:
            raise ValueError("min_samples must be >= 2")
        if isinstance(window_size, bool) or not isinstance(window_size, int) or window_size < min_samples:
            raise ValueError("window_size must be >= min_samples")
        if isinstance(tv_threshold, bool) or not isinstance(tv_threshold, (int, float)) or not math.isfinite(tv_threshold) or not 0 < tv_threshold <= 1:
            raise ValueError("tv_threshold must be in (0,1]")
        self.candidate_ref, self.scope_id = candidate_ref, scope_id
        self.scope_digest, self.protocol_id = scope_digest, protocol_id
        self.candidate_reference = _distribution(candidate_reference)
        self.control_references = {k: _distribution(v) for k, v in control_references.items()}
        if not self.control_references or any(not isinstance(k, str) or not k for k in self.control_references):
            raise ValueError("non-empty known control target digests are required")
        control_models = set(self.control_references.values())
        if len(control_models) != 1:
            raise ValueError("aggregated controls must share an identical reference distribution")
        if not isinstance(protocol_version, str) or not protocol_version.strip():
            raise ValueError("protocol_version is required")
        self.protocol_version = protocol_version
        self.public_key_bytes, self.executor_id, self.key_id = public_key_bytes, executor_id, key_id
        self.ledger, self.min_samples, self.window_size = ledger, min_samples, window_size
        self.tv_threshold = float(tv_threshold)
        self.replay_guard = replay_guard or MeasurementReplayGuard()
        self._controls = {k: [] for k in self.control_references}
        self._targets, self._receipt_ids = [], set()
        self._assessment_count = 0

    @staticmethod
    def _tv(observations, reference):
        ref = dict(reference)
        keys, n = set(ref) | set(observations), len(observations)
        empirical = {key: observations.count(key) / n for key in keys}
        return 0.5 * sum(abs(empirical.get(key, 0.0) - ref.get(key, 0.0)) for key in keys)

    def ingest(self, receipt: SignedMeasurementReceipt):
        if receipt.status != MeasurementStatus.SELECT.value or not receipt.outcome:
            raise ValueError("only signed SELECT observations can be diagnosed")
        expected = {"executor_id": self.executor_id, "key_id": self.key_id,
            "protocol_version": self.protocol_version, "candidate_ref": self.candidate_ref, "scope_id": self.scope_id,
            "scope_digest": self.scope_digest, "protocol_id": self.protocol_id}
        verify_receipt(receipt, self.public_key_bytes, expected_context=expected)
        if receipt.receipt_id in self._receipt_ids:
            raise ValueError("receipt already ingested")
        is_control = receipt.target_digest in self.control_references
        reference = self.control_references[receipt.target_digest] if is_control else self.candidate_reference
        if receipt.outcome not in dict(reference):
            raise ValueError("outcome outside registered reference support")
        self.replay_guard.accept(receipt)
        self._receipt_ids.add(receipt.receipt_id)
        values = self._controls[receipt.target_digest] if is_control else self._targets
        values.append(receipt.outcome)
        del values[:-self.window_size]
        return "control" if is_control else "target"

    def assess(self):
        controls = [v for values in self._controls.values() for v in values]
        target_n, control_n = len(self._targets), len(controls)
        control_tv = self._tv(controls, next(iter(self.control_references.values()))) if control_n >= self.min_samples else None
        target_tv = self._tv(self._targets, self.candidate_reference) if target_n >= self.min_samples else None
        cr, tr = control_tv is not None, target_tv is not None
        if not cr and not tr:
            diagnosis, explanation = DriftDiagnosis.INSUFFICIENT_DATA, "insufficient control and target observations"
        elif cr and tr:
            cs, ts = control_tv > self.tv_threshold, target_tv > self.tv_threshold
            if cs and ts:
                diagnosis, explanation = DriftDiagnosis.JOINT_SHIFT, "control and target streams both deviate"
            elif cs:
                diagnosis, explanation = DriftDiagnosis.CONTROL_SHIFT, "known controls deviate; candidate attribution is unsafe"
            elif ts:
                diagnosis, explanation = DriftDiagnosis.TARGET_MISMATCH, "controls stable but targets deviate; candidate or scope mismatch remains unresolved"
            else:
                diagnosis, explanation = DriftDiagnosis.STABLE, "no deviation exceeds configured TV threshold"
        elif cr and control_tv > self.tv_threshold:
            diagnosis, explanation = DriftDiagnosis.CONTROL_SHIFT, "known controls deviate; candidate attribution is unsafe"
        elif tr and target_tv > self.tv_threshold:
            diagnosis, explanation = DriftDiagnosis.TARGET_MISMATCH, "target deviation detected without sufficient controls"
        else:
            diagnosis, explanation = DriftDiagnosis.INSUFFICIENT_DATA, "one stream is insufficient; stability is not established"
        shifted = diagnosis in (DriftDiagnosis.CONTROL_SHIFT, DriftDiagnosis.TARGET_MISMATCH, DriftDiagnosis.JOINT_SHIFT)
        scope_status = ScopeStatus.SHIFT_SUSPECTED if shifted else ScopeStatus.UNTESTED
        self._assessment_count += 1
        assessment_id = "e12a13:" + _sha({"candidate": self.candidate_ref, "scope": self.scope_id,
            "receipts": sorted(self._receipt_ids), "diagnosis": diagnosis.value,
            "control_tv": control_tv, "target_tv": target_tv, "count": self._assessment_count})
        if shifted:
            self.ledger.append(LifecycleEvent(sequence=len(self.ledger.events)+1,
                event_id="e12a13-event:"+assessment_id, candidate_ref=self.candidate_ref,
                kind=EventKind.SCOPE_ASSESSMENT, scope_id=self.scope_id,
                scope_status=ScopeStatus.SHIFT_SUSPECTED, evidence_ids=(assessment_id,),
                reason=explanation))
        return DriftAssessment(assessment_id, diagnosis, control_n, target_n,
            control_tv, target_tv, self.scope_id, scope_status, explanation)
