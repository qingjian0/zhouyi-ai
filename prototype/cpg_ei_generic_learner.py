"""Dimension-generic CPG-EI relation learner.

The learner consumes Boolean transition rows and explicit relation supports.
It uses a complete Boolean-monomial basis up to max_arity, so XOR/parity
teachers are representable without hard-coding six-line or 2nd/3rd-order
features. This is a controlled synthetic benchmark, not a language model.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Iterable, Sequence


Support = tuple[int, ...]


def relation_supports(input_dim: int, min_arity: int = 1,
                      max_arity: int = 6) -> tuple[Support, ...]:
    if isinstance(input_dim, bool) or not isinstance(input_dim, int) or input_dim < 1:
        raise ValueError("input_dim must be a positive integer")
    if (isinstance(min_arity, bool) or not isinstance(min_arity, int)
            or isinstance(max_arity, bool) or not isinstance(max_arity, int)
            or min_arity < 1 or max_arity < min_arity or max_arity > input_dim):
        raise ValueError("arity bounds must satisfy 1 <= min_arity <= max_arity <= input_dim")
    return tuple(
        support
        for arity in range(min_arity, max_arity + 1)
        for support in itertools.combinations(range(input_dim), arity)
    )


def encode_relations(state: Sequence[int], supports: Sequence[Support]) -> tuple[float, ...]:
    if not state or any(bit not in (0, 1) for bit in state):
        raise ValueError("state must be a non-empty binary vector")
    for support in supports:
        if (not support or tuple(sorted(set(support))) != tuple(support)
                or support[0] < 0 or support[-1] >= len(state)):
            raise ValueError("invalid relation support for state dimension")
    return (1.0, *(
        float(math.prod(state[index] for index in support))
        for support in supports
    ))


@dataclass(frozen=True)
class TransitionExample:
    state: tuple[int, ...]
    target: tuple[int, ...]


@dataclass
class RelationalTransitionModel:
    input_dim: int
    output_dim: int
    supports: tuple[Support, ...]
    weights: list[list[float]]

    @classmethod
    def create(cls, input_dim: int, output_dim: int,
               min_arity: int = 1, max_arity: int = 6) -> "RelationalTransitionModel":
        if isinstance(output_dim, bool) or not isinstance(output_dim, int) or output_dim < 1:
            raise ValueError("output_dim must be a positive integer")
        supports = relation_supports(input_dim, min_arity, max_arity)
        return cls(input_dim, output_dim, supports,
                   [[0.0] * (len(supports) + 1) for _ in range(output_dim)])

    def _validate_example(self, row: TransitionExample) -> None:
        if len(row.state) != self.input_dim or any(v not in (0, 1) for v in row.state):
            raise ValueError("example state dimension or values do not match model")
        if len(row.target) != self.output_dim or any(v not in (0, 1) for v in row.target):
            raise ValueError("example target dimension or values do not match model")

    def logits(self, state: Sequence[int]) -> tuple[float, ...]:
        if len(state) != self.input_dim:
            raise ValueError("state dimension does not match model")
        features = encode_relations(state, self.supports)
        return tuple(sum(w * x for w, x in zip(head, features)) for head in self.weights)

    @staticmethod
    def _sigmoid(value: float) -> float:
        if value >= 0:
            z = math.exp(-value)
            return 1.0 / (1.0 + z)
        z = math.exp(value)
        return z / (1.0 + z)

    def predict_proba(self, state: Sequence[int]) -> tuple[float, ...]:
        return tuple(self._sigmoid(value) for value in self.logits(state))

    def predict(self, state: Sequence[int]) -> tuple[int, ...]:
        return tuple(int(value >= 0.5) for value in self.predict_proba(state))

    def train(self, examples: Sequence[TransitionExample], *, epochs: int = 500,
              learning_rate: float = 0.2, l2: float = 1e-5) -> list[float]:
        if not examples:
            raise ValueError("training examples must not be empty")
        if epochs < 1 or learning_rate <= 0 or l2 < 0:
            raise ValueError("invalid optimizer configuration")
        for row in examples:
            self._validate_example(row)
        encoded = [(encode_relations(row.state, self.supports), row.target)
                   for row in examples]
        n = float(len(encoded))
        losses: list[float] = []
        for _ in range(epochs):
            gradients = [[0.0] * (len(self.supports) + 1)
                         for _ in range(self.output_dim)]
            total_loss = 0.0
            for features, target in encoded:
                for out, head in enumerate(self.weights):
                    logit = sum(w * x for w, x in zip(head, features))
                    probability = self._sigmoid(logit)
                    label = target[out]
                    total_loss += (max(logit, 0.0) - logit * label
                                   + math.log1p(math.exp(-abs(logit))))
                    error = probability - label
                    for j, feature in enumerate(features):
                        gradients[out][j] += error * feature
            for out, head in enumerate(self.weights):
                for j in range(len(head)):
                    penalty = 0.0 if j == 0 else l2 * head[j]
                    head[j] -= learning_rate * (gradients[out][j] / n + penalty)
            losses.append(total_loss / (n * self.output_dim))
        return losses


def evaluate(model: RelationalTransitionModel,
             examples: Iterable[TransitionExample]) -> dict[str, float]:
    rows = list(examples)
    if not rows:
        raise ValueError("evaluation examples must not be empty")
    for row in rows:
        model._validate_example(row)
    correct = sum(
        int(model.predict(row.state) == row.target) for row in rows
    )
    bit_correct = sum(
        int(a == b)
        for row in rows
        for a, b in zip(model.predict(row.state), row.target)
    )
    return {
        "examples": float(len(rows)),
        "exact_state_accuracy": correct / len(rows),
        "bit_accuracy": bit_correct / (len(rows) * model.output_dim),
    }
