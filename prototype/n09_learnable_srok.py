"""N0.10: CPU-friendly learnable role-conditioned relational composition.

The learner replaces deterministic node ranking and additive-only scoring with
trainable role weights plus pairwise/third-order interaction terms. Type/tag
filters, distinct-member checks, and search budgets remain deterministic.

This is a small synthetic-reasoning prototype, not a language model.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations, product
import hashlib
import json
import math
from typing import Iterable, Sequence


@dataclass(frozen=True)
class RoleSpec:
    name: str
    allowed_types: frozenset[str] = frozenset()
    required_tags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Node:
    node_id: str
    node_type: str
    features: tuple[float, ...]
    tags: frozenset[str] = frozenset()
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class TrainingExample:
    role_candidates: tuple[tuple[Node, ...], ...]
    target_ids: tuple[str, ...]


@dataclass(frozen=True)
class LabeledStructure:
    assignment: tuple[Node, ...]
    label: int


@dataclass(frozen=True)
class RankedStructure:
    role_bindings: tuple[tuple[str, str], ...]
    score: float
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class Prediction:
    candidates: tuple[RankedStructure, ...]
    abstained: bool
    reason: str
    expanded_assignments: int
    budget_exhausted: bool
    role_pool_sizes: tuple[tuple[str, int], ...]


class LearnableSROKError(ValueError):
    """Invalid learner schema, training example, or inference budget."""


class LearnableSROK:
    """Structured softmax learner with deterministic symbolic boundaries.

    Score(x_1,...,x_R) contains role-conditioned unary terms, elementwise
    pairwise role interactions, and elementwise third-order interactions.
    """

    def __init__(self, roles: Sequence[RoleSpec], feature_dim: int) -> None:
        self.roles = tuple(roles)
        self.feature_dim = feature_dim
        if len(self.roles) < 2:
            raise LearnableSROKError("at least two roles are required")
        if len({role.name for role in self.roles}) != len(self.roles):
            raise LearnableSROKError("role names must be unique")
        if any(not role.name for role in self.roles):
            raise LearnableSROKError("role names must be non-empty")
        if feature_dim < 1:
            raise LearnableSROKError("feature_dim must be positive")
        self.pairs = tuple(combinations(range(len(self.roles)), 2))
        self.triples = tuple(combinations(range(len(self.roles)), 3))
        self.weights = [0.0] * (
            feature_dim * (len(self.roles) + len(self.pairs) + len(self.triples))
        )
        self.training_steps = 0

    def _validate_node(self, node: Node) -> None:
        if not node.node_id or not node.node_type:
            raise LearnableSROKError("node_id and node_type are required")
        if len(node.features) != self.feature_dim:
            raise LearnableSROKError("node feature dimension mismatch")
        if any(not math.isfinite(value) for value in node.features):
            raise LearnableSROKError("node features must be finite")

    def _compatible(self, node: Node, role: RoleSpec) -> bool:
        return (
            (not role.allowed_types or node.node_type in role.allowed_types)
            and role.required_tags.issubset(node.tags)
        )

    def _assignment_features(self, assignment: Sequence[Node]) -> list[float]:
        if len(assignment) != len(self.roles):
            raise LearnableSROKError("assignment role count mismatch")
        for node in assignment:
            self._validate_node(node)
        out: list[float] = []
        for node in assignment:
            out.extend(node.features)
        for left, right in self.pairs:
            out.extend(a * b for a, b in zip(
                assignment[left].features, assignment[right].features
            ))
        for first, second, third in self.triples:
            out.extend(a * b * c for a, b, c in zip(
                assignment[first].features,
                assignment[second].features,
                assignment[third].features,
            ))
        return out

    @staticmethod
    def _dot(left: Sequence[float], right: Sequence[float]) -> float:
        return sum(a * b for a, b in zip(left, right))

    def score(self, assignment: Sequence[Node]) -> float:
        return self._dot(self.weights, self._assignment_features(assignment))

    def _enumerate(self, pools, max_expansions):
        if max_expansions < 1:
            raise LearnableSROKError("max_expansions must be positive")
        assignments = []
        exhausted = False
        expanded = 0
        for candidate in product(*pools):
            if expanded >= max_expansions:
                exhausted = True
                break
            expanded += 1
            if len({node.node_id for node in candidate}) != len(candidate):
                continue
            assignments.append(tuple(candidate))
        return assignments, exhausted, expanded

    def fit(
        self, examples: Iterable[TrainingExample], *, epochs: int = 80,
        learning_rate: float = 0.2, l2: float = 1e-4,
        max_assignments_per_example: int = 4096,
    ) -> list[float]:
        """Train by full-candidate-set softmax; return mean loss per epoch."""
        rows = tuple(examples)
        if not rows:
            raise LearnableSROKError("training examples must not be empty")
        if epochs < 1 or learning_rate <= 0 or l2 < 0:
            raise LearnableSROKError("invalid optimizer settings")
        prepared = []
        for example in rows:
            if len(example.role_candidates) != len(self.roles):
                raise LearnableSROKError("training role pool count mismatch")
            if len(example.target_ids) != len(self.roles):
                raise LearnableSROKError("target role count mismatch")
            pools = []
            for role, pool in zip(self.roles, example.role_candidates):
                if not pool:
                    raise LearnableSROKError("training role pools must be non-empty")
                pool_ids = [node.node_id for node in pool]
                if len(pool_ids) != len(set(pool_ids)):
                    raise LearnableSROKError("node IDs must be unique within each role pool")
                for node in pool:
                    self._validate_node(node)
                    if not self._compatible(node, role):
                        raise LearnableSROKError("training pool violates role constraints")
                pools.append(tuple(pool))
            assignments, truncated, _expanded = self._enumerate(
                pools, max_assignments_per_example
            )
            if truncated:
                raise LearnableSROKError("training assignment budget truncated")
            target = next((
                index for index, assignment in enumerate(assignments)
                if tuple(node.node_id for node in assignment) == example.target_ids
            ), None)
            if target is None:
                raise LearnableSROKError("target assignment missing or violates uniqueness")
            prepared.append((
                [self._assignment_features(item) for item in assignments], target
            ))

        history = []
        width = len(self.weights)
        for _ in range(epochs):
            total_loss = 0.0
            gradient = [0.0] * width
            for features, target in prepared:
                scores = [self._dot(self.weights, row) for row in features]
                peak = max(scores)
                exp_scores = [math.exp(max(-60.0, score - peak)) for score in scores]
                denominator = sum(exp_scores)
                probabilities = [value / denominator for value in exp_scores]
                total_loss += -math.log(max(probabilities[target], 1e-15))
                for index, row in enumerate(features):
                    error = probabilities[index] - (1.0 if index == target else 0.0)
                    for column, value in enumerate(row):
                        gradient[column] += error * value
            scale = 1.0 / len(prepared)
            for column in range(width):
                gradient[column] = gradient[column] * scale + l2 * self.weights[column]
                self.weights[column] -= learning_rate * gradient[column]
            history.append(total_loss / len(prepared))
            self.training_steps += 1
        return history

    def retrieve(self, role_index: int, nodes: Iterable[Node], *, top_k: int):
        """Role-conditioned top-k retrieval after deterministic hard filtering."""
        if not 0 <= role_index < len(self.roles):
            raise LearnableSROKError("role_index out of range")
        if top_k < 1:
            raise LearnableSROKError("top_k must be positive")
        start = role_index * self.feature_dim
        role_weights = self.weights[start:start + self.feature_dim]
        eligible = []
        seen = set()
        for node in nodes:
            self._validate_node(node)
            if node.node_id in seen:
                raise LearnableSROKError("node IDs must be unique")
            seen.add(node.node_id)
            if self._compatible(node, self.roles[role_index]):
                eligible.append((node, self._dot(role_weights, node.features)))
        eligible.sort(key=lambda item: (-item[1], item[0].node_id))
        return tuple(eligible[:top_k])

    def predict(
        self, nodes: Iterable[Node], *, top_k_per_role: int = 8,
        max_expansions: int = 4096, result_limit: int = 5,
        abstain_margin: float = 0.0,
    ) -> Prediction:
        """Retrieve, compose, score, and optionally abstain under fixed budgets."""
        if result_limit < 1 or abstain_margin < 0:
            raise LearnableSROKError("invalid result limit or abstain margin")
        node_list = tuple(nodes)
        for node in node_list:
            self._validate_node(node)
        if len({node.node_id for node in node_list}) != len(node_list):
            raise LearnableSROKError("node IDs must be unique")
        retrieved = tuple(
            self.retrieve(i, node_list, top_k=top_k_per_role)
            for i in range(len(self.roles))
        )
        pools = tuple(tuple(node for node, _ in items) for items in retrieved)
        sizes = tuple((role.name, len(pool)) for role, pool in zip(self.roles, pools))
        if any(not pool for pool in pools):
            return Prediction((), True, "NO_ROLE_CANDIDATES", 0, False, sizes)
        assignments, exhausted, expanded = self._enumerate(pools, max_expansions)
        ranked = sorted(
            assignments,
            key=lambda assignment: (
                -self.score(assignment),
                tuple(node.node_id for node in assignment),
            ),
        )
        structures = tuple(
            RankedStructure(
                role_bindings=tuple(
                    (role.name, node.node_id)
                    for role, node in zip(self.roles, assignment)
                ),
                score=self.score(assignment),
                evidence_ids=tuple(dict.fromkeys(
                    evidence_id for node in assignment
                    for evidence_id in node.evidence_ids
                )),
            )
            for assignment in ranked[:result_limit]
        )
        if not structures:
            return Prediction(
                (), True, "NO_VALID_ASSIGNMENT", expanded, exhausted, sizes
            )
        # Compute confidence from the actual top two found assignments before
        # applying result_limit; result_limit=1 must not disable abstention.
        margin = (
            self.score(ranked[0]) - self.score(ranked[1])
            if len(ranked) > 1 else math.inf
        )
        if margin <= abstain_margin:
            return Prediction(
                structures, True, "LOW_SCORE_MARGIN", expanded,
                exhausted, sizes,
            )
        return Prediction(
            structures, False, "ACCEPTED", expanded, exhausted, sizes
        )


    def _features_at_order(self, assignment: Sequence[Node], max_order: int) -> list[float]:
        if isinstance(max_order, bool) or not isinstance(max_order, int) or max_order not in (1, 2, 3):
            raise LearnableSROKError("max_order must be integer 1, 2, or 3")
        features = self._assignment_features(assignment)
        unary_end = self.feature_dim * len(self.roles)
        pair_end = unary_end + self.feature_dim * len(self.pairs)
        if max_order == 1:
            features[unary_end:] = [0.0] * (len(features) - unary_end)
        elif max_order == 2:
            features[pair_end:] = [0.0] * (len(features) - pair_end)
        if any(not math.isfinite(value) for value in features):
            raise LearnableSROKError("interaction features must be finite")
        return features

    def fit_binary(
        self,
        examples: Iterable[LabeledStructure],
        *,
        max_order: int = 3,
        epochs: int = 120,
        learning_rate: float = 0.15,
        l2: float = 1e-3,
    ) -> list[float]:
        """Fit a binary structure classifier for controlled interaction ablations.

        max_order=1 trains unary terms only; 2 adds pairwise terms; 3 adds
        explicit triple terms. The same feature map and optimizer are used for
        every ablation, with inactive higher-order blocks zeroed.
        """
        if isinstance(max_order, bool) or not isinstance(max_order, int) or max_order not in (1, 2, 3):
            raise LearnableSROKError("max_order must be integer 1, 2, or 3")
        if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
            raise LearnableSROKError("epochs must be a positive integer")
        if (not math.isfinite(learning_rate) or learning_rate <= 0
                or not math.isfinite(l2) or l2 < 0):
            raise LearnableSROKError("invalid optimizer settings")
        rows = []
        for example in examples:
            if not isinstance(example, LabeledStructure):
                raise LearnableSROKError("examples must be LabeledStructure values")
            if (isinstance(example.label, bool) or not isinstance(example.label, int)
                    or example.label not in (0, 1)):
                raise LearnableSROKError("binary labels must be integer 0 or 1")
            if len(example.assignment) != len(self.roles):
                raise LearnableSROKError("assignment role count mismatch")
            if len({node.node_id for node in example.assignment}) != len(self.roles):
                raise LearnableSROKError("assignment node IDs must be unique")
            for role, node in zip(self.roles, example.assignment):
                self._validate_node(node)
                if not self._compatible(node, role):
                    raise LearnableSROKError("assignment violates role constraints")
            rows.append((self._features_at_order(example.assignment, max_order),
                         float(example.label)))
        if not rows:
            raise LearnableSROKError("binary training examples must not be empty")

        active_width = (
            self.feature_dim * len(self.roles)
            + (self.feature_dim * len(self.pairs) if max_order >= 2 else 0)
            + (self.feature_dim * len(self.triples) if max_order >= 3 else 0)
        )
        active_mask = [1.0 if i < active_width else 0.0
                       for i in range(len(self.weights))]
        self.weights = [0.0] * len(self.weights)
        history = []
        for _ in range(epochs):
            gradient = [0.0] * len(self.weights)
            total_loss = 0.0
            for features, label in rows:
                score = self._dot(self.weights, features)
                if score >= 0:
                    probability = 1.0 / (1.0 + math.exp(-min(score, 60.0)))
                else:
                    exp_score = math.exp(max(score, -60.0))
                    probability = exp_score / (1.0 + exp_score)
                total_loss += (
                    max(score, 0.0) - score * label
                    + math.log1p(math.exp(-abs(score)))
                )
                error = probability - label
                for index, value in enumerate(features):
                    gradient[index] += error * value
            scale = 1.0 / len(rows)
            for index in range(len(self.weights)):
                gradient[index] = (
                    gradient[index] * scale
                    + l2 * self.weights[index] * active_mask[index]
                )
                self.weights[index] -= learning_rate * gradient[index] * active_mask[index]
                if not math.isfinite(self.weights[index]):
                    raise LearnableSROKError("optimizer produced non-finite weights")
            history.append(total_loss / len(rows))
            self.training_steps += 1
        return history

    def predict_binary(
        self, assignment: Sequence[Node], *, max_order: int = 3
    ) -> tuple[int, float]:
        """Return (thresholded label, raw logit) at the requested interaction order."""
        features = self._features_at_order(assignment, max_order)
        score = self._dot(self.weights, features)
        if not math.isfinite(score):
            raise LearnableSROKError("prediction score must be finite")
        return (1 if score >= 0.0 else 0), score


    def checkpoint_json(self) -> str:
        """Serialize deterministic model state with a content-addressed version."""
        payload = {
            "format": "zhouyi-ai.n10.learnable-srok",
            "schema_version": 1,
            "feature_dim": self.feature_dim,
            "roles": [
                {
                    "name": role.name,
                    "allowed_types": sorted(role.allowed_types),
                    "required_tags": sorted(role.required_tags),
                }
                for role in self.roles
            ],
            "weights": self.weights,
            "training_steps": self.training_steps,
        }
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        envelope = dict(payload)
        envelope["sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return json.dumps(
            envelope, sort_keys=True, indent=2,
            ensure_ascii=False, allow_nan=False,
        )

    @classmethod
    def from_checkpoint_json(cls, raw: str) -> "LearnableSROK":
        """Load a checkpoint only after schema, digest, shape, and finiteness checks."""
        try:
            envelope = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise LearnableSROKError("checkpoint must be valid JSON") from exc
        if not isinstance(envelope, dict):
            raise LearnableSROKError("checkpoint root must be an object")
        expected = {
            "format", "schema_version", "feature_dim", "roles",
            "weights", "training_steps", "sha256",
        }
        if set(envelope) != expected:
            raise LearnableSROKError("checkpoint fields do not match schema")
        supplied_digest = envelope.get("sha256")
        payload = {key: value for key, value in envelope.items() if key != "sha256"}
        try:
            canonical = json.dumps(
                payload, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise LearnableSROKError("checkpoint contains non-canonical values") from exc
        actual_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if (not isinstance(supplied_digest, str)
                or supplied_digest != actual_digest):
            raise LearnableSROKError("checkpoint digest mismatch")
        if (payload["format"] != "zhouyi-ai.n10.learnable-srok"
                or isinstance(payload["schema_version"], bool)
                or not isinstance(payload["schema_version"], int)
                or payload["schema_version"] != 1):
            raise LearnableSROKError("unsupported checkpoint format or version")
        feature_dim = payload["feature_dim"]
        if isinstance(feature_dim, bool) or not isinstance(feature_dim, int) or feature_dim < 1:
            raise LearnableSROKError("checkpoint feature_dim must be a positive integer")
        raw_roles = payload["roles"]
        if not isinstance(raw_roles, list) or len(raw_roles) < 2:
            raise LearnableSROKError("checkpoint roles must be a list of at least two roles")
        roles = []
        for item in raw_roles:
            if not isinstance(item, dict) or set(item) != {"name", "allowed_types", "required_tags"}:
                raise LearnableSROKError("invalid checkpoint role schema")
            if (not isinstance(item["name"], str) or not item["name"]
                    or not isinstance(item["allowed_types"], list)
                    or not isinstance(item["required_tags"], list)
                    or any(not isinstance(x, str) or not x for x in item["allowed_types"] + item["required_tags"])):
                raise LearnableSROKError("invalid checkpoint role values")
            roles.append(RoleSpec(
                item["name"], frozenset(item["allowed_types"]),
                frozenset(item["required_tags"]),
            ))
        weights = payload["weights"]
        if not isinstance(weights, list) or any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) for value in weights
        ):
            raise LearnableSROKError("checkpoint weights must be finite numbers")
        steps = payload["training_steps"]
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
            raise LearnableSROKError("checkpoint training_steps must be a non-negative integer")
        model = cls(roles, feature_dim)
        if len(weights) != len(model.weights):
            raise LearnableSROKError("checkpoint weight shape mismatch")
        model.weights = [float(value) for value in weights]
        model.training_steps = steps
        return model
