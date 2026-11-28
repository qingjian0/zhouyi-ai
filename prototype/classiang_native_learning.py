"""Trainable, backend-neutral scorer for native classiang compositions.

This is a small, auditable learning component over explicit symbol/relation
graphs. It is not a language model, perception model, or foundation model.
Labels must be reviewed and evidence-bound. The scorer ranks candidate
structures; it does not establish semantic or causal truth.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Sequence

from prototype.classiang_native import (
    Composition, EvidenceRef, Relation, Symbol, SymbolGraph, compose_relations,
)

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
        if isinstance(self.label, bool) or not isinstance(self.label, int) or self.label not in (0, 1):
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
        evidence_families = {evidence_map[item].source_family for item in self.evidence_ids}
        if evidence_families != {self.source_family}:
            raise ValueError("label evidence must belong to exactly its declared source_family")
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
    return (
        float(len(selected)),
        len(shared) / max(1, len(union)),
        len(types) / max(1, len(selected)),
        len(common_conditions) / max(1, len(set().union(*condition_sets))),
        len(evidence) / max(1, sum(len(item.evidence_ids) for item in selected)),
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
    train_relation_ids = {rid for row in train for rid in row.relation_ids}
    validation_relation_ids = {rid for row in validation for rid in row.relation_ids}
    if train_relation_ids & validation_relation_ids:
        raise ValueError("relation IDs must not cross source-family train/validation split")
    if (isinstance(threshold, bool) or not isinstance(threshold, (int, float))
            or not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0):
        raise ValueError("threshold must be finite and in [0, 1]")

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
            "evaluation is source-family holdout over reviewed labels; relation structures are supplied as a fixed graph",
            "larger independent benchmarks and out-of-domain evaluation remain required",
        ],
    }
    return model, report


def rank_compositions(
    graph: SymbolGraph,
    model: NativeCompositionScorer | NativeRoleBindingModel,
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


def graph_from_json(path: str | Path) -> SymbolGraph:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("graph JSON must use schema_version 1")
    try:
        graph = SymbolGraph(
            evidence=tuple(EvidenceRef(**item) for item in data["evidence"]),
            symbols=tuple(Symbol(
                symbol_id=item["symbol_id"], domain=item["domain"],
                symbol_type=item["symbol_type"],
                attributes=tuple(tuple(pair) for pair in item["attributes"]),
                evidence_ids=tuple(item["evidence_ids"]),
                context=tuple(item.get("context", ())),
                version=item.get("version", 1),
            ) for item in data["symbols"]),
            relations=tuple(Relation(
                relation_id=item["relation_id"], relation_type=item["relation_type"],
                roles=tuple(tuple(pair) for pair in item["roles"]),
                evidence_ids=tuple(item["evidence_ids"]),
                conditions=tuple(item.get("conditions", ())),
                context=tuple(item.get("context", ())),
                version=item.get("version", 1),
            ) for item in data["relations"]),
            schema_version=data.get("schema_version", 1),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(f"invalid graph JSON structure: {exc}") from exc
    graph.validate()
    return graph


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", help="schema-v1 evidence-bound symbol graph JSON")
    parser.add_argument("labels", help="reviewed composition labels JSONL")
    parser.add_argument("--checkpoint", default="artifacts/classiang-composition.json")
    parser.add_argument("--report", default="artifacts/classiang-composition-report.json")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--model", choices=("linear", "role-binding"), default="role-binding")
    parser.add_argument("--dimension", type=int, default=16)
    parser.add_argument("--validation-graph")
    parser.add_argument("--validation-labels")
    args = parser.parse_args()
    if bool(args.validation_graph) != bool(args.validation_labels):
        parser.error("--validation-graph and --validation-labels must be supplied together")
    graph = graph_from_json(args.graph)
    labels = labels_from_jsonl(args.labels)
    if args.model == "role-binding":
        validation_graph = graph_from_json(args.validation_graph) if args.validation_graph else None
        validation_labels = labels_from_jsonl(args.validation_labels) if args.validation_labels else None
        model, report = train_and_evaluate_role_model(
            graph, labels, validation_graph=validation_graph,
            validation_labels=validation_labels,
            seed=args.seed, dimension=args.dimension,
            epochs=args.epochs, learning_rate=args.learning_rate,
            validation_fraction=args.validation_fraction, threshold=args.threshold,
        )
        if args.validation_graph:
            report["validation_graph_sha256"] = hashlib.sha256(Path(args.validation_graph).read_bytes()).hexdigest()
            report["validation_labels_sha256"] = hashlib.sha256(Path(args.validation_labels).read_bytes()).hexdigest()
    else:
        model, report = train_and_evaluate(
            graph, labels, seed=args.seed, epochs=args.epochs,
            learning_rate=args.learning_rate,
            validation_fraction=args.validation_fraction, threshold=args.threshold,
        )
    report["graph_sha256"] = hashlib.sha256(Path(args.graph).read_bytes()).hexdigest()
    report["labels_sha256"] = hashlib.sha256(Path(args.labels).read_bytes()).hexdigest()
    report["checkpoint_sha256"] = model.save(args.checkpoint)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))



@dataclass
class NativeRoleBindingModel:
    """Learned role-bound symbol representations with no token-attention path.

    Symbol vectors are composed from symbol-type, attribute-key, and
    attribute-value embeddings. A relation-role operator scores each bound
    symbol; the energy of a composition is the mean over its role bindings.
    This is an experimental native structural learner, not a foundation model.
    """

    dimension: int
    symbol_type_embeddings: dict[str, list[float]]
    attribute_key_embeddings: dict[str, list[float]]
    attribute_value_embeddings: dict[str, list[float]]
    relation_embeddings: dict[str, list[float]]
    role_embeddings: dict[str, list[float]]
    bias: float = 0.0
    trained_examples: int = 0
    epochs: int = 0

    @classmethod
    def initialize(
        cls, graph: SymbolGraph, training_labels: Sequence[CompositionLabel],
        *, dimension: int = 16, seed: int = 17,
    ) -> "NativeRoleBindingModel":
        if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 2:
            raise ValueError("dimension must be an integer >= 2")
        graph.validate()
        relation_map = {item.relation_id: item for item in graph.relations}
        symbol_map = {item.symbol_id: item for item in graph.symbols}
        used_relations = {
            relation_id for row in training_labels for relation_id in row.relation_ids
        }
        if not used_relations:
            raise ValueError("training labels must reference at least one relation")
        used_symbols: set[str] = set()
        relation_types: set[str] = set()
        roles: set[str] = set()
        for relation_id in used_relations:
            relation = relation_map[relation_id]
            relation_types.add(relation.relation_type)
            for role, symbol_id in relation.roles:
                roles.add(role)
                used_symbols.add(symbol_id)
        symbol_types: set[str] = set()
        attribute_keys: set[str] = set()
        attribute_values: set[str] = set()
        for symbol_id in used_symbols:
            symbol = symbol_map[symbol_id]
            symbol_types.add(symbol.symbol_type)
            for key, value in symbol.attributes:
                attribute_keys.add(key)
                attribute_values.add(value)
        rng = random.Random(seed)
        scale = 0.5 / math.sqrt(dimension)

        def table(keys: set[str]) -> dict[str, list[float]]:
            return {
                key: [rng.uniform(-scale, scale) for _ in range(dimension)]
                for key in sorted(keys)
            }

        return cls(
            dimension=dimension,
            symbol_type_embeddings=table(symbol_types),
            attribute_key_embeddings=table(attribute_keys),
            attribute_value_embeddings=table(attribute_values),
            relation_embeddings=table(relation_types),
            role_embeddings=table(roles),
        )

    def _symbol_parts(self, symbol: Symbol):
        parts = []
        if symbol.symbol_type in self.symbol_type_embeddings:
            parts.append(("symbol_type_embeddings", symbol.symbol_type))
        for key, value in symbol.attributes:
            if key in self.attribute_key_embeddings:
                parts.append(("attribute_key_embeddings", key))
            if value in self.attribute_value_embeddings:
                parts.append(("attribute_value_embeddings", value))
        if not parts:
            raise ValueError("symbol has no representation in the trained vocabulary")
        return parts

    def _symbol_vector(self, symbol: Symbol) -> tuple[list[float], list[tuple[str, str]]]:
        parts = self._symbol_parts(symbol)
        vector = [0.0] * self.dimension
        for table_name, key in parts:
            embedding = getattr(self, table_name)[key]
            for index, value in enumerate(embedding):
                vector[index] += value / len(parts)
        return vector, parts

    def _energy_terms(self, graph: SymbolGraph, relation_ids: tuple[str, ...]):
        relation_map = {item.relation_id: item for item in graph.relations}
        symbol_map = {item.symbol_id: item for item in graph.symbols}
        terms = []
        for relation_id in relation_ids:
            if relation_id not in relation_map:
                raise ValueError(f"unknown relation ID: {relation_id}")
            relation = relation_map[relation_id]
            if relation.relation_type not in self.relation_embeddings:
                raise ValueError("relation type is outside the trained vocabulary")
            relation_vector = self.relation_embeddings[relation.relation_type]
            for role, symbol_id in relation.roles:
                if role not in self.role_embeddings:
                    raise ValueError("role is outside the trained vocabulary")
                symbol_vector, parts = self._symbol_vector(symbol_map[symbol_id])
                role_vector = self.role_embeddings[role]
                terms.append((symbol_vector, parts, relation_vector, role_vector))
        if not terms:
            raise ValueError("composition contains no role bindings")
        return terms

    def score(self, graph: SymbolGraph, composition: Composition) -> float:
        return self.predict_probability(graph, composition.relation_ids)

    def predict_probability(self, graph: SymbolGraph, relation_ids: tuple[str, ...]) -> float:
        terms = self._energy_terms(graph, relation_ids)
        scale = math.sqrt(self.dimension)
        energy = sum(
            sum(s * (r + q) for s, r, q in zip(symbol, relation, role)) / scale
            for symbol, _, relation, role in terms
        ) / len(terms)
        return _sigmoid(self.bias + energy)

    def fit(
        self, graph: SymbolGraph, labels: Sequence[CompositionLabel], *,
        epochs: int = 200, learning_rate: float = 0.1,
        l2: float = 0.0001, seed: int = 17,
    ) -> "NativeRoleBindingModel":
        if not labels or not any(row.label == 0 for row in labels) or not any(row.label == 1 for row in labels):
            raise ValueError("training requires both positive and negative reviewed labels")
        if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
            raise ValueError("epochs must be a positive integer")
        for name, value in (("learning_rate", learning_rate), ("l2", l2)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if learning_rate == 0:
            raise ValueError("learning_rate must be positive")
        for row in labels:
            row.validate(graph)
        rng = random.Random(seed)
        scale = math.sqrt(self.dimension)
        for _ in range(epochs):
            order = list(range(len(labels)))
            rng.shuffle(order)
            for row_index in order:
                row = labels[row_index]
                terms = self._energy_terms(graph, row.relation_ids)
                term_scale = 1.0 / (len(terms) * scale)
                energy = sum(
                    sum(s * (r + q) for s, r, q in zip(symbol, relation, role)) / scale
                    for symbol, _, relation, role in terms
                ) / len(terms)
                error = _sigmoid(self.bias + energy) - row.label
                for symbol_vector, parts, relation_vector, role_vector in terms:
                    symbol_gradient = [
                        error * (relation_vector[i] + role_vector[i]) * term_scale
                        for i in range(self.dimension)
                    ]
                    relation_gradient = [
                        error * symbol_vector[i] * term_scale
                        for i in range(self.dimension)
                    ]
                    for table_name, key in parts:
                        embedding = getattr(self, table_name)[key]
                        part_scale = 1.0 / len(parts)
                        for i in range(self.dimension):
                            embedding[i] -= learning_rate * (
                                symbol_gradient[i] * part_scale + l2 * embedding[i]
                            )
                    relation = relation_vector
                    role = role_vector
                    for i in range(self.dimension):
                        relation[i] -= learning_rate * (
                            relation_gradient[i] + l2 * relation[i]
                        )
                        role[i] -= learning_rate * (
                            relation_gradient[i] + l2 * role[i]
                        )
                self.bias -= learning_rate * error
        self.trained_examples = len(labels)
        self.epochs = epochs
        return self

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "model_type": "classiang-native-role-binding-v1",
            "dimension": self.dimension,
            "symbol_type_embeddings": self.symbol_type_embeddings,
            "attribute_key_embeddings": self.attribute_key_embeddings,
            "attribute_value_embeddings": self.attribute_value_embeddings,
            "relation_embeddings": self.relation_embeddings,
            "role_embeddings": self.role_embeddings,
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
    def load(cls, path: str | Path) -> "NativeRoleBindingModel":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != 1 or data.get("model_type") != "classiang-native-role-binding-v1":
            raise ValueError("unsupported native role-binding checkpoint")
        dimension = data.get("dimension")
        if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 2:
            raise ValueError("invalid checkpoint dimension")
        names = (
            "symbol_type_embeddings", "attribute_key_embeddings",
            "attribute_value_embeddings", "relation_embeddings", "role_embeddings",
        )
        tables = {}
        for name in names:
            table = data.get(name)
            if not isinstance(table, dict):
                raise ValueError(f"invalid checkpoint table: {name}")
            checked = {}
            for key, vector in table.items():
                if not isinstance(key, str) or not key or not isinstance(vector, list) or len(vector) != dimension:
                    raise ValueError(f"invalid checkpoint vector in {name}")
                if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in vector):
                    raise ValueError(f"non-finite checkpoint vector in {name}")
                checked[key] = [float(x) for x in vector]
            tables[name] = checked
        bias = data.get("bias")
        if isinstance(bias, bool) or not isinstance(bias, (int, float)) or not math.isfinite(bias):
            raise ValueError("invalid checkpoint bias")
        return cls(
            dimension=dimension, **tables, bias=float(bias),
            trained_examples=int(data.get("trained_examples", 0)),
            epochs=int(data.get("epochs", 0)),
        )


def train_and_evaluate_role_model(
    graph: SymbolGraph, labels: Sequence[CompositionLabel], *,
    validation_graph: SymbolGraph | None = None,
    validation_labels: Sequence[CompositionLabel] | None = None,
    seed: int = 17, dimension: int = 16, epochs: int = 200,
    learning_rate: float = 0.1, validation_fraction: float = 0.2,
    threshold: float = 0.5,
) -> tuple[NativeRoleBindingModel, dict]:
    graph.validate()
    if not labels:
        raise ValueError("labels must be non-empty")
    for row in labels:
        row.validate(graph)

    if (validation_graph is None) != (validation_labels is None):
        raise ValueError("validation_graph and validation_labels must be supplied together")
    if validation_labels is None:
        train, validation = _split_by_group(labels, validation_fraction, seed)
        evaluation_graph = graph
        validation_mode = "source_family_holdout_from_train"
    else:
        if not validation_labels:
            raise ValueError("validation_labels must be non-empty")
        if not isinstance(validation_graph, SymbolGraph):
            raise ValueError("validation_graph must be SymbolGraph")
        validation_graph.validate()
        for row in validation_labels:
            row.validate(validation_graph)
        train_evidence = {item.evidence_id for item in graph.evidence}
        validation_evidence = {item.evidence_id for item in validation_graph.evidence}
        if train_evidence & validation_evidence:
            raise ValueError("evidence IDs must not cross train/validation split")
        train, validation = tuple(labels), tuple(validation_labels)
        evaluation_graph = validation_graph
        validation_mode = "manifest_dev_split"

    train_ids = [row.example_id for row in train]
    validation_ids = [row.example_id for row in validation]
    if len(train_ids) != len(set(train_ids)) or len(validation_ids) != len(set(validation_ids)):
        raise ValueError("example IDs must be unique within each split")
    if set(train_ids) & set(validation_ids):
        raise ValueError("example IDs must not cross train/validation split")
    train_families = {row.source_family for row in train}
    validation_families = {row.source_family for row in validation}
    if train_families & validation_families:
        raise ValueError("source families must not cross train/validation split")
    train_relations = {rid for row in train for rid in row.relation_ids}
    validation_relations = {rid for row in validation for rid in row.relation_ids}
    if train_relations & validation_relations:
        raise ValueError("relation IDs must not cross train/validation split")
    if not any(row.label == 0 for row in validation) or not any(row.label == 1 for row in validation):
        raise ValueError("validation requires both positive and negative reviewed labels")
    if (isinstance(threshold, bool) or not isinstance(threshold, (int, float))
            or not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0):
        raise ValueError("threshold must be finite and in [0, 1]")

    model = NativeRoleBindingModel.initialize(
        graph, train, dimension=dimension, seed=seed,
    ).fit(
        graph, train, epochs=epochs, learning_rate=learning_rate, seed=seed,
    )
    probabilities = [
        model.predict_probability(evaluation_graph, row.relation_ids)
        for row in validation
    ]
    truth = [row.label for row in validation]
    predictions = [int(value >= threshold) for value in probabilities]
    tp = sum(p == 1 and y == 1 for p, y in zip(predictions, truth))
    fp = sum(p == 1 and y == 0 for p, y in zip(predictions, truth))
    fn = sum(p == 0 and y == 1 for p, y in zip(predictions, truth))
    tn = sum(p == 0 and y == 0 for p, y in zip(predictions, truth))
    report = {
        "schema_version": 1,
        "model_type": "classiang-native-role-binding-v1",
        "dimension": dimension,
        "seed": seed,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "validation_mode": validation_mode,
        "validation_fraction": validation_fraction if validation_mode == "source_family_holdout_from_train" else None,
        "threshold": threshold,
        "train_examples": len(train),
        "validation_examples": len(validation),
        "train_source_families": sorted(train_families),
        "validation_source_families": sorted(validation_families),
        "source_family_disjoint": not (train_families & validation_families),
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "accuracy": (tp + tn) / len(truth),
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "brier_score": sum((p - y) ** 2 for p, y in zip(probabilities, truth)) / len(truth),
        "limitations": [
            "learned embeddings are composed from symbol type and explicit attribute key/value fields",
            "relation-role energy is a simple bilinear operator, not a general semantic model",
            "requires reviewed evidence-bound labels",
            "unseen relation types or roles are outside the trained vocabulary",
            "evaluation is source-family disjoint; independent OOD benchmarks remain required",
        ],
    }
    return model, report


if __name__ == "__main__":
    main()
