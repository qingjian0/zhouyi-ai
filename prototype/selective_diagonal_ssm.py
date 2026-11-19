"""Minimal trainable input-selective diagonal state-space baseline for P5-B.

This pure-Python model is a mechanism baseline, not a production SSM or LM.
The discretization step depends on the current input symbol, while the state
transition remains diagonal and supports explicit chunk-state carry.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Sequence


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _softplus(x: float) -> float:
    if x > 30.0:
        return x
    if x < -30.0:
        return math.exp(x)
    return math.log1p(math.exp(x))


@dataclass
class SelectiveSSMState:
    hidden: list[float]


class SelectiveDiagonalSSM:
    """Diagonal recurrence with input-dependent discretization.

    For each channel:
      delta_t = softplus(delta_bias + x_t)
      decay_t = exp(-softplus(a_log) * delta_t)
      h_t = decay_t * h_(t-1) + input_weight * x_t
      p_t = sigmoid(output_bias + dot(output_weight, h_t))

    Parameters: a_log, delta_bias, input_weight, output_weight and output_bias.
    Thus parameter_count = 4 * hidden_size + 1.
    """

    def __init__(self, hidden_size: int = 7, seed: int = 17) -> None:
        if isinstance(hidden_size, bool) or not isinstance(hidden_size, int) or hidden_size < 1:
            raise ValueError("hidden_size must be a positive integer")
        self.hidden_size = hidden_size
        rng = random.Random(seed)
        scale = 1.0 / math.sqrt(hidden_size)
        self.a_log = [rng.uniform(-1.2, -0.6) for _ in range(hidden_size)]
        self.delta_bias = [rng.uniform(-0.8, -0.2) for _ in range(hidden_size)]
        self.input_weight = [rng.uniform(-scale, scale) for _ in range(hidden_size)]
        self.output_weight = [rng.uniform(-scale, scale) for _ in range(hidden_size)]
        self.output_bias = 0.0

    @property
    def parameter_count(self) -> int:
        return 4 * self.hidden_size + 1

    def zero_state(self) -> SelectiveSSMState:
        return SelectiveSSMState([0.0] * self.hidden_size)

    def _step(self, x: float, previous: Sequence[float]):
        hidden, decay, d_decay_da, d_decay_ddelta = [], [], [], []
        for i, old in enumerate(previous):
            a_rate = _softplus(self.a_log[i])
            delta_arg = self.delta_bias[i] + x
            delta = _softplus(delta_arg)
            alpha = math.exp(-a_rate * delta)
            hidden.append(alpha * old + self.input_weight[i] * x)
            decay.append(alpha)
            d_decay_da.append(-alpha * delta * _sigmoid(self.a_log[i]))
            d_decay_ddelta.append(-alpha * a_rate * _sigmoid(delta_arg))
        probability = _sigmoid(
            self.output_bias + sum(a * b for a, b in zip(self.output_weight, hidden))
        )
        return hidden, decay, d_decay_da, d_decay_ddelta, probability

    def predict_chunk(
        self, symbols: Sequence[int], state: SelectiveSSMState | None = None
    ) -> tuple[list[float], SelectiveSSMState]:
        current = self.zero_state() if state is None else SelectiveSSMState(
            [float(value) for value in state.hidden]
        )
        if len(current.hidden) != self.hidden_size or not all(
            math.isfinite(value) for value in current.hidden
        ):
            raise ValueError("state.hidden must contain finite values of hidden_size")
        predictions = []
        for symbol in symbols:
            if symbol not in (0, 1):
                raise ValueError("input symbols must be binary 0 or 1")
            hidden, _, _, _, probability = self._step(float(symbol), current.hidden)
            predictions.append(probability)
            current = SelectiveSSMState(hidden)
        return predictions, current

    def train_final_target(
        self, context: Sequence[int], target: int, *,
        learning_rate: float = 0.03, clip_norm: float = 1.0,
    ) -> float:
        if not context or any(value not in (0, 1) for value in context) or target not in (0, 1):
            raise ValueError("context must be non-empty binary data and target must be binary")
        if not math.isfinite(learning_rate) or learning_rate <= 0:
            raise ValueError("learning_rate must be positive and finite")
        if not math.isfinite(clip_norm) or clip_norm <= 0:
            raise ValueError("clip_norm must be positive and finite")

        old = [0.0] * self.hidden_size
        tape = []
        for symbol in context:
            x = float(symbol)
            hidden, decay, d_da, d_ddelta, _ = self._step(x, old)
            tape.append((old, hidden, decay, d_da, d_ddelta, x))
            old = hidden

        final_hidden = tape[-1][1]
        probability = _sigmoid(
            self.output_bias + sum(a * b for a, b in zip(self.output_weight, final_hidden))
        )
        y = float(target)
        p = min(max(probability, 1e-12), 1.0 - 1e-12)
        loss = -y * math.log(p) - (1.0 - y) * math.log(1.0 - p)

        grads = {
            name: [0.0] * self.hidden_size
            for name in ("a_log", "delta_bias", "input_weight", "output_weight")
        }
        dy = probability - y
        grad_output_bias = dy
        for i in range(self.hidden_size):
            grads["output_weight"][i] = dy * final_hidden[i]

        future = [0.0] * self.hidden_size
        for t in range(len(tape) - 1, -1, -1):
            previous, hidden, decay, d_da, d_ddelta, x = tape[t]
            for i in range(self.hidden_size):
                dh = (dy * self.output_weight[i] if t == len(tape) - 1 else 0.0) + future[i]
                d_old_path = dh * previous[i]
                grads["a_log"][i] += d_old_path * d_da[i]
                grads["delta_bias"][i] += d_old_path * d_ddelta[i]
                grads["input_weight"][i] += dh * x
                future[i] = dh * decay[i]

        all_grads = [value for values in grads.values() for value in values] + [grad_output_bias]
        norm = math.sqrt(sum(value * value for value in all_grads))
        factor = min(1.0, clip_norm / max(norm, 1e-12))
        for name, values in grads.items():
            params = getattr(self, name)
            for index, grad in enumerate(values):
                params[index] -= learning_rate * factor * grad
        self.output_bias -= learning_rate * factor * grad_output_bias
        return loss
