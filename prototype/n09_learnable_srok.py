"""N0.10: CPU-friendly learnable role-conditioned relational composition.

The learner replaces deterministic node ranking and additive-only scoring with
trainable role weights plus pairwise/third-order interaction terms. Type/tag
filters, distinct-member checks, and search budgets remain deterministic.

This is a small synthetic-reasoning prototype, not a language model.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations, product
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
        if margin < abstain_margin:
            return Prediction(
                structures, True, "LOW_SCORE_MARGIN", expanded,
                exhausted, sizes,
            )
        return Prediction(
            structures, False, "ACCEPTED", expanded, exhausted, sizes
        )
