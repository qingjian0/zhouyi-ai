"""ZNCA N2: sparse typed relational dynamics with learnable influence weights.

A small dependency-free reference learner. It is deliberately not presented
as a general neural architecture: candidate terms are supplied, then their
weights are fitted from state-transition examples.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Iterable


class DynamicsError(ValueError):
    """Invalid state, transition, or dynamics configuration."""


@dataclass(frozen=True)
class StateSnapshot:
    values: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        keys = [key for key, _ in self.values]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise DynamicsError("state keys must be sorted and unique")
        for key, value in self.values:
            if not key.strip() or not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise DynamicsError("state values must be finite and in [0, 1]")

    @classmethod
    def from_mapping(cls, values: dict[str, float]) -> "StateSnapshot":
        return cls(tuple(sorted(values.items())))

    def as_dict(self) -> dict[str, float]:
        return dict(self.values)


@dataclass(frozen=True)
class SourceSlot:
    role: str
    state_key: str

    def __post_init__(self) -> None:
        if not self.role.strip() or not self.state_key.strip():
            raise DynamicsError("source role and state_key are required")


@dataclass(frozen=True)
class InfluenceTerm:
    term_id: str
    relation_type: str
    sources: tuple[SourceSlot, ...]
    target: str
    polarity: int = 1
    weight: float = 0.5

    def __post_init__(self) -> None:
        if not self.term_id.strip() or not self.relation_type.strip() or not self.target.strip():
            raise DynamicsError("term_id, relation_type and target are required")
        if not self.sources:
            raise DynamicsError("an influence term needs at least one source")
        roles = [slot.role for slot in self.sources]
        if len(roles) != len(set(roles)):
            raise DynamicsError("source roles must be unique within a term")
        if len({slot.state_key for slot in self.sources}) != len(self.sources):
            raise DynamicsError("source state keys must be unique within a term")
        if self.polarity not in (-1, 1):
            raise DynamicsError("polarity must be -1 or +1")
        if not math.isfinite(self.weight) or self.weight < 0:
            raise DynamicsError("weight must be finite and non-negative")


@dataclass(frozen=True)
class TransitionExample:
    before: StateSnapshot
    after: StateSnapshot
    evidence_ref: str

    def __post_init__(self) -> None:
        if not self.evidence_ref.strip():
            raise DynamicsError("transition evidence_ref is required")
        if set(self.before.as_dict()) != set(self.after.as_dict()):
            raise DynamicsError("before and after states must have identical keys")


@dataclass(frozen=True)
class FitReport:
    epochs: int
    initial_loss: float
    final_loss: float
    examples: int
    terms: int


class RelationalDynamicsModel:
    """Synchronous state update from typed pairwise and higher-order terms."""

    def __init__(self, terms: Iterable[InfluenceTerm], *,
                 biases: dict[str, float] | None = None) -> None:
        self.terms = tuple(terms)
        if len({term.term_id for term in self.terms}) != len(self.terms):
            raise DynamicsError("term_id values must be unique")
        targets = {term.target for term in self.terms}
        self.biases = {target: float((biases or {}).get(target, 0.0))
                       for target in targets}
        if any(not math.isfinite(value) for value in self.biases.values()):
            raise DynamicsError("biases must be finite")

    @staticmethod
    def _product(state: dict[str, float], term: InfluenceTerm) -> float:
        try:
            result = 1.0
            for slot in term.sources:
                result *= state[slot.state_key]
            return result
        except KeyError as exc:
            raise DynamicsError(f"missing source state: {exc.args[0]}") from exc

    @staticmethod
    def _sigmoid(value: float) -> float:
        value = max(-30.0, min(30.0, value))
        return 1.0 / (1.0 + math.exp(-value))

    def predict(self, state: StateSnapshot) -> StateSnapshot:
        """All target values are computed from the same pre-transition state."""
        values = state.as_dict()
        logits = dict(self.biases)
        for term in self.terms:
            logits[term.target] += term.polarity * term.weight * self._product(values, term)
        updated = dict(values)
        for target, logit in logits.items():
            updated[target] = self._sigmoid(logit)
        return StateSnapshot.from_mapping(updated)

    def rollout(self, initial: StateSnapshot, steps: int) -> tuple[StateSnapshot, ...]:
        if steps < 0:
            raise DynamicsError("steps must be non-negative")
        states = [initial]
        for _ in range(steps):
            states.append(self.predict(states[-1]))
        return tuple(states)

    def _loss_and_gradients(self, examples: tuple[TransitionExample, ...]):
        if not examples:
            raise DynamicsError("at least one training example is required")
        targets = tuple(sorted(self.biases))
        grad_bias = {target: 0.0 for target in targets}
        grad_weight = [0.0 for _ in self.terms]
        loss = 0.0
        count = len(examples) * max(1, len(targets))
        for example in examples:
            before, after = example.before.as_dict(), example.after.as_dict()
            logits = dict(self.biases)
            products = [self._product(before, term) for term in self.terms]
            for term, product in zip(self.terms, products):
                logits[term.target] += term.polarity * term.weight * product
            for target in targets:
                prediction = self._sigmoid(logits[target])
                actual = after[target]
                eps = 1e-12
                loss -= actual * math.log(max(eps, prediction)) + (1.0 - actual) * math.log(max(eps, 1.0 - prediction))
                error = prediction - actual
                grad_bias[target] += error / count
                for index, (term, product) in enumerate(zip(self.terms, products)):
                    if term.target == target:
                        grad_weight[index] += error * term.polarity * product / count
        return loss / count, grad_bias, grad_weight

    def fit(self, examples: Iterable[TransitionExample], *,
            epochs: int = 1000, learning_rate: float = 0.1,
            l1: float = 0.0) -> FitReport:
        """Full-batch BCE fitting; provide a training split, not locked test data."""
        data = tuple(examples)
        if epochs < 1 or learning_rate <= 0 or l1 < 0:
            raise DynamicsError("epochs/lr must be positive and l1 non-negative")
        if not math.isfinite(learning_rate) or not math.isfinite(l1):
            raise DynamicsError("learning_rate and l1 must be finite")
        if not data:
            raise DynamicsError("at least one training example is required")
        keys = set(data[0].before.as_dict())
        if any(set(row.before.as_dict()) != keys for row in data):
            raise DynamicsError("all examples must use the same state schema")
        if any(term.target not in keys or any(slot.state_key not in keys for slot in term.sources)
               for term in self.terms):
            raise DynamicsError("all term source and target keys must exist in state schema")
        initial_loss, _, _ = self._loss_and_gradients(data)
        for _ in range(epochs):
            _, grad_bias, grad_weight = self._loss_and_gradients(data)
            self.biases = {
                key: self.biases[key] - learning_rate * grad_bias[key]
                for key in self.biases
            }
            updated = []
            for term, gradient in zip(self.terms, grad_weight):
                penalty = l1 if term.weight > 0 else 0.0
                weight = max(0.0, term.weight - learning_rate * (gradient + penalty))
                updated.append(replace(term, weight=weight))
            self.terms = tuple(updated)
        final_loss, _, _ = self._loss_and_gradients(data)
        return FitReport(epochs, initial_loss, final_loss, len(data), len(self.terms))
