"""E12-A15: scoped competing explanations and cost-aware active discrimination.

Posterior values are relative to a frozen, registered hypothesis set. They are
not calibrated truth probabilities and do not directly promote epistemic status.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from prototype.e12a11_active_measurement_evidence import (
    MeasurementReplayGuard, MeasurementRequest, MeasurementStatus,
    SignedMeasurementReceipt, verify_receipt,
)
from prototype.e12a7_orthogonal_lifecycle import CandidateVersion


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _entropy(probabilities: list[float]) -> float:
    return -sum(p * math.log(p, 2) for p in probabilities if p > 0)


class ExplanationKind(str, Enum):
    ENVIRONMENT_SHIFT = "environment_shift"
    SCOPE_TOO_BROAD = "scope_too_broad"
    COMPOSITION_ERROR = "composition_error"
    MEASUREMENT_NOISE = "measurement_noise"
    MODEL_SET_INCOMPLETE = "model_set_incomplete"
    OTHER = "other"


class SelectionStatus(str, Enum):
    SELECT = "SELECT"
    NO_DISCRIMINATING_MEASUREMENT = "NO_DISCRIMINATING_MEASUREMENT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


@dataclass(frozen=True)
class CompetingHypothesis:
    hypothesis_id: str
    kind: ExplanationKind
    candidate_ref: str
    prior: float
    # Canonically sorted: (measurement_id, ((outcome, probability), ...))
    predictions: tuple[tuple[str, tuple[tuple[str, float], ...]], ...]
    description: str = ""

    def __post_init__(self):
        if not self.hypothesis_id or not self.hypothesis_id.strip():
            raise ValueError("hypothesis_id is required")
        if "@" not in self.candidate_ref:
            raise ValueError("candidate_ref must identify an immutable version")
        if isinstance(self.prior, bool) or not math.isfinite(self.prior) or self.prior <= 0:
            raise ValueError("prior must be finite and positive")
        if not isinstance(self.kind, ExplanationKind):
            raise TypeError("kind must be an ExplanationKind")
        if not self.predictions or tuple(sorted(self.predictions)) != self.predictions:
            raise ValueError("predictions must be non-empty and canonically sorted")
        if len({key for key, _ in self.predictions}) != len(self.predictions):
            raise ValueError("duplicate measurement prediction")
        for measurement_id, distribution in self.predictions:
            if not measurement_id or not distribution or tuple(sorted(distribution)) != distribution:
                raise ValueError("each measurement needs a sorted outcome distribution")
            if len({name for name, _ in distribution}) != len(distribution):
                raise ValueError("duplicate outcome")
            if any(not isinstance(name, str) or not name or isinstance(p, bool)
                   or not isinstance(p, (int, float)) or not math.isfinite(p) or p <= 0 or p > 1
                   for name, p in distribution):
                raise ValueError("likelihoods must be finite and in (0,1]")
            if not math.isclose(sum(p for _, p in distribution), 1.0,
                                rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError("likelihoods must sum to one")

    def distribution(self, measurement_id: str) -> dict[str, float]:
        for key, values in self.predictions:
            if key == measurement_id:
                return dict(values)
        raise KeyError(measurement_id)


@dataclass(frozen=True)
class MeasurementPlan:
    measurement_id: str
    protocol_id: str
    target_digest: str
    params_digest: str
    estimated_cost: float
    max_cost: float

    def __post_init__(self):
        if not all(isinstance(x, str) and x.strip() for x in
                   (self.measurement_id, self.protocol_id, self.target_digest, self.params_digest)):
            raise ValueError("measurement plan identity fields are required")
        if any(isinstance(x, bool) or not isinstance(x, (int, float))
               or not math.isfinite(x) or x < 0
               for x in (self.estimated_cost, self.max_cost)):
            raise ValueError("measurement costs must be finite and non-negative")
        if self.estimated_cost > self.max_cost:
            raise ValueError("estimated cost cannot exceed max_cost")


@dataclass(frozen=True)
class MeasurementDecision:
    status: SelectionStatus
    measurement_id: str | None
    expected_information_gain_bits: float
    utility_per_cost: float
    request: MeasurementRequest | None
    reason: str


@dataclass(frozen=True)
class PosteriorUpdate:
    update_id: str
    scope_id: str
    receipt_id: str
    observation: str
    posterior: tuple[tuple[str, float], ...]
    entropy_before_bits: float
    entropy_after_bits: float
    evidence_lineage: tuple[str, ...]
    top_hypotheses: tuple[str, ...]


class CompetingHypothesisPortfolio:
    """Immutable hypothesis definitions plus a scope-local posterior projection."""

    def __init__(self, *, anchor_candidate_ref: str, scope_id: str, scope_digest: str,
                 hypotheses: tuple[CompetingHypothesis, ...],
                 plans: tuple[MeasurementPlan, ...],
                 replay_guard: MeasurementReplayGuard | None = None):
        if not all(isinstance(x, str) and x.strip()
                   for x in (anchor_candidate_ref, scope_id, scope_digest)):
            raise ValueError("portfolio candidate and scope bindings are required")
        if "@" not in anchor_candidate_ref:
            raise ValueError("anchor candidate must be an immutable version")
        if len(hypotheses) < 2:
            raise ValueError("at least two competing hypotheses are required")
        if len({h.hypothesis_id for h in hypotheses}) != len(hypotheses):
            raise ValueError("hypothesis ids must be unique")
        if len({p.measurement_id for p in plans}) != len(plans):
            raise ValueError("measurement plan ids must be unique")
        if not plans:
            raise ValueError("at least one measurement plan is required")
        common_measurements = {p.measurement_id for p in plans}
        if any({key for key, _ in h.predictions} != common_measurements for h in hypotheses):
            raise ValueError("every hypothesis must predict every registered measurement")
        for plan in plans:
            outcome_spaces = [set(h.distribution(plan.measurement_id)) for h in hypotheses]
            if any(space != outcome_spaces[0] for space in outcome_spaces[1:]):
                raise ValueError("competing hypotheses must share each measurement outcome space")
        total = sum(h.prior for h in hypotheses)
        self.hypotheses = tuple(hypotheses)
        self.plans = tuple(sorted(plans, key=lambda p: p.measurement_id))
        self.anchor_candidate_ref, self.scope_id, self.scope_digest = (
            anchor_candidate_ref, scope_id, scope_digest)
        self._posterior = {h.hypothesis_id: h.prior / total for h in hypotheses}
        self._lineage: list[str] = []
        self._replay_guard = replay_guard or MeasurementReplayGuard()
        self._updates: list[PosteriorUpdate] = []

    @property
    def posterior(self) -> tuple[tuple[str, float], ...]:
        return tuple(sorted(self._posterior.items()))

    @property
    def evidence_lineage(self) -> tuple[str, ...]:
        return tuple(self._lineage)

    @property
    def updates(self) -> tuple[PosteriorUpdate, ...]:
        return tuple(self._updates)

    def _expected_information_gain(self, measurement_id: str) -> float:
        prior = self._posterior
        outcomes = sorted(set().union(*(set(h.distribution(measurement_id))
                                       for h in self.hypotheses)))
        marginal = {
            outcome: sum(prior[h.hypothesis_id] * h.distribution(measurement_id).get(outcome, 0.0)
                         for h in self.hypotheses)
            for outcome in outcomes
        }
        prior_entropy = _entropy(list(prior.values()))
        expected_posterior_entropy = 0.0
        for outcome, p_outcome in marginal.items():
            if p_outcome <= 0:
                continue
            posterior = [
                prior[h.hypothesis_id] * h.distribution(measurement_id).get(outcome, 0.0)
                / p_outcome for h in self.hypotheses
            ]
            expected_posterior_entropy += p_outcome * _entropy(posterior)
        return max(0.0, prior_entropy - expected_posterior_entropy)

    def select_measurement(self, *, request_id: str, remaining_budget: float,
                           min_information_gain_bits: float = 1e-9) -> MeasurementDecision:
        if not request_id or not request_id.strip():
            raise ValueError("request_id is required")
        if (isinstance(remaining_budget, bool) or not math.isfinite(remaining_budget)
                or remaining_budget < 0):
            raise ValueError("remaining_budget must be finite and non-negative")
        if (isinstance(min_information_gain_bits, bool)
                or not math.isfinite(min_information_gain_bits)
                or min_information_gain_bits < 0):
            raise ValueError("minimum information gain must be finite and non-negative")
        feasible = [p for p in self.plans if p.estimated_cost <= remaining_budget
                    and p.max_cost <= remaining_budget]
        if not feasible:
            return MeasurementDecision(SelectionStatus.BUDGET_EXHAUSTED, None, 0.0, 0.0,
                                       None, "no registered measurement fits the remaining budget")
        ranked = []
        for plan in feasible:
            gain = self._expected_information_gain(plan.measurement_id)
            utility = gain / max(plan.estimated_cost, 1e-12)
            ranked.append((utility, gain, plan.measurement_id, plan))
        utility, gain, _, selected = sorted(ranked, key=lambda row: (-row[0], -row[1], row[2]))[0]
        if gain <= min_information_gain_bits:
            return MeasurementDecision(SelectionStatus.NO_DISCRIMINATING_MEASUREMENT,
                selected.measurement_id, gain, utility, None,
                "registered measurements do not separate the current hypotheses")
        request = MeasurementRequest(
            request_id=request_id, candidate_ref=self.anchor_candidate_ref,
            scope_id=self.scope_id, scope_digest=self.scope_digest,
            protocol_id=selected.protocol_id, target_digest=selected.target_digest,
            params_digest=selected.params_digest, estimated_cost=selected.estimated_cost,
            max_cost=selected.max_cost)
        return MeasurementDecision(SelectionStatus.SELECT, selected.measurement_id,
            gain, utility, request, "selected by expected information gain per estimated cost")

    def update(self, request: MeasurementRequest, receipt: SignedMeasurementReceipt,
               public_key_bytes: bytes, *, executor_id: str, key_id: str) -> PosteriorUpdate:
        if receipt.status != MeasurementStatus.SELECT.value or not receipt.outcome:
            raise ValueError("only signed SELECT receipts can update the hypothesis posterior")
        if request.candidate_ref != self.anchor_candidate_ref or request.scope_id != self.scope_id:
            raise ValueError("request is outside this portfolio scope")
        if request.scope_digest != self.scope_digest:
            raise ValueError("request scope digest mismatch")
        plan = next((p for p in self.plans if p.protocol_id == request.protocol_id
                     and p.target_digest == request.target_digest
                     and p.params_digest == request.params_digest), None)
        if plan is None:
            raise ValueError("request does not match a registered measurement plan")
        if request.estimated_cost != plan.estimated_cost or request.max_cost != plan.max_cost:
            raise ValueError("request cost differs from the registered plan")
        expected = {"executor_id": executor_id, "key_id": key_id,
            "candidate_ref": self.anchor_candidate_ref, "scope_id": self.scope_id,
            "scope_digest": self.scope_digest, "protocol_id": plan.protocol_id,
            "target_digest": plan.target_digest, "params_digest": plan.params_digest,
            "request_id": request.request_id, "request_digest": request.request_digest}
        verify_receipt(receipt, public_key_bytes, expected_context=expected)
        likelihoods = {h.hypothesis_id: h.distribution(plan.measurement_id).get(receipt.outcome, 0.0)
                       for h in self.hypotheses}
        if not any(likelihood > 0 for likelihood in likelihoods.values()):
            raise ValueError("observation is impossible under every registered hypothesis")
        self._replay_guard.accept(receipt)
        before = _entropy(list(self._posterior.values()))
        log_weights = {}
        for hypothesis_id, prior in self._posterior.items():
            likelihood = likelihoods[hypothesis_id]
            log_weights[hypothesis_id] = (math.log(prior) + math.log(likelihood)
                                          if likelihood > 0 else float("-inf"))
        maximum = max(log_weights.values())
        weights = {key: (math.exp(value - maximum) if math.isfinite(value) else 0.0)
                   for key, value in log_weights.items()}
        normalizer = sum(weights.values())
        self._posterior = {key: value / normalizer for key, value in weights.items()}
        self._lineage.append(receipt.receipt_id)
        after = _entropy(list(self._posterior.values()))
        top_probability = max(self._posterior.values())
        top = tuple(sorted(key for key, value in self._posterior.items()
                           if math.isclose(value, top_probability, rel_tol=1e-12, abs_tol=1e-12)))
        update_id = "e12a15:" + _sha({"scope": self.scope_id,
            "receipt_ids": self._lineage, "posterior": self.posterior})
        result = PosteriorUpdate(update_id, self.scope_id, receipt.receipt_id,
            receipt.outcome, self.posterior, before, after, tuple(self._lineage), top)
        self._updates.append(result)
        return result


def propose_revision(parent: CandidateVersion, *, new_definition: str,
                     grammar_version: str) -> CandidateVersion:
    """Create a new immutable candidate version; never rewrite the parent."""
    if not isinstance(parent, CandidateVersion):
        raise TypeError("parent must be a CandidateVersion")
    if not new_definition or not new_definition.strip():
        raise ValueError("new_definition is required")
    if not grammar_version or not grammar_version.strip():
        raise ValueError("grammar_version is required")
    return CandidateVersion(candidate_id=parent.candidate_id,
        version=parent.version + 1, definition=new_definition,
        grammar_version=grammar_version,
        parent_refs=(f"{parent.candidate_id}@{parent.version}",))
