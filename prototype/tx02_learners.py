"""TX-02B-3/02C set-conditioned relation learner.

A small pure-Python MLP scores each (support triple, query, candidate) tuple.
Scores are pooled over the support set, then normalized across the shuffled
candidate row. Fixed codebooks isolate representation geometry; LEARNED uses
a trainable symbol embedding table updated by cross-entropy gradients.

This is an experimental baseline, not evidence of representation superiority.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable

from prototype.tx02_splits import EvaluationEpisode, LearnerInput, SupervisedEpisode
from prototype.tx02_state_encoders import build_codebook


@dataclass(frozen=True)
class FitReport:
    epochs_completed: int
    training_loss: float
    validation_accuracy: float | None
    parameter_count: int
    updates: int


class SetConditionedMLPLearner:
    """Permutation-invariant support-set scorer with a trainable MLP."""

    def __init__(
        self,
        family: str = "ONE_HOT",
        hidden_size: int = 24,
        embedding_dim: int = 6,
        learning_rate: float = 0.03,
        seed: int = 0,
    ) -> None:
        if family not in ("BINARY", "TERNARY", "HYBRID", "ONE_HOT", "LEARNED", "FIXED_RANDOM", "PERMUTED"):
            raise ValueError("unknown representation family")
        if type(hidden_size) is not int or hidden_size < 1:
            raise ValueError("hidden_size must be a positive integer")
        if type(embedding_dim) is not int or embedding_dim < 1:
            raise ValueError("embedding_dim must be a positive integer")
        if not math.isfinite(learning_rate) or learning_rate <= 0:
            raise ValueError("learning_rate must be positive and finite")
        self.family = family
        self.hidden_size = hidden_size
        self.embedding_dim = embedding_dim
        self.learning_rate = learning_rate
        self.seed = seed
        self._rng = random.Random(seed)
        self._cardinality: int | None = None
        self._codewords: tuple[tuple[float, ...], ...] | None = None
        self._embeddings: list[list[float]] | None = None
        self._trainable_embeddings = family == "LEARNED"
        self._w1: list[list[float]] = []
        self._b1: list[float] = []
        self._w2: list[float] = []
        self._b2 = 0.0
        self._updates = 0
        self._fitted = False

    def _initialize(self, cardinality: int) -> None:
        if self._cardinality is not None:
            if cardinality != self._cardinality:
                raise ValueError("one learner instance supports exactly one cardinality")
            return
        self._cardinality = cardinality
        if self.family in ("LEARNED", "FIXED_RANDOM"):
            d = self.embedding_dim
            scale = 1.0 / math.sqrt(d)
            table = tuple(
                tuple(self._rng.uniform(-scale, scale) for _ in range(d))
                for _ in range(cardinality)
            )
            if self.family == "LEARNED":
                self._embeddings = [list(row) for row in table]
                self._codewords = None
            else:
                self._embeddings = None
                self._codewords = table
            feature_dim = d
        else:
            code_family = "PERMUTED" if self.family == "PERMUTED" else self.family
            codebook = build_codebook(cardinality, code_family, self.seed)
            self._codewords = codebook.codewords
            feature_dim = codebook.dimension
        input_dim = feature_dim * 6
        scale = 1.0 / math.sqrt(input_dim)
        self._w1 = [
            [self._rng.uniform(-scale, scale) for _ in range(input_dim)]
            for _ in range(self.hidden_size)
        ]
        self._b1 = [0.0] * self.hidden_size
        self._w2 = [self._rng.uniform(-1.0 / math.sqrt(self.hidden_size),
                                      1.0 / math.sqrt(self.hidden_size))
                    for _ in range(self.hidden_size)]
        self._b2 = 0.0

    @property
    def parameter_count(self) -> int:
        embedding_count = (
            self._cardinality * self.embedding_dim if self._trainable_embeddings and self._cardinality
            else 0
        )
        input_dim = len(self._w1[0]) if self._w1 else 0
        return embedding_count + self.hidden_size * input_dim + self.hidden_size + self.hidden_size + 1

    def _encode(self, symbol: int) -> tuple[float, ...]:
        if self._cardinality is None or type(symbol) is not int or not 0 <= symbol < self._cardinality:
            raise ValueError("symbol outside learner cardinality")
        if self._trainable_embeddings:
            assert self._embeddings is not None
            return tuple(self._embeddings[symbol])
        assert self._codewords is not None
        return self._codewords[symbol]

    def _features(self, support_row: tuple[int, int, int],
                  query: tuple[int, int], candidate: int) -> tuple[list[float], tuple[int, ...]]:
        symbols = (support_row[0], support_row[1], support_row[2],
                   query[0], query[1], candidate)
        vectors = [self._encode(s) for s in symbols]
        return [v for vector in vectors for v in vector], symbols

    def _row_score(self, features: list[float]) -> tuple[float, list[float]]:
        hidden = []
        for weights, bias in zip(self._w1, self._b1):
            z = bias + sum(w * x for w, x in zip(weights, features))
            hidden.append(math.tanh(z))
        score = self._b2 + sum(w * h for w, h in zip(self._w2, hidden))
        return score, hidden

    def predict_scores(self, episode: LearnerInput, query_index: int) -> tuple[float, ...]:
        self._initialize(episode.cardinality)
        if not episode.support:
            raise ValueError("support must not be empty")
        if not 0 <= query_index < len(episode.queries):
            raise IndexError("query_index out of range")
        query = episode.queries[query_index]
        candidates = episode.candidates[query_index]
        scores = []
        for candidate in candidates:
            total = 0.0
            for support_row in episode.support:
                features, _ = self._features(support_row, query, candidate)
                score, _ = self._row_score(features)
                total += score
            scores.append(total / len(episode.support))
        return tuple(scores)

    def predict_proba(self, episode: LearnerInput, query_index: int) -> tuple[float, ...]:
        scores = self.predict_scores(episode, query_index)
        peak = max(scores)
        exps = [math.exp(max(-60.0, min(60.0, score - peak))) for score in scores]
        total = sum(exps)
        return tuple(value / total for value in exps)

    def predict(self, episode: LearnerInput) -> tuple[int, ...]:
        return tuple(
            max(range(len(row)), key=lambda i: row[i])
            for row in (self.predict_proba(episode, qi) for qi in range(len(episode.queries)))
        )

    def _train_query(self, episode: LearnerInput, query_index: int, target: int) -> float:
        self._initialize(episode.cardinality)
        if not 0 <= target < len(episode.candidates[query_index]):
            raise ValueError("target must index the shuffled candidate row")
        support_count = len(episode.support)
        if support_count == 0:
            raise ValueError("support must not be empty")
        query = episode.queries[query_index]
        candidates = episode.candidates[query_index]
        caches = []
        scores = []
        for candidate in candidates:
            candidate_cache = []
            total = 0.0
            for support_row in episode.support:
                features, symbols = self._features(support_row, query, candidate)
                score, hidden = self._row_score(features)
                total += score
                candidate_cache.append((features, symbols, hidden))
            scores.append(total / support_count)
            caches.append(candidate_cache)

        peak = max(scores)
        exp_scores = [math.exp(max(-60.0, min(60.0, value - peak))) for value in scores]
        denominator = sum(exp_scores)
        probabilities = [value / denominator for value in exp_scores]
        loss = -math.log(max(probabilities[target], 1e-15))

        gw1 = [[0.0] * len(self._w1[0]) for _ in self._w1]
        gb1 = [0.0] * self.hidden_size
        gw2 = [0.0] * self.hidden_size
        gb2 = 0.0
        embedding_grads = (
            [[0.0] * self.embedding_dim for _ in range(self._cardinality or 0)]
            if self._trainable_embeddings else None
        )

        for ci, candidate_cache in enumerate(caches):
            dscore = probabilities[ci] - (1.0 if ci == target else 0.0)
            dscore /= support_count
            for features, symbols, hidden in candidate_cache:
                for h in range(self.hidden_size):
                    gw2[h] += dscore * hidden[h]
                gb2 += dscore
                for h in range(self.hidden_size):
                    dz = dscore * self._w2[h] * (1.0 - hidden[h] * hidden[h])
                    gb1[h] += dz
                    for j, value in enumerate(features):
                        gw1[h][j] += dz * value
                    if embedding_grads is not None:
                        dfeature = [dz * self._w1[h][j] for j in range(len(features))]
                        d = self.embedding_dim
                        for slot, symbol in enumerate(symbols):
                            offset = slot * d
                            for component in range(d):
                                embedding_grads[symbol][component] += dfeature[offset + component]

        lr = self.learning_rate
        for h in range(self.hidden_size):
            self._w2[h] -= lr * gw2[h]
            self._b1[h] -= lr * gb1[h]
            for j in range(len(self._w1[h])):
                self._w1[h][j] -= lr * gw1[h][j]
        self._b2 -= lr * gb2
        if embedding_grads is not None and self._embeddings is not None:
            for symbol in range(len(self._embeddings)):
                for j in range(self.embedding_dim):
                    self._embeddings[symbol][j] -= lr * embedding_grads[symbol][j]
        self._updates += 1
        return loss

    def _mean_loss(self, episodes: Iterable[SupervisedEpisode | EvaluationEpisode],
                   labels_available: bool) -> float | None:
        losses = []
        for item in episodes:
            for qi, target in enumerate(item.targets):
                probs = self.predict_proba(item.inputs, qi)
                losses.append(-math.log(max(probs[target], 1e-15)))
        return sum(losses) / len(losses) if losses else None

    def _accuracy(self, episodes: Iterable[EvaluationEpisode]) -> float | None:
        correct = total = 0
        for item in episodes:
            predictions = self.predict(item.inputs)
            for prediction, target in zip(predictions, item.targets):
                correct += int(prediction == target)
                total += 1
        return correct / total if total else None

    def fit(
        self,
        train_episodes: Iterable[SupervisedEpisode],
        validation_episodes: Iterable[EvaluationEpisode] = (),
        budget: dict | None = None,
        seed: int | None = None,
    ) -> FitReport:
        rows = tuple(train_episodes)
        if not rows:
            raise ValueError("train_episodes must not be empty")
        if seed is not None and seed != self.seed:
            # Reproducibility requires reseeding before lazy initialization.
            if self._cardinality is not None:
                raise ValueError("seed cannot change after learner initialization")
            self.seed = seed
            self._rng = random.Random(seed)
        budget = dict(budget or {})
        epochs = budget.get("epochs", 5)
        if type(epochs) is not int or epochs < 1:
            raise ValueError("budget.epochs must be a positive integer")
        validation = tuple(validation_episodes)
        self._initialize(rows[0].inputs.cardinality)
        losses = []
        completed = 0
        for _ in range(epochs):
            order = list(rows)
            self._rng.shuffle(order)
            epoch_losses = []
            for item in order:
                for qi, target in enumerate(item.targets):
                    epoch_losses.append(self._train_query(item.inputs, qi, target))
            losses.append(sum(epoch_losses) / len(epoch_losses))
            completed += 1
        self._fitted = True
        return FitReport(
            epochs_completed=completed,
            training_loss=losses[-1],
            validation_accuracy=self._accuracy(validation) if validation else None,
            parameter_count=self.parameter_count,
            updates=self._updates,
        )

    def metadata(self) -> dict:
        return {
            "family": self.family,
            "cardinality": self._cardinality,
            "hidden_size": self.hidden_size,
            "embedding_dim": self.embedding_dim if self.family in ("LEARNED", "FIXED_RANDOM") else None,
            "trainable_embedding": self._trainable_embeddings,
            "parameter_count": self.parameter_count,
            "updates": self._updates,
            "seed": self.seed,
            "fitted": self._fitted,
        }
