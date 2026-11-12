"""CPU-friendly CPG-EI trainable MVP.

This is a controlled transition-learning benchmark, not a language model.
The internal representation is a six-line Yixiang state plus explicit
2nd/3rd-order relation (hyperedge) features. A bank of logistic heads learns
the next six-bit state. Pure Python keeps the first training path dependency-
free and reproducible; later backends can preserve this model contract.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Example:
    state: tuple[int, int, int, int, int, int]
    target: tuple[int, int, int, int, int, int]


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def feature_names() -> tuple[str, ...]:
    names = ["bias"]
    names.extend(f"line_{i}" for i in range(6))
    for order in (2, 3):
        for indices in itertools.combinations(range(6), order):
            names.append(f"hyperedge_{order}_" + "_".join(map(str, indices)))
    return tuple(names)


FEATURE_NAMES = feature_names()


def encode_state(state: Sequence[int]) -> tuple[float, ...]:
    """Encode yin/yang bits and all pair/triple conjunction hyperedges."""
    if len(state) != 6 or any(bit not in (0, 1) for bit in state):
        raise ValueError("state must contain exactly six binary lines (0/1)")
    values = [float(bit) for bit in state]
    features = [1.0, *values]
    for order in (2, 3):
        features.extend(
            float(math.prod(state[index] for index in indices))
            for indices in itertools.combinations(range(6), order)
        )
    return tuple(features)


def _teacher(
    seed: int, *, sparse_relations: bool = False
) -> tuple[tuple[float, ...], ...]:
    rng = random.Random(seed)
    if not sparse_relations:
        # Six independent but jointly state-conditioned transition heads.
        return tuple(
            tuple(rng.gauss(0.0, 0.9) for _ in FEATURE_NAMES)
            for _ in range(6)
        )
    # Controlled sparse teacher: 3 of 15 pair edges and 3 of 20 triple edges.
    active_pairs = {0, 4, 10}
    active_triples = {1, 7, 15}
    heads = []
    for _ in range(6):
        row = [rng.gauss(0.0, 0.9) for _ in range(7)]
        row.extend(rng.gauss(0.0, 0.9) if i in active_pairs else 0.0 for i in range(15))
        row.extend(rng.gauss(0.0, 0.9) if i in active_triples else 0.0 for i in range(20))
        heads.append(tuple(row))
    return tuple(heads)


def _target(state: Sequence[int], weights: Sequence[Sequence[float]]) -> tuple[int, ...]:
    x = encode_state(state)
    return tuple(
        int(sum(w * v for w, v in zip(head, x)) >= 0.0)
        for head in weights
    )


def make_dataset(
    count: int,
    seed: int,
    teacher_seed: int = 20261112,
    sparse_teacher: bool = False,
) -> list[Example]:
    if count < 1:
        raise ValueError("count must be positive")
    rng = random.Random(seed)
    teacher = _teacher(teacher_seed, sparse_relations=sparse_teacher)
    rows = []
    for _ in range(count):
        state = tuple(rng.randrange(2) for _ in range(6))
        rows.append(Example(state, _target(state, teacher)))  # type: ignore[arg-type]
    return rows


@dataclass
class CpgEiTransitionModel:
    """A trainable sparse-relation transition model with six logistic heads."""

    weights: list[list[float]]
    # One shared learnable gate for each pair/triple relation feature.
    gate_logits: list[float]
    active_relation_indices: set[int]

    @classmethod
    def create(
        cls, active_relation_indices: Iterable[int] | None = None
    ) -> "CpgEiTransitionModel":
        active = (
            set(range(7, len(FEATURE_NAMES)))
            if active_relation_indices is None
            else set(active_relation_indices)
        )
        if any(
            isinstance(index, bool) or not isinstance(index, int)
            or not 7 <= index < len(FEATURE_NAMES)
            for index in active
        ):
            raise ValueError("active relation indices must be in [7, 41]")
        return cls(
            [[0.0] * len(FEATURE_NAMES) for _ in range(6)],
            [2.0] * (len(FEATURE_NAMES) - 7),
            active,
        )

    def relation_gate_probabilities(self) -> tuple[float, ...]:
        return tuple(_sigmoid(value) for value in self.gate_logits)

    def _gated_features(self, state: Sequence[int]) -> tuple[float, ...]:
        raw = encode_state(state)
        gates = self.relation_gate_probabilities()
        return (
            *raw[:7],
            *(
                value * gate if index in self.active_relation_indices else 0.0
                for index, (value, gate) in enumerate(zip(raw[7:], gates), start=7)
            ),
        )

    def logits(self, state: Sequence[int]) -> tuple[float, ...]:
        x = self._gated_features(state)
        return tuple(sum(w * v for w, v in zip(head, x)) for head in self.weights)

    def predict_proba(self, state: Sequence[int]) -> tuple[float, ...]:
        return tuple(_sigmoid(value) for value in self.logits(state))

    def predict(self, state: Sequence[int]) -> tuple[int, ...]:
        return tuple(int(value >= 0.5) for value in self.predict_proba(state))

    def train(
        self,
        examples: Sequence[Example],
        epochs: int = 120,
        learning_rate: float = 0.35,
        l2: float = 1e-4,
        gate_l1: float = 1e-4,
        edge_group_l1: float = 0.0,
        optimizer: str = "sgd",
        adam_beta1: float = 0.9,
        adam_beta2: float = 0.999,
        adam_epsilon: float = 1e-8,
    ) -> list[float]:
        if not examples:
            raise ValueError("training data must not be empty")
        if (epochs < 1 or learning_rate <= 0.0 or l2 < 0.0
                or gate_l1 < 0.0 or edge_group_l1 < 0.0):
            raise ValueError("invalid optimizer configuration")
        if optimizer not in {"sgd", "adam"}:
            raise ValueError("optimizer must be 'sgd' or 'adam'")
        if not (0.0 <= adam_beta1 < 1.0 and 0.0 <= adam_beta2 < 1.0
                and math.isfinite(adam_epsilon) and adam_epsilon > 0.0):
            raise ValueError("invalid Adam configuration")
        rows = [(encode_state(row.state), row.target) for row in examples]
        losses = []
        n = float(len(rows))
        weight_m = [[0.0] * len(FEATURE_NAMES) for _ in range(6)]
        weight_v = [[0.0] * len(FEATURE_NAMES) for _ in range(6)]
        gate_m = [0.0] * len(self.gate_logits)
        gate_v = [0.0] * len(self.gate_logits)
        adam_step = 0
        for _ in range(epochs):
            weight_gradients = [[0.0] * len(FEATURE_NAMES) for _ in range(6)]
            gate_gradients = [0.0] * len(self.gate_logits)
            gates = self.relation_gate_probabilities()
            gate_derivatives = [gate * (1.0 - gate) for gate in gates]
            total_loss = 0.0
            for raw, target in rows:
                effective = (
                    *raw[:7],
                    *(
                        value * gate if index in self.active_relation_indices else 0.0
                        for index, (value, gate) in enumerate(
                            zip(raw[7:], gates), start=7
                        )
                    ),
                )
                for head_index, head in enumerate(self.weights):
                    logit = sum(w * value for w, value in zip(head, effective))
                    probability = _sigmoid(logit)
                    label = target[head_index]
                    total_loss += max(logit, 0.0) - logit * label + math.log1p(math.exp(-abs(logit)))
                    error = probability - label
                    weight_grad = weight_gradients[head_index]
                    for j, value in enumerate(effective):
                        weight_grad[j] += error * value
                    for gate_index, feature_index in enumerate(range(7, len(raw))):
                        if feature_index not in self.active_relation_indices:
                            continue
                        gate_gradients[gate_index] += (
                            error * head[feature_index] * raw[feature_index]
                            * gate_derivatives[gate_index]
                        )
            for head_index, head in enumerate(self.weights):
                grad = weight_gradients[head_index]
                for j in range(len(head)):
                    grad[j] = grad[j] / n + l2 * head[j]
            for gate_index in range(len(self.gate_logits)):
                gate_gradients[gate_index] = (
                    gate_gradients[gate_index] / (n * 6.0)
                    + (gate_l1 / 6.0) * gate_derivatives[gate_index]
                )

            if optimizer == "sgd":
                for head_index, head in enumerate(self.weights):
                    for j in range(len(head)):
                        head[j] -= learning_rate * weight_gradients[head_index][j]
                for gate_index in range(len(self.gate_logits)):
                    self.gate_logits[gate_index] -= (
                        learning_rate * gate_gradients[gate_index]
                    )
            else:
                adam_step += 1
                correction1 = 1.0 - adam_beta1 ** adam_step
                correction2 = 1.0 - adam_beta2 ** adam_step
                for head_index, head in enumerate(self.weights):
                    for j in range(len(head)):
                        grad = weight_gradients[head_index][j]
                        weight_m[head_index][j] = (
                            adam_beta1 * weight_m[head_index][j]
                            + (1.0 - adam_beta1) * grad
                        )
                        weight_v[head_index][j] = (
                            adam_beta2 * weight_v[head_index][j]
                            + (1.0 - adam_beta2) * grad * grad
                        )
                        m_hat = weight_m[head_index][j] / correction1
                        v_hat = weight_v[head_index][j] / correction2
                        head[j] -= (
                            learning_rate * m_hat
                            / (math.sqrt(v_hat) + adam_epsilon)
                        )
                for gate_index in range(len(self.gate_logits)):
                    grad = gate_gradients[gate_index]
                    gate_m[gate_index] = (
                        adam_beta1 * gate_m[gate_index]
                        + (1.0 - adam_beta1) * grad
                    )
                    gate_v[gate_index] = (
                        adam_beta2 * gate_v[gate_index]
                        + (1.0 - adam_beta2) * grad * grad
                    )
                    m_hat = gate_m[gate_index] / correction1
                    v_hat = gate_v[gate_index] / correction2
                    self.gate_logits[gate_index] -= (
                        learning_rate * m_hat
                        / (math.sqrt(v_hat) + adam_epsilon)
                    )

            # Proximal group-L1 over each relation's six output weights. This
            # removes whole candidate edges rather than sparsifying each head
            # independently.
            group_norm_sum = 0.0
            if edge_group_l1:
                for feature_index in self.active_relation_indices:
                    norm = math.sqrt(sum(
                        self.weights[head_index][feature_index] ** 2
                        for head_index in range(6)
                    ))
                    group_norm_sum += norm
                    shrink = max(
                        0.0,
                        1.0 - learning_rate * edge_group_l1 / max(norm, 1e-12),
                    )
                    for head_index in range(6):
                        self.weights[head_index][feature_index] *= shrink
            losses.append(
                total_loss / (n * 6.0)
                + gate_l1 * sum(gates) / 6.0
                + edge_group_l1 * group_norm_sum
            )
        return losses


def evaluate(model: CpgEiTransitionModel, examples: Iterable[Example]) -> dict[str, float]:
    rows = list(examples)
    if not rows:
        raise ValueError("evaluation data must not be empty")
    correct_bits = 0
    correct_states = 0
    total_bits = len(rows) * 6
    for row in rows:
        predicted = model.predict(row.state)
        correct_bits += sum(int(a == b) for a, b in zip(predicted, row.target))
        correct_states += int(predicted == row.target)
    return {
        "bit_accuracy": correct_bits / total_bits,
        "exact_state_accuracy": correct_states / len(rows),
        "examples": float(len(rows)),
    }


def run_experiment(
    seed: int = 7,
    train_samples: int = 1024,
    test_samples: int = 256,
    epochs: int = 120,
) -> dict:
    train_rows = make_dataset(train_samples, seed)
    test_rows = make_dataset(test_samples, seed + 1)
    model = CpgEiTransitionModel.create()
    losses = model.train(train_rows, epochs=epochs)
    return {
        "experiment": "CPG-EI-MVP-six-line-transition",
        "seed": seed,
        "feature_count": len(FEATURE_NAMES),
        "feature_orders": [1, 2, 3],
        "train_samples": train_samples,
        "test_samples": test_samples,
        "epochs": epochs,
        "initial_train_loss": losses[0],
        "final_train_loss": losses[-1],
        "test": evaluate(model, test_rows),
        "relation_gate_summary": {
            "pair_mean": sum(model.relation_gate_probabilities()[:15]) / 15.0,
            "triple_mean": sum(model.relation_gate_probabilities()[15:]) / 20.0,
            "active_gates_gt_0_5": sum(
                gate > 0.5 for gate in model.relation_gate_probabilities()
            ),
        },
        "model_weights": model.weights,
        "claim_boundary": (
            "Synthetic finite-state transition benchmark only; not natural-language "
            "understanding, general reasoning, or evidence of superiority to Transformers."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--train-samples", type=int, default=1024)
    parser.add_argument("--test-samples", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_experiment(args.seed, args.train_samples, args.test_samples, args.epochs)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
