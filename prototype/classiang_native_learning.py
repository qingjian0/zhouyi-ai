"""Trainable, backend-neutral scorer for native classiang compositions.

This is a small, auditable learning component over explicit symbol/relation
graphs. It is not a language model, perception model, or foundation model.
Labels must be reviewed and evidence-bound. The scorer ranks candidate
structures; it does not establish semantic or causal truth.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Sequence

from prototype.classiang_native import Composition, Relation, SymbolGraph, compose_relations

FEATURE_NAMES = (
    "depth",
    "shared_symbol_ratio",
    "relation_type_diversity",
    "condition_overlap",
    "evidence_coverage",
)
MODEL_TYPE = "classiang-composition-logistic-v1"


@dataclass(frozen=True)
class CompositionLabel:
    example_id: str
    group_id: str
    source_family: str
    relation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    label: int
    reviewed: bool

    def validate(self, graph: SymbolGraph) -> None:
        for name in ("example_id", "group_id", "source_family"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if not isinstance(self.relation_ids, tuple) or len(self.relation_ids) < 2:
            raise ValueError("relation_ids must contain at least two relation IDs")
        if any(not isinstance(v, str) or not v.strip() for v in self.relation_ids):
            raise ValueError("relation_ids must be non-empty strings")
        if len(set(self.relation_ids)) != len(self.relation_ids):
            raise ValueError("relation_ids must be unique")
        if not isinstance(self.evidence_ids, tuple) or not self.evidence_ids:
            raise ValueError("evidence_ids must be a non-empty tuple")
        if any(not isinstance(v, str) or not v.strip() for v in self.evidence_ids):
            raise ValueError("evidence_ids must be non-empty strings")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must be unique")
        if isinstance(self.label, bool) or self.label not in (0, 1):
            raise ValueError("label must be integer 0 or 1")
        if not isinstance(self.reviewed, bool) or not self.reviewed:
            raise ValueError("only reviewed labels may enter training")
        relation_map = {item.relation_id: item for item in graph.relations}
        evidence_map = {item.evidence_id: item for item in graph.evidence}
        if not set(self.relation_ids) <= set(relation_map):
            raise ValueError("label references unknown relation")
        if not set(self.evidence_ids) <= set(evidence_map):
            raise ValueError("label references unknown evidence")
        if any(not evidence_map[item].reviewed for item in self.evidence_ids):
            raise ValueError("label references unreviewed evidence")
        relation_evidence = set().union(*(set(relation_map[r].evidence_ids) for r in self.relation_ids))
        if not relation_evidence <= set(self.evidence_ids):
            raise ValueError("label evidence must cover all relation evidence")


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-min(value, 60.0))
        return 1.0 / (1.0 + z)
    z = math.exp(max(value, -60.0))
    return z / (1.0 + z)


def _features(graph: SymbolGraph, relation_ids: tuple[str, ...]) -> tuple[float, ...]:
    relation_map = {item.relation_id: item for item in graph.relations}
    selected = [relation_map[item] for item in relation_ids]
    symbol_sets = [{symbol for _, symbol in item.roles} for item in selected]
    union: set[str] = set()
    shared: set[str] = set()
    for current in symbol_sets:
        shared |= union & current
        union |= current
    types = {item.relation_type for item in selected}
    condition_sets = [set(item.conditions) for item in selected]
    common_conditions = set.intersection(*condition_sets) if condition_sets else set()
    evidence = set().union(*(set(item.evidence_ids) for item in selected))
    graph_evidence = {item.evidence_id for item in graph.evidence}
    return (
        float(len(selected)),
        len(shared) / max(1, len(union)),
        len(types) / max(1, len(selected)),
        len(common_conditions) / max(1, len(set().union(*condition_sets))),
        len(evidence) / max(1, len(graph_evidence)),
    )


@dataclass
class NativeCompositionScorer:
    weights: list[float]
    bias: float
    trained_examples: int = 0
    epochs: int = 0

    @classmethod
    def initialize(cls) -> "NativeCompositionScorer":
        return cls(weights=[0.0] * len(FEATURE_NAMES), bias=0.0)

    def predict_probability(self, features: Sequence[float]) -> float:
        if len(features) != len(self.weights):
            raise ValueError("feature dimension mismatch")
        return _sigmoid(self.bias + sum(w * x for w, x in zip(self.weights, features)))

    def fit(
        self,
        rows: Sequence[tuple[tuple[float, ...], int]],
        *,
        epochs: int = 100,
        learning_rate: float = 0.05,
        l2: float = 0.001,
        seed: int = 17,
    ) -> "NativeCompositionScorer":
        if not rows:
            raise ValueError("training rows must not be empty")
        if not any(label == 0 for _, label in rows) or not any(label == 1 for _, label in rows):
            raise ValueError("training requires both positive and negative reviewed labels")
        if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
            raise ValueError("epochs must be a positive integer")
        for name, value in (("learning_rate", learning_rate), ("l2", l2)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if learning_rate == 0:
            raise ValueError("learning_rate must be positive")
        rng = random.Random(seed)
        weights = [0.0] * len(FEATURE_NAMES)
        bias = 0.0
        for _ in range(epochs):
            order = list(range(len(rows)))
            rng.shuffle(order)
            for index in order:
                vector, label = rows[index]
                if len(vector) != len(FEATURE_NAMES) or any(not math.isfinite(x) for x in vector):
                    raise ValueError("invalid feature vector")
                probability = _sigmoid(bias + sum(w * x for w, x in zip(weights, vector)))
                error = probability - label
                for j, value in enumerate(vector):
                    weights[j] -= learning_rate * (error * value + l2 * weights[j])
                bias -= learning_rate * error
        self.weights, self.bias = weights, bias
        self.trained_examples = len(rows)
        self.epochs = epochs
        return self

    def score(self, graph: SymbolGraph, composition: Composition) -> float:
        return self.predict_probability(_features(graph, composition.relation_ids))

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "model_type": MODEL_TYPE,
            "feature_names": list(FEATURE_NAMES),
            "weights": self.weights,
            "bias": self.bias,
            "trained_examples": self.trained_examples,
            "epochs": self.epochs,
        }

    def save(self, path: str | Path) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(target)
        return hashlib.sha256(target.read_bytes()).hexdigest()

    @classmethod
    def load(cls, path: str | Path) -> "NativeCompositionScorer":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != 1 or data.get("model_type") != MODEL_TYPE:
            raise ValueError("unsupported checkpoint")
        if tuple(data.get("feature_names", ())) != FEATURE_NAMES:
            raise ValueError("checkpoint feature schema mismatch")
        weights = data.get("weights")
        bias = data.get("bias")
        if not isinstance(weights, list) or len(weights) != len(FEATURE_NAMES):
            raise ValueError("invalid checkpoint weights")
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in weights):
            raise ValueError("checkpoint weights must be finite numbers")
        if isinstance(bias, bool) or not isinstance(bias, (int, float)) or not math.isfinite(bias):
            raise ValueError("checkpoint bias must be finite")
        return cls(
            weights=[float(x) for x in weights], bias=float(bias),
            trained_examples=int(data.get("trained_examples", 0)),
            epochs=int(data.get("epochs", 0)),
        )


def _split_by_group(labels: Sequence[CompositionLabel], validation_fraction: float, seed: int):
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must be in (0, 1)")
    groups: dict[str, list[CompositionLabel]] = {}
    for row in labels:
        groups.setdefault(row.source_family, []).append(row)
    if len(groups) < 2:
        raise ValueError("at least two source families are required for leakage-safe evaluation")
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)
    target = max(1, min(len(keys) - 1, round(len(keys) * validation_fraction)))
    validation_keys = set(keys[:target])
    train = [row for key, values in groups.items() if key not in validation_keys for row in values]
    validation = [row for key, values in groups.items() if key in validation_keys for row in values]
    if not train or not validation:
        raise ValueError("group split produced an empty partition")
    return tuple(train), tuple(validation)


def train_and_evaluate(
    graph: SymbolGraph,
    labels: Sequence[CompositionLabel],
    *,
    seed: int = 17,
    epochs: int = 100,
    learning_rate: float = 0.05,
    validation_fraction: float = 0.2,
    threshold: float = 0.5,
) -> tuple[NativeCompositionScorer, dict]:
    graph.validate()
    if not isinstance(labels, Sequence) or not labels:
        raise ValueError("labels must be a non-empty sequence")
    for row in labels:
        if not isinstance(row, CompositionLabel):
            raise ValueError("labels must contain CompositionLabel")
        row.validate(graph)
    ids = [row.example_id for row in labels]
    if len(ids) != len(set(ids)):
        raise ValueError("example IDs must be unique")
    train, validation = _split_by_group(labels, validation_fraction, seed)
    def materialize(rows):
        return [
            (_features(graph, row.relation_ids), row.label)
            for row in rows
        ]

    model = NativeCompositionScorer.initialize().fit(
        materialize(train), epochs=epochs, learning_rate=learning_rate, seed=seed,
    )
    probs = [model.predict_probability(_features(graph, row.relation_ids)) for row in validation]
    truth = [row.label for row in validation]
    predictions = [int(p >= threshold) for p in probs]
    tp = sum(p == 1 and y == 1 for p, y in zip(predictions, truth))
    fp = sum(p == 1 and y == 0 for p, y in zip(predictions, truth))
    fn = sum(p == 0 and y == 1 for p, y in zip(predictions, truth))
    tn = sum(p == 0 and y == 0 for p, y in zip(predictions, truth))
    brier = sum((p - y) ** 2 for p, y in zip(probs, truth)) / len(truth)
    report = {
        "schema_version": 1,
        "model_type": MODEL_TYPE,
        "seed": seed,
        "epochs": epochs,
        "threshold": threshold,
        "train_examples": len(train),
        "validation_examples": len(validation),
        "train_source_families": sorted({r.source_family for r in train}),
        "validation_source_families": sorted({r.source_family for r in validation}),
        "source_family_disjoint": not ({r.source_family for r in train} & {r.source_family for r in validation}),
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "accuracy": (tp + tn) / len(truth),
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "brier_score": brier,
        "limitations": [
            "linear logistic scorer over five hand-defined structural features",
            "requires reviewed evidence-bound composition labels",
            "not a perception model or language model",
            "scores candidate structural compatibility, not semantic or causal truth",
            "evaluation is source-family holdout only; larger independent benchmarks remain required",
        ],
    }
    return model, report


def rank_compositions(
    graph: SymbolGraph,
    model: NativeCompositionScorer,
    *,
    max_depth: int = 3,
    max_candidates: int = 1000,
) -> tuple[tuple[float, Composition], ...]:
    result = compose_relations(
        graph, max_depth=max_depth, max_candidates=max_candidates,
    )
    return tuple(sorted(
        ((model.score(graph, candidate), candidate) for candidate in result.candidates),
        key=lambda item: (-item[0], item[1].relation_ids),
    ))


def labels_from_jsonl(path: str | Path) -> tuple[CompositionLabel, ...]:
    rows = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            rows.append(CompositionLabel(
                example_id=item["example_id"],
                group_id=item["group_id"],
                source_family=item["source_family"],
                relation_ids=tuple(item["relation_ids"]),
                evidence_ids=tuple(item["evidence_ids"]),
                label=item["label"],
                reviewed=item["reviewed"],
            ))
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid label JSONL at line {line_number}: {exc}") from exc
    return tuple(rows)
