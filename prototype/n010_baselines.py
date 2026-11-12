"""Parameter-matched nonlinear baselines for N0.10 Xiang experiments.

Pure Python reference implementations; intentionally small and deterministic.
The CP-style low-rank tensor baseline scores products of role-specific linear
projections. The MLP baseline operates on the concatenated role features.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable, Sequence

from prototype.n09_learnable_srok import LearnableSROKError, Node, RelationClassificationExample


def xiang_parameter_count(role_count: int, feature_dim: int, latent_dim: int) -> int:
    if any(isinstance(x, bool) or not isinstance(x, int) or x < 1
           for x in (role_count, feature_dim, latent_dim)):
        raise LearnableSROKError("role_count, feature_dim and latent_dim must be positive integers")
    interaction_blocks = role_count
    interaction_blocks += role_count * (role_count - 1) // 2
    interaction_blocks += role_count * (role_count - 1) * (role_count - 2) // 6
    return latent_dim * (feature_dim + 1 + interaction_blocks)


def mlp_parameter_count(role_count: int, feature_dim: int, hidden_dim: int) -> int:
    if any(isinstance(x, bool) or not isinstance(x, int) or x < 1
           for x in (role_count, feature_dim, hidden_dim)):
        raise LearnableSROKError("role_count, feature_dim and hidden_dim must be positive integers")
    input_dim = role_count * feature_dim
    return hidden_dim * (input_dim + 2) + 1


def low_rank_tensor_parameter_count(role_count: int, feature_dim: int, rank: int) -> int:
    if any(isinstance(x, bool) or not isinstance(x, int) or x < 1
           for x in (role_count, feature_dim, rank)):
        raise LearnableSROKError("role_count, feature_dim and rank must be positive integers")
    return rank * role_count * feature_dim + 1


def _nearest_integer_budget(target: int, count_fn, tolerance: float = 0.05) -> int:
    if isinstance(target, bool) or not isinstance(target, int) or target < 1:
        raise LearnableSROKError("target parameter count must be positive")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise LearnableSROKError("tolerance must be finite and non-negative")
    candidates = range(1, max(2, target * 2 + 2))
    best = min(candidates, key=lambda value: (abs(count_fn(value) - target), value))
    if abs(count_fn(best) - target) / target > tolerance:
        raise LearnableSROKError("no integer architecture meets parameter tolerance")
    return best


def match_mlp_hidden_dim(role_count: int, feature_dim: int, target: int,
                         tolerance: float = 0.05) -> int:
    return _nearest_integer_budget(
        target, lambda hidden: mlp_parameter_count(role_count, feature_dim, hidden),
        tolerance,
    )


def match_tensor_rank(role_count: int, feature_dim: int, target: int,
                      tolerance: float = 0.05) -> int:
    return _nearest_integer_budget(
        target, lambda rank: low_rank_tensor_parameter_count(role_count, feature_dim, rank),
        tolerance,
    )


@dataclass(frozen=True)
class BaselineConfig:
    seed: int = 0


class ParameterMatchedMLP:
    def __init__(self, role_count: int, feature_dim: int, hidden_dim: int,
                 config: BaselineConfig = BaselineConfig()):
        self.role_count, self.feature_dim, self.hidden_dim = role_count, feature_dim, hidden_dim
        if any(isinstance(x, bool) or not isinstance(x, int) or x < 1
               for x in (role_count, feature_dim, hidden_dim)):
            raise LearnableSROKError("MLP dimensions must be positive integers")
        if isinstance(config.seed, bool) or not isinstance(config.seed, int) or config.seed < 0:
            raise LearnableSROKError("seed must be a non-negative integer")
        self.config = config
        rng = random.Random(config.seed)
        d = role_count * feature_dim
        scale = 1.0 / math.sqrt(d)
        self.weights = [[rng.uniform(-scale, scale) for _ in range(d)]
                        for _ in range(hidden_dim)]
        self.hidden_bias = [0.0] * hidden_dim
        self.readout = [0.0] * hidden_dim
        self.output_bias = 0.0
        self.training_steps = 0

    @property
    def parameter_count(self) -> int:
        return mlp_parameter_count(self.role_count, self.feature_dim, self.hidden_dim)

    def _input(self, assignment: Sequence[Node]) -> list[float]:
        if len(assignment) != self.role_count:
            raise LearnableSROKError("MLP assignment role count mismatch")
        values = []
        for node in assignment:
            if not isinstance(node, Node) or len(node.features) != self.feature_dim:
                raise LearnableSROKError("invalid MLP node or feature dimension")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                   for v in node.features):
                raise LearnableSROKError("MLP features must be finite")
            values.extend(float(v) for v in node.features)
        return values

    @staticmethod
    def _sigmoid(value: float) -> float:
        if value >= 0:
            e = math.exp(-min(value, 60.0))
            return 1.0 / (1.0 + e)
        e = math.exp(max(value, -60.0))
        return e / (1.0 + e)

    def _forward(self, assignment):
        x = self._input(assignment)
        hidden = [math.tanh(math.fsum(w * v for w, v in zip(row, x)) + b)
                  for row, b in zip(self.weights, self.hidden_bias)]
        logit = math.fsum(w * h for w, h in zip(self.readout, hidden)) + self.output_bias
        return logit, hidden, x

    def score(self, assignment: Sequence[Node]) -> float:
        return self._forward(assignment)[0]

    def predict_probability(self, assignment: Sequence[Node]) -> float:
        return self._sigmoid(self.score(assignment))

    def fit(self, examples: Iterable[RelationClassificationExample], *, epochs: int = 100,
            learning_rate: float = 0.03, l2: float = 1e-4) -> list[float]:
        rows = tuple(examples)
        if not rows or isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
            raise LearnableSROKError("MLP requires examples and positive epochs")
        if isinstance(learning_rate, bool) or not isinstance(learning_rate, (int, float)) or not math.isfinite(learning_rate) or learning_rate <= 0:
            raise LearnableSROKError("learning_rate must be finite and positive")
        if isinstance(l2, bool) or not isinstance(l2, (int, float)) or not math.isfinite(l2) or l2 < 0:
            raise LearnableSROKError("l2 must be finite and non-negative")
        prepared = []
        for row in rows:
            if not isinstance(row, RelationClassificationExample) or type(row.label) is not int or row.label not in (-1, 1):
                raise LearnableSROKError("invalid MLP training row")
            prepared.append((self._input(row.assignment), 1.0 if row.label == 1 else 0.0))
        n, hdim, ddim = len(prepared), self.hidden_dim, self.role_count * self.feature_dim
        history = []
        for _ in range(epochs):
            gw = [[0.0] * ddim for _ in range(hdim)]
            gb = [0.0] * hdim
            gr = [0.0] * hdim
            go = 0.0
            loss = 0.0
            for x, target in prepared:
                hidden = [math.tanh(math.fsum(w * v for w, v in zip(row, x)) + b)
                          for row, b in zip(self.weights, self.hidden_bias)]
                logit = math.fsum(w * v for w, v in zip(self.readout, hidden)) + self.output_bias
                p = self._sigmoid(logit)
                pc = min(max(p, 1e-15), 1 - 1e-15)
                loss -= target * math.log(pc) + (1 - target) * math.log(1 - pc)
                error = p - target
                go += error
                for h in range(hdim):
                    gr[h] += error * hidden[h]
                    delta = error * self.readout[h] * (1 - hidden[h] ** 2)
                    gb[h] += delta
                    for d in range(ddim):
                        gw[h][d] += delta * x[d]
            self.output_bias -= learning_rate * go / n
            for h in range(hdim):
                self.readout[h] -= learning_rate * (gr[h] / n + l2 * self.readout[h])
                self.hidden_bias[h] -= learning_rate * gb[h] / n
                for d in range(ddim):
                    self.weights[h][d] -= learning_rate * (gw[h][d] / n + l2 * self.weights[h][d])
            history.append(loss / n)
            self.training_steps += 1
        return history


class ParameterMatchedLowRankTensor:
    """CP-style rank-K multiplicative tensor over role-specific projections."""
    def __init__(self, role_count: int, feature_dim: int, rank: int,
                 config: BaselineConfig = BaselineConfig()):
        self.role_count, self.feature_dim, self.rank = role_count, feature_dim, rank
        if any(isinstance(x, bool) or not isinstance(x, int) or x < 1
               for x in (role_count, feature_dim, rank)):
            raise LearnableSROKError("tensor dimensions must be positive integers")
        if isinstance(config.seed, bool) or not isinstance(config.seed, int) or config.seed < 0:
            raise LearnableSROKError("seed must be a non-negative integer")
        self.config = config
        rng = random.Random(config.seed)
        scale = 1.0 / math.sqrt(feature_dim)
        self.factors = [[[rng.uniform(-scale, scale) for _ in range(feature_dim)]
                         for _ in range(role_count)] for _ in range(rank)]
        self.coefficients = [0.0] * rank
        self.bias = 0.0
        self.training_steps = 0

    @property
    def parameter_count(self) -> int:
        return low_rank_tensor_parameter_count(self.role_count, self.feature_dim, self.rank)

    def _validate(self, assignment: Sequence[Node]) -> None:
        if len(assignment) != self.role_count:
            raise LearnableSROKError("tensor assignment role count mismatch")
        for node in assignment:
            if not isinstance(node, Node) or len(node.features) != self.feature_dim:
                raise LearnableSROKError("invalid tensor node or feature dimension")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                   for v in node.features):
                raise LearnableSROKError("tensor features must be finite")

    def _forward(self, assignment):
        self._validate(assignment)
        projections = [[math.fsum(w * x for w, x in zip(self.factors[k][r], node.features))
                        for r, node in enumerate(assignment)] for k in range(self.rank)]
        products = [math.prod(row) for row in projections]
        return self.bias + math.fsum(a * p for a, p in zip(self.coefficients, products)), projections, products

    def score(self, assignment: Sequence[Node]) -> float:
        return self._forward(assignment)[0]

    def predict_probability(self, assignment: Sequence[Node]) -> float:
        value = self.score(assignment)
        if value >= 0:
            e = math.exp(-min(value, 60.0))
            return 1 / (1 + e)
        e = math.exp(max(value, -60.0))
        return e / (1 + e)

    def fit(self, examples: Iterable[RelationClassificationExample], *, epochs: int = 100,
            learning_rate: float = 0.03, l2: float = 1e-4) -> list[float]:
        rows = tuple(examples)
        if not rows or isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
            raise LearnableSROKError("tensor baseline requires examples and positive epochs")
        if isinstance(learning_rate, bool) or not isinstance(learning_rate, (int, float)) or not math.isfinite(learning_rate) or learning_rate <= 0:
            raise LearnableSROKError("learning_rate must be finite and positive")
        if isinstance(l2, bool) or not isinstance(l2, (int, float)) or not math.isfinite(l2) or l2 < 0:
            raise LearnableSROKError("l2 must be finite and non-negative")
        prepared = []
        for row in rows:
            if not isinstance(row, RelationClassificationExample) or type(row.label) is not int or row.label not in (-1, 1):
                raise LearnableSROKError("invalid tensor training row")
            self._validate(row.assignment)
            prepared.append((row.assignment, 1.0 if row.label == 1 else 0.0))
        n = len(prepared)
        history = []
        for _ in range(epochs):
            gf = [[[0.0] * self.feature_dim for _ in range(self.role_count)]
                  for _ in range(self.rank)]
            gc = [0.0] * self.rank
            gb = 0.0
            loss = 0.0
            for assignment, target in prepared:
                logit, projections, products = self._forward(assignment)
                p = self.predict_probability(assignment)
                pc = min(max(p, 1e-15), 1 - 1e-15)
                loss -= target * math.log(pc) + (1 - target) * math.log(1 - pc)
                error = p - target
                gb += error
                for k in range(self.rank):
                    gc[k] += error * products[k]
                    for role in range(self.role_count):
                        other = math.prod(projections[k][j] for j in range(self.role_count) if j != role)
                        for f, value in enumerate(assignment[role].features):
                            gf[k][role][f] += error * self.coefficients[k] * other * value
            self.bias -= learning_rate * gb / n
            for k in range(self.rank):
                self.coefficients[k] -= learning_rate * (gc[k] / n + l2 * self.coefficients[k])
                for role in range(self.role_count):
                    for f in range(self.feature_dim):
                        self.factors[k][role][f] -= learning_rate * (
                            gf[k][role][f] / n + l2 * self.factors[k][role][f])
            history.append(loss / n)
            self.training_steps += 1
        return history
