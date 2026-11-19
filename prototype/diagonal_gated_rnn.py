"""Trainable diagonal gated recurrent baseline (pure Python, no ML framework).

This is a deliberately small P5-B reference model, not a language model or a
claim of million-token capability. It predicts the next binary symbol and
supports explicit state carry across input chunks.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable, Sequence


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _vector(values: Sequence[float], size: int, name: str) -> list[float]:
    if len(values) != size:
        raise ValueError(f"{name} must have length {size}")
    result = [float(v) for v in values]
    if not all(math.isfinite(v) for v in result):
        raise ValueError(f"{name} must contain finite values")
    return result


@dataclass
class RecurrentState:
    hidden: list[float]


@dataclass(frozen=True)
class TrainMetrics:
    mean_loss: float
    examples: int
    updates: int


class DiagonalGatedRNN:
    """A diagonal gated recurrence with manual truncated-BPTT updates.

    For each dimension:
      candidate = tanh(wx*x + wh*h_prev + b)
      gate = sigmoid(ux*x + uh*h_prev + c)
      h = gate*candidate + (1-gate)*h_prev
    A shared logistic head predicts the next binary symbol.
    """

    def __init__(self, hidden_size: int = 16, seed: int = 7) -> None:
        if not isinstance(hidden_size, int) or hidden_size < 1:
            raise ValueError("hidden_size must be a positive integer")
        self.hidden_size = hidden_size
        rng = random.Random(seed)
        scale = 1.0 / math.sqrt(hidden_size)
        self.wx = [rng.uniform(-scale, scale) for _ in range(hidden_size)]
        self.wh = [rng.uniform(-scale, scale) for _ in range(hidden_size)]
        self.b = [0.0] * hidden_size
        self.ux = [rng.uniform(-scale, scale) for _ in range(hidden_size)]
        self.uh = [rng.uniform(-scale, scale) for _ in range(hidden_size)]
        self.c = [0.0] * hidden_size
        self.v = [rng.uniform(-scale, scale) for _ in range(hidden_size)]
        self.d = 0.0

    def zero_state(self) -> RecurrentState:
        return RecurrentState([0.0] * self.hidden_size)

    def _step(self, x: float, previous: Sequence[float]):
        if x not in (0, 1, 0.0, 1.0):
            raise ValueError("input symbols must be binary 0 or 1")
        candidate, gate, hidden = [], [], []
        for i, old in enumerate(previous):
            a = self.wx[i] * x + self.wh[i] * old + self.b[i]
            q = self.ux[i] * x + self.uh[i] * old + self.c[i]
            cand, z = math.tanh(a), _sigmoid(q)
            candidate.append(cand)
            gate.append(z)
            hidden.append(z * cand + (1.0 - z) * old)
        logit = self.d + sum(a * b for a, b in zip(self.v, hidden))
        return hidden, candidate, gate, _sigmoid(logit)

    def predict_chunk(
        self, symbols: Sequence[int], state: RecurrentState | None = None
    ) -> tuple[list[float], RecurrentState]:
        current = self.zero_state() if state is None else RecurrentState(
            _vector(state.hidden, self.hidden_size, "state.hidden")
        )
        predictions = []
        for symbol in symbols:
            hidden, _, _, probability = self._step(float(symbol), current.hidden)
            predictions.append(probability)
            current = RecurrentState(hidden)
        return predictions, current

    def train_sequence(
        self, symbols: Sequence[int], *, learning_rate: float = 0.03,
        clip_norm: float = 1.0,
    ) -> float:
        """Train next-symbol prediction on one sequence using full BPTT."""
        if len(symbols) < 2:
            raise ValueError("training sequence must contain at least two symbols")
        if any(x not in (0, 1) for x in symbols):
            raise ValueError("training symbols must be binary")
        if not math.isfinite(learning_rate) or learning_rate <= 0:
            raise ValueError("learning_rate must be positive and finite")
        if not math.isfinite(clip_norm) or clip_norm <= 0:
            raise ValueError("clip_norm must be positive and finite")

        hprev = [0.0] * self.hidden_size
        tape = []
        loss = 0.0
        for index, symbol in enumerate(symbols[:-1]):
            h, cand, gate, probability = self._step(float(symbol), hprev)
            target = float(symbols[index + 1])
            p = min(max(probability, 1e-12), 1.0 - 1e-12)
            loss -= target * math.log(p) + (1.0 - target) * math.log(1.0 - p)
            tape.append((hprev, h, cand, gate, probability, target))
            hprev = h

        grads = {name: [0.0] * self.hidden_size for name in
                 ("wx", "wh", "b", "ux", "uh", "c", "v")}
        grad_d = 0.0
        future = [0.0] * self.hidden_size
        for t in range(len(tape) - 1, -1, -1):
            old, h, cand, gate, probability, target = tape[t]
            x = float(symbols[t])
            dy = probability - target
            for i in range(self.hidden_size):
                dh = dy * self.v[i] + future[i]
                dz = dh * (cand[i] - old[i])
                dcand = dh * gate[i]
                da = dcand * (1.0 - cand[i] * cand[i])
                dq = dz * gate[i] * (1.0 - gate[i])
                grads["wx"][i] += da * x
                grads["wh"][i] += da * old[i]
                grads["b"][i] += da
                grads["ux"][i] += dq * x
                grads["uh"][i] += dq * old[i]
                grads["c"][i] += dq
                future[i] = dh * (1.0 - gate[i]) + da * self.wh[i] + dq * self.uh[i]

        all_grads = [g for values in grads.values() for g in values] + [grad_d]
        norm = math.sqrt(sum(g * g for g in all_grads))
        factor = min(1.0, clip_norm / max(norm, 1e-12))
        for name, values in grads.items():
            params = getattr(self, name)
            for i, grad in enumerate(values):
                params[i] -= learning_rate * factor * grad
        self.d -= learning_rate * factor * grad_d
        return loss / len(tape)

    def fit(
        self, sequences: Iterable[Sequence[int]], *, epochs: int = 1,
        learning_rate: float = 0.03,
    ) -> TrainMetrics:
        rows = list(sequences)
        if not rows:
            raise ValueError("sequences must not be empty")
        if not isinstance(epochs, int) or epochs < 1:
            raise ValueError("epochs must be a positive integer")
        total, updates = 0.0, 0
        for _ in range(epochs):
            for row in rows:
                total += self.train_sequence(row, learning_rate=learning_rate)
                updates += 1
        return TrainMetrics(total / updates, len(rows), updates)
