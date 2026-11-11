"""E12-A19-C: deterministic multi-rule joint inference and a matched null control.

Candidate proposal and feature extraction reuse A19. Rule ranking and model fitting
use training labels only; validation labels are read only by the final scorer.
The randomized-feature control preserves each rule's activation count per split.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable

from prototype.e12a19_unified_structure_competition import (
    Budget, Example, SplitManifest, _build_feature_index, _candidate_stream,
    _matches,
)


@dataclass(frozen=True)
class JointBudget:
    max_candidates: int = 500
    max_rules: int = 8
    gradient_steps: int = 300
    learning_rate: float = 0.15
    l2: float = 0.02
    alpha: float = 0.5
    seed: int = 17

    def __post_init__(self):
        for name in ("max_candidates", "max_rules", "gradient_steps"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(name + " must be a positive integer")
        for name in ("learning_rate", "alpha"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(name + " must be finite and positive")
        if isinstance(self.l2, bool) or not isinstance(self.l2, (int, float)) or not math.isfinite(self.l2) or self.l2 < 0:
            raise ValueError("l2 must be finite and non-negative")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")


@dataclass(frozen=True)
class Score:
    log_loss: float
    accuracy: float
    brier_score: float


@dataclass(frozen=True)
class JointResult:
    split_digest: str
    candidate_count: int
    selected_rule_keys: tuple[str, ...]
    baseline: Score
    single_rule: Score
    joint_model: Score
    randomized_control: Score
    fitted_weights: tuple[tuple[float, ...], ...]
    randomized_weights: tuple[tuple[float, ...], ...]
    train_only_fit_digest: str


def _softmax(logits):
    peak = max(logits)
    exps = [math.exp(max(-700.0, x - peak)) for x in logits]
    total = math.fsum(exps)
    return [x / total for x in exps]


def _fit(x, y, classes, cfg):
    """Fixed-step multinomial logistic fit; never receives validation labels."""
    counts = [y.count(c) for c in classes]
    bias = [math.log((n + cfg.alpha) / (len(y) + cfg.alpha * len(classes))) for n in counts]
    weights = [[0.0 for _ in range(len(x[0]))] for _ in classes]
    for _ in range(cfg.gradient_steps):
        grad_b = [0.0] * len(classes)
        grad_w = [[0.0 for _ in range(len(x[0]))] for _ in classes]
        for row, target in zip(x, y):
            probs = _softmax([bias[k] + math.fsum(weights[k][j] * row[j] for j in range(len(row)))
                              for k in range(len(classes))])
            for k, cls in enumerate(classes):
                error = probs[k] - float(target == cls)
                grad_b[k] += error
                for j, value in enumerate(row):
                    grad_w[k][j] += error * value
        scale = 1.0 / len(y)
        for k in range(len(classes)):
            bias[k] -= cfg.learning_rate * grad_b[k] * scale
            for j in range(len(x[0])):
                grad_w[k][j] = grad_w[k][j] * scale + cfg.l2 * weights[k][j]
                weights[k][j] -= cfg.learning_rate * grad_w[k][j]
    return tuple(bias), tuple(tuple(row) for row in weights)


def _predict(x, params):
    bias, weights = params
    return [_softmax([bias[k] + math.fsum(weights[k][j] * row[j] for j in range(len(row)))
                      for k in range(len(bias))]) for row in x]


def _score(y, probs, classes):
    losses, correct, briers = [], 0, []
    for target, p in zip(y, probs):
        losses.append(-math.log(max(p[classes.index(target)], 1e-15)))
        correct += int(classes[max(range(len(p)), key=lambda i: p[i])] == target)
        briers.append(math.fsum((p[i] - float(target == cls)) ** 2 for i, cls in enumerate(classes)))
    return Score(math.fsum(losses) / len(y), correct / len(y), math.fsum(briers) / len(y))


def _mi_rank(column, labels, classes):
    """Training-only empirical mutual information in nats."""
    n = len(labels)
    joint = {}
    for active, label in zip(column, labels):
        joint[(active, label)] = joint.get((active, label), 0) + 1
    p_active = sum(column) / n
    p_inactive = 1.0 - p_active
    score = 0.0
    for active in (0, 1):
        pa = p_active if active else p_inactive
        if pa == 0:
            continue
        for cls in classes:
            count = joint.get((active, cls), 0)
            if not count:
                continue
            pj = count / n
            pc = labels.count(cls) / n
            score += pj * math.log(pj / (pa * pc))
    return score


def _matrix(rows, candidates, features):
    return [[int(_matches(features[row.observation_id], candidate)) for candidate in candidates]
            for row in rows]


def _permuted(matrix, seed):
    """Independently permute each feature column, preserving split-wise prevalence."""
    rng = random.Random(seed)
    if not matrix:
        return []
    columns = list(zip(*matrix))
    shuffled = []
    for column in columns:
        values = list(column)
        rng.shuffle(values)
        shuffled.append(values)
    return [list(row) for row in zip(*shuffled)] if shuffled else [[] for _ in matrix]


def run_joint(train_examples: Iterable[Example], validation_examples: Iterable[Example],
              manifest: SplitManifest, *, structure_budget: Budget = Budget(),
              budget: JointBudget = JointBudget()) -> JointResult:
    train = tuple(sorted(train_examples, key=lambda row: row.observation_id))
    validation = tuple(sorted(validation_examples, key=lambda row: row.observation_id))
    if not train or not validation:
        raise ValueError("train and validation must be non-empty")
    if len({r.observation_id for r in train}) != len(train) or len({r.observation_id for r in validation}) != len(validation):
        raise ValueError("duplicate observation IDs")
    if tuple(sorted(r.observation_id for r in train)) != manifest.train_ids:
        raise ValueError("training IDs do not match manifest")
    if tuple(sorted(r.observation_id for r in validation)) != manifest.validation_ids:
        raise ValueError("validation IDs do not match manifest")
    if set(r.observation_id for r in train + validation) & set(manifest.locked_test_ids):
        raise ValueError("locked-test ID leaked")
    classes = manifest.outcome_vocabulary
    if any(r.outcome not in classes for r in train + validation):
        raise ValueError("outcome outside manifest vocabulary")

    features, _ = _build_feature_index(train + validation, structure_budget)
    candidates = []
    for family in ("SPARSE_CONJUNCTION", "TYPED_PATH", "FORK_JOIN"):
        candidates.extend(list(__import__("itertools").islice(
            _candidate_stream(family, train, features, structure_budget), budget.max_candidates + 1)))
    candidates = candidates[:budget.max_candidates]
    if not candidates:
        raise ValueError("no candidate rules available")
    x_train_all = _matrix(train, candidates, features)
    x_valid_all = _matrix(validation, candidates, features)
    y_train = [r.outcome for r in train]
    y_valid = [r.outcome for r in validation]

    ranking = sorted(range(len(candidates)),
                     key=lambda j: (-_mi_rank([row[j] for row in x_train_all], y_train, classes),
                                    candidates[j].key))
    selected_idx = ranking[:min(budget.max_rules, len(ranking))]
    selected = [candidates[j] for j in selected_idx]
    x_train = [[row[j] for j in selected_idx] for row in x_train_all]
    x_valid = [[row[j] for j in selected_idx] for row in x_valid_all]
    params = _fit(x_train, y_train, classes, budget)
    joint = _score(y_valid, _predict(x_valid, params), classes)

    single_params = _fit([[row[0]] for row in x_train], y_train, classes, budget)
    single = _score(y_valid, _predict([[row[0]] for row in x_valid], single_params), classes)

    prior = [((y_train.count(c) + budget.alpha) /
              (len(y_train) + budget.alpha * len(classes))) for c in classes]
    baseline = _score(y_valid, [prior[:] for _ in y_valid], classes)

    null_train = _permuted(x_train, budget.seed)
    null_valid = _permuted(x_valid, budget.seed ^ 0x5A17)
    null_params = _fit(null_train, y_train, classes, budget)
    null_score = _score(y_valid, _predict(null_valid, null_params), classes)

    import hashlib
    import json
    fit_payload = {"classes": classes, "keys": [c.key for c in selected],
                   "weights": params[1], "bias": params[0], "steps": budget.gradient_steps,
                   "learning_rate": budget.learning_rate, "l2": budget.l2}
    fit_digest = hashlib.sha256(json.dumps(fit_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return JointResult(manifest.digest, len(candidates), tuple(c.key for c in selected),
                       baseline, single, joint, null_score, params[1], null_params[1], fit_digest)
