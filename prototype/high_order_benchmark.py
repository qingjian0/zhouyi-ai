"""Controlled pairwise-preserving benchmark for third-order reasoning.

This benchmark is a mathematical identifiability probe, not a claim that the
full SROK learner has solved relational reasoning. It provides a balanced
three-variable parity task whose unary and pairwise marginals are identical
under both labels, while the third-order product determines the label.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math
import random
from typing import Iterable, Sequence


Bits = tuple[int, int, int]


@dataclass(frozen=True)
class ParityExample:
    bits: Bits
    label: int


@dataclass(frozen=True)
class ProbeResult:
    interaction_order: int
    accuracy: float
    mean_log_loss: float
    epochs: int


@dataclass(frozen=True)
class IdentifiabilityReport:
    examples: int
    positive_examples: int
    negative_examples: int
    max_unary_label_correlation: float
    max_pairwise_label_correlation: float
    third_order_label_correlation: float
    pairwise_conditional_tv: float


def parity_label(bits: Sequence[int]) -> int:
    """Return +1 iff the product of exactly three {-1,+1} values is +1."""
    if len(bits) != 3 or any(value not in (-1, 1) for value in bits):
        raise ValueError("parity requires exactly three values from {-1,+1}")
    return bits[0] * bits[1] * bits[2]


def truth_table() -> tuple[ParityExample, ...]:
    """All eight states exactly once; labels are balanced four-to-four."""
    rows = []
    for bits in product((-1, 1), repeat=3):
        state = (bits[0], bits[1], bits[2])
        rows.append(ParityExample(state, parity_label(state)))
    return tuple(rows)


def make_dataset(*, repeats: int = 32, seed: int = 0) -> tuple[ParityExample, ...]:
    """Create a balanced dataset without changing the exact parity marginals."""
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    rows = list(truth_table()) * repeats
    random.Random(seed).shuffle(rows)
    return tuple(rows)


def interaction_features(bits: Sequence[int], order: int) -> tuple[float, ...]:
    """Return intercept plus every monomial of degree <= order."""
    if len(bits) != 3 or any(value not in (-1, 1) for value in bits):
        raise ValueError("features require exactly three values from {-1,+1}")
    if isinstance(order, bool) or not isinstance(order, int) or order not in (1, 2, 3):
        raise ValueError("interaction order must be 1, 2, or 3")
    x, y, z = bits
    features = [1.0, float(x), float(y), float(z)]
    if order >= 2:
        features.extend((float(x * y), float(x * z), float(y * z)))
    if order >= 3:
        features.append(float(x * y * z))
    return tuple(features)


def _sigmoid(value: float) -> float:
    if value >= 0:
        exp_value = math.exp(-min(value, 60.0))
        return 1.0 / (1.0 + exp_value)
    exp_value = math.exp(max(value, -60.0))
    return exp_value / (1.0 + exp_value)


def fit_linear_probe(
    examples: Iterable[ParityExample],
    *,
    interaction_order: int,
    epochs: int = 500,
    learning_rate: float = 0.25,
    l2: float = 0.01,
) -> tuple[float, ...]:
    """Fit a deterministic full-batch logistic probe with zero initialization."""
    rows = tuple(examples)
    if not rows:
        raise ValueError("examples must not be empty")
    if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
        raise ValueError("epochs must be a positive integer")
    if not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be finite and positive")
    if not math.isfinite(l2) or l2 < 0:
        raise ValueError("l2 must be finite and non-negative")
    matrix = [interaction_features(row.bits, interaction_order) for row in rows]
    labels = [1.0 if row.label == 1 else 0.0 for row in rows]
    weights = [0.0] * len(matrix[0])
    scale = 1.0 / len(rows)
    for _ in range(epochs):
        gradient = [0.0] * len(weights)
        for features, label in zip(matrix, labels):
            probability = _sigmoid(math.fsum(w * x for w, x in zip(weights, features)))
            error = probability - label
            for index, value in enumerate(features):
                gradient[index] += error * value
        for index in range(len(weights)):
            penalty = 0.0 if index == 0 else l2 * weights[index]
            weights[index] -= learning_rate * (gradient[index] * scale + penalty)
            if not math.isfinite(weights[index]):
                raise ValueError("probe weights became non-finite")
    return tuple(weights)


def evaluate_linear_probe(
    train: Iterable[ParityExample],
    test: Iterable[ParityExample],
    *,
    interaction_order: int,
    epochs: int = 500,
) -> ProbeResult:
    """Train on one shuffled draw and evaluate on a separately shuffled draw."""
    train_rows, test_rows = tuple(train), tuple(test)
    if not test_rows:
        raise ValueError("test examples must not be empty")
    weights = fit_linear_probe(
        train_rows, interaction_order=interaction_order, epochs=epochs
    )
    correct = 0
    total_loss = 0.0
    for row in test_rows:
        features = interaction_features(row.bits, interaction_order)
        probability = _sigmoid(math.fsum(w * x for w, x in zip(weights, features)))
        predicted = 1 if probability >= 0.5 else -1
        correct += int(predicted == row.label)
        target = 1.0 if row.label == 1 else 0.0
        clipped = min(max(probability, 1e-12), 1.0 - 1e-12)
        total_loss += -(target * math.log(clipped) + (1.0 - target) * math.log(1.0 - clipped))
    return ProbeResult(
        interaction_order=interaction_order,
        accuracy=correct / len(test_rows),
        mean_log_loss=total_loss / len(test_rows),
        epochs=epochs,
    )


def _conditional_pair_distribution(
    rows: Sequence[ParityExample], pair: tuple[int, int], label: int
) -> dict[tuple[int, int], float]:
    selected = [row for row in rows if row.label == label]
    counts = {(a, b): 0 for a, b in product((-1, 1), repeat=2)}
    for row in selected:
        counts[(row.bits[pair[0]], row.bits[pair[1]])] += 1
    total = len(selected)
    if total == 0:
        raise ValueError("both parity classes must be present")
    return {key: value / total for key, value in counts.items()}


def identifiability_report(examples: Iterable[ParityExample]) -> IdentifiabilityReport:
    """Measure label correlations and conditional pairwise distribution gaps."""
    rows = tuple(examples)
    if not rows:
        raise ValueError("examples must not be empty")
    if any(row.label not in (-1, 1) or parity_label(row.bits) != row.label for row in rows):
        raise ValueError("dataset contains an invalid parity label")
    positives = sum(row.label == 1 for row in rows)
    negatives = len(rows) - positives
    if positives == 0 or negatives == 0:
        raise ValueError("both parity classes must be represented")
    unary = [
        abs(math.fsum(row.label * row.bits[index] for row in rows) / len(rows))
        for index in range(3)
    ]
    pairwise = [
        abs(math.fsum(row.label * row.bits[i] * row.bits[j] for row in rows) / len(rows))
        for i, j in ((0, 1), (0, 2), (1, 2))
    ]
    triple = abs(
        math.fsum(row.label * row.bits[0] * row.bits[1] * row.bits[2] for row in rows)
        / len(rows)
    )
    tvs = []
    for pair in ((0, 1), (0, 2), (1, 2)):
        positive = _conditional_pair_distribution(rows, pair, 1)
        negative = _conditional_pair_distribution(rows, pair, -1)
        tvs.append(0.5 * math.fsum(abs(positive[key] - negative[key]) for key in positive))
    return IdentifiabilityReport(
        examples=len(rows),
        positive_examples=positives,
        negative_examples=negatives,
        max_unary_label_correlation=max(unary),
        max_pairwise_label_correlation=max(pairwise),
        third_order_label_correlation=triple,
        pairwise_conditional_tv=max(tvs),
    )


def run_parity_probe_suite(*, repeats: int = 32, epochs: int = 500) -> tuple[ProbeResult, ...]:
    """Compare unary, pairwise and third-order probes on independent shuffles."""
    train = make_dataset(repeats=repeats, seed=17)
    test = make_dataset(repeats=repeats, seed=29)
    return tuple(
        evaluate_linear_probe(
            train, test, interaction_order=order, epochs=epochs
        )
        for order in (1, 2, 3)
    )
