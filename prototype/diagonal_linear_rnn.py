"""Trainable diagonal linear recurrence baseline for P5-B comparisons."""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable, Sequence


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


@dataclass
class LinearRecurrentState:
    hidden: list[float]


@dataclass(frozen=True)
class LinearTrainMetrics:
    mean_loss: float
    examples: int
    updates: int


class DiagonalLinearRNN:
    """Linear diagonal state transition with a logistic next-symbol head.

    h[t] = tanh(raw_recurrence) * h[t-1] + input_weight*x[t] + bias
    The state transition has no multiplicative input gate or nonlinear
    candidate. Manual BPTT makes the baseline independently trainable.
    """

    def __init__(self, hidden_size: int = 9, seed: int = 11) -> None:
        if not isinstance(hidden_size, int) or hidden_size < 1:
            raise ValueError("hidden_size must be a positive integer")
        self.hidden_size = hidden_size
        rng = random.Random(seed)
        scale = 1.0 / math.sqrt(hidden_size)
        self.raw_recurrence = [rng.uniform(-0.5, 0.5) for _ in range(hidden_size)]
        self.input_weight = [rng.uniform(-scale, scale) for _ in range(hidden_size)]
        self.bias = [0.0] * hidden_size
        self.output_weight = [rng.uniform(-scale, scale) for _ in range(hidden_size)]
        self.output_bias = 0.0

    @property
    def parameter_count(self) -> int:
        return 4 * self.hidden_size + 1

    def zero_state(self) -> LinearRecurrentState:
        return LinearRecurrentState([0.0] * self.hidden_size)

    def _step(self, x: float, previous: Sequence[float]):
        recurrence = [math.tanh(v) for v in self.raw_recurrence]
        hidden = [
            recurrence[i] * previous[i] + self.input_weight[i] * x + self.bias[i]
            for i in range(self.hidden_size)
        ]
        probability = _sigmoid(
            self.output_bias + sum(a * b for a, b in zip(self.output_weight, hidden))
        )
        return hidden, recurrence, probability

    def predict_chunk(
        self, symbols: Sequence[int], state: LinearRecurrentState | None = None
    ) -> tuple[list[float], LinearRecurrentState]:
        current = self.zero_state() if state is None else LinearRecurrentState(
            [float(v) for v in state.hidden]
        )
        if len(current.hidden) != self.hidden_size or not all(
            math.isfinite(v) for v in current.hidden
        ):
            raise ValueError("state.hidden must contain finite values of hidden_size")
        predictions = []
        for symbol in symbols:
            if symbol not in (0, 1):
                raise ValueError("input symbols must be binary 0 or 1")
            hidden, _, probability = self._step(float(symbol), current.hidden)
            predictions.append(probability)
            current = LinearRecurrentState(hidden)
        return predictions, current

    def train_sequence(
        self, symbols: Sequence[int], *, learning_rate: float = 0.03,
        clip_norm: float = 1.0,
    ) -> float:
        if len(symbols) < 2 or any(x not in (0, 1) for x in symbols):
            raise ValueError("sequence must contain at least two binary symbols")
        if not math.isfinite(learning_rate) or learning_rate <= 0:
            raise ValueError("learning_rate must be positive and finite")
        if not math.isfinite(clip_norm) or clip_norm <= 0:
            raise ValueError("clip_norm must be positive and finite")

        tape = []
        old = [0.0] * self.hidden_size
        loss = 0.0
        for t, symbol in enumerate(symbols[:-1]):
            hidden, recurrence, probability = self._step(float(symbol), old)
            target = float(symbols[t + 1])
            p = min(max(probability, 1e-12), 1 - 1e-12)
            loss -= target * math.log(p) + (1 - target) * math.log(1 - p)
            tape.append((old, hidden, recurrence, probability, target, float(symbol)))
            old = hidden

        names = ("raw_recurrence", "input_weight", "bias", "output_weight")
        grads = {name: [0.0] * self.hidden_size for name in names}
        grad_output_bias = 0.0
        future = [0.0] * self.hidden_size
        for old, hidden, recurrence, probability, target, x in reversed(tape):
            dy = probability - target
            grad_output_bias += dy
            for i in range(self.hidden_size):
                grads["output_weight"][i] += dy * hidden[i]
                dh = dy * self.output_weight[i] + future[i]
                grads["raw_recurrence"][i] += (
                    dh * old[i] * (1.0 - recurrence[i] ** 2)
                )
                grads["input_weight"][i] += dh * x
                grads["bias"][i] += dh
                future[i] = dh * recurrence[i]

        all_grads = [g for values in grads.values() for g in values] + [grad_output_bias]
        norm = math.sqrt(sum(g * g for g in all_grads))
        factor = min(1.0, clip_norm / max(norm, 1e-12))
        for name, values in grads.items():
            params = getattr(self, name)
            for i, grad in enumerate(values):
                params[i] -= learning_rate * factor * grad
        self.output_bias -= learning_rate * factor * grad_output_bias
        return loss / len(tape)

    def train_final_target(
        self, context: Sequence[int], target: int, *,
        learning_rate: float = 0.03, clip_norm: float = 1.0,
    ) -> float:
        """Train one target after a context; only the final prediction is supervised."""
        if not context or any(x not in (0, 1) for x in context) or target not in (0, 1):
            raise ValueError("context must be non-empty binary data and target must be binary")
        if not math.isfinite(learning_rate) or learning_rate <= 0:
            raise ValueError("learning_rate must be positive and finite")
        if not math.isfinite(clip_norm) or clip_norm <= 0:
            raise ValueError("clip_norm must be positive and finite")

        old = [0.0] * self.hidden_size
        tape = []
        for symbol in context:
            x = float(symbol)
            hidden, recurrence, _ = self._step(x, old)
            tape.append((old, hidden, recurrence, x))
            old = hidden
        final_hidden = tape[-1][1]
        probability = _sigmoid(
            self.output_bias + sum(a * b for a, b in zip(self.output_weight, final_hidden))
        )
        y = float(target)
        p = min(max(probability, 1e-12), 1.0 - 1e-12)
        loss = -y * math.log(p) - (1.0 - y) * math.log(1.0 - p)

        names = ("raw_recurrence", "input_weight", "bias", "output_weight")
        grads = {name: [0.0] * self.hidden_size for name in names}
        dy = probability - y
        grad_output_bias = dy
        for i in range(self.hidden_size):
            grads["output_weight"][i] += dy * final_hidden[i]
        future = [0.0] * self.hidden_size
        for t in range(len(tape) - 1, -1, -1):
            previous, hidden, recurrence, x = tape[t]
            for i in range(self.hidden_size):
                dh = (dy * self.output_weight[i] if t == len(tape) - 1 else 0.0) + future[i]
                grads["raw_recurrence"][i] += (
                    dh * previous[i] * (1.0 - recurrence[i] ** 2)
                )
                grads["input_weight"][i] += dh * x
                grads["bias"][i] += dh
                future[i] = dh * recurrence[i]

        all_grads = [g for values in grads.values() for g in values] + [grad_output_bias]
        norm = math.sqrt(sum(g * g for g in all_grads))
        factor = min(1.0, clip_norm / max(norm, 1e-12))
        for name, values in grads.items():
            params = getattr(self, name)
            for i, grad in enumerate(values):
                params[i] -= learning_rate * factor * grad
        self.output_bias -= learning_rate * factor * grad_output_bias
        return loss

    def fit(
        self, sequences: Iterable[Sequence[int]], *, epochs: int = 1,
        learning_rate: float = 0.03,
    ) -> LinearTrainMetrics:
        rows = list(sequences)
        if not rows or not isinstance(epochs, int) or epochs < 1:
            raise ValueError("non-empty sequences and positive epochs are required")
        losses = [
            self.train_sequence(row, learning_rate=learning_rate)
            for _ in range(epochs) for row in rows
        ]
        return LinearTrainMetrics(sum(losses) / len(losses), len(rows), len(losses))
