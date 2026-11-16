"""N0.10: CPU-friendly learnable role-conditioned relational composition.

The learner replaces deterministic node ranking and additive-only scoring with
trainable role weights plus pairwise/third-order interaction terms. Type/tag
filters, distinct-member checks, and search budgets remain deterministic.

This is a small synthetic-reasoning prototype, not a language model.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import heapq
import json
from itertools import combinations, product
import math
from typing import Callable, Iterable, Sequence


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
class RelationClassificationExample:
    """One labeled complete role assignment for relation classification."""
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

    @property
    def expanded_search_states(self) -> int:
        """Number of expanded search states, including partial beam prefixes.

        expanded_assignments is retained as a compatibility alias. Exact
        product search expands complete assignments; beam and branch-bound
        also expand partial prefixes, so the older field name is not precise
        for all strategies.
        """
        return self.expanded_assignments


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
        if len(self.roles) < 2 or any(not isinstance(role, RoleSpec) for role in self.roles):
            raise LearnableSROKError("at least two valid roles are required")
        if any(not isinstance(role.name, str) or not role.name.strip() for role in self.roles):
            raise LearnableSROKError("role names must be non-empty strings")
        if len({role.name for role in self.roles}) != len(self.roles):
            raise LearnableSROKError("role names must be unique")
        if any(any(not isinstance(value, str) or not value.strip() for value in role.allowed_types | role.required_tags) for role in self.roles):
            raise LearnableSROKError("role types and tags must be non-empty strings")
        if isinstance(feature_dim, bool) or not isinstance(feature_dim, int) or feature_dim < 1:
            raise LearnableSROKError("feature_dim must be a positive integer")
        self.pairs = tuple(combinations(range(len(self.roles)), 2))
        self.triples = tuple(combinations(range(len(self.roles)), 3))
        self.weights = [0.0] * (
            feature_dim * (len(self.roles) + len(self.pairs) + len(self.triples))
        )
        self.training_steps = 0

    def _validate_node(self, node: Node) -> None:
        if not isinstance(node, Node):
            raise LearnableSROKError("candidate must be a Node")
        if not isinstance(node.node_id, str) or not node.node_id.strip() or not isinstance(node.node_type, str) or not node.node_type.strip():
            raise LearnableSROKError("node_id and node_type must be non-empty strings")
        if len(node.features) != self.feature_dim:
            raise LearnableSROKError("node feature dimension mismatch")
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) for value in node.features):
            raise LearnableSROKError("node features must be finite numbers")
        if any(not isinstance(tag, str) or not tag.strip() for tag in node.tags):
            raise LearnableSROKError("node tags must be non-empty strings")
        if any(not isinstance(ref, str) or not ref.strip() for ref in node.evidence_ids):
            raise LearnableSROKError("evidence IDs must be non-empty strings")

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
        if any(not math.isfinite(value) for value in out):
            raise LearnableSROKError("interaction features overflowed")
        return out

    @staticmethod
    def _dot(left: Sequence[float], right: Sequence[float]) -> float:
        try:
            value = math.fsum(a * b for a, b in zip(left, right))
        except OverflowError as exc:
            raise LearnableSROKError("score computation overflowed") from exc
        if not math.isfinite(value):
            raise LearnableSROKError("score must be finite")
        return value

    def _interaction_limit(self, features: Sequence[float], interaction_order: int) -> int:
        if isinstance(interaction_order, bool) or not isinstance(interaction_order, int) or interaction_order not in (1, 2, 3):
            raise LearnableSROKError("interaction_order must be 1, 2, or 3")
        unary_width = self.feature_dim * len(self.roles)
        pair_width = self.feature_dim * len(self.pairs)
        if interaction_order == 1:
            return unary_width
        if interaction_order == 2:
            return unary_width + pair_width
        return len(features)

    def score(self, assignment: Sequence[Node], *, interaction_order: int = 3) -> float:
        """Score one complete assignment, optionally ablating higher interactions."""
        features = self._assignment_features(assignment)
        limit = self._interaction_limit(features, interaction_order)
        return self._dot(self.weights[:limit], features[:limit])

    def fit_relation_classifier(self, examples: Iterable[RelationClassificationExample], *,
                                epochs: int = 300, learning_rate: float = 0.1,
                                l2: float = 1e-4, interaction_order: int = 3) -> list[float]:
        """Train binary labels on complete assignments using the SROK score features.

        Unlike structured fit(), this supports multiple positive assignments and
        is suitable for balanced parity truth tables.
        """
        rows = tuple(examples)
        if not rows:
            raise LearnableSROKError("relation examples must not be empty")
        if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
            raise LearnableSROKError("epochs must be a positive integer")
        if not isinstance(learning_rate, (int, float)) or isinstance(learning_rate, bool) or not math.isfinite(learning_rate) or learning_rate <= 0:
            raise LearnableSROKError("learning_rate must be finite and positive")
        if not isinstance(l2, (int, float)) or isinstance(l2, bool) or not math.isfinite(l2) or l2 < 0:
            raise LearnableSROKError("l2 must be finite and non-negative")
        prepared = []
        for row in rows:
            if not isinstance(row, RelationClassificationExample):
                raise LearnableSROKError("each row must be a RelationClassificationExample")
            if type(row.label) is not int or row.label not in (-1, 1):
                raise LearnableSROKError("relation labels must be integer -1 or +1")
            if len(row.assignment) != len(self.roles):
                raise LearnableSROKError("assignment role count mismatch")
            for node, role in zip(row.assignment, self.roles):
                self._validate_node(node)
                if not self._compatible(node, role):
                    raise LearnableSROKError("assignment violates role constraints")
            if len({node.node_id for node in row.assignment}) != len(row.assignment):
                raise LearnableSROKError("assignment members must be distinct")
            features = self._assignment_features(row.assignment)
            limit = self._interaction_limit(features, interaction_order)
            prepared.append((features[:limit], 1.0 if row.label == 1 else 0.0))
        width = len(prepared[0][0])
        if any(len(features) != width for features, _ in prepared):
            raise LearnableSROKError("inconsistent relation feature widths")
        history = []
        for _ in range(epochs):
            gradient = [0.0] * width
            total_loss = 0.0
            for features, target in prepared:
                logit = self._dot(self.weights[:width], features)
                if logit >= 0:
                    exp_value = math.exp(-min(logit, 60.0))
                    probability = 1.0 / (1.0 + exp_value)
                else:
                    exp_value = math.exp(max(logit, -60.0))
                    probability = exp_value / (1.0 + exp_value)
                clipped = min(max(probability, 1e-15), 1.0 - 1e-15)
                total_loss += -(target * math.log(clipped) + (1.0 - target) * math.log(1.0 - clipped))
                error = probability - target
                for index, value in enumerate(features):
                    gradient[index] += error * value
            for index in range(width):
                gradient[index] = gradient[index] / len(prepared) + l2 * self.weights[index]
                if not math.isfinite(gradient[index]):
                    raise LearnableSROKError("relation gradient became non-finite")
                self.weights[index] -= learning_rate * gradient[index]
                if not math.isfinite(self.weights[index]):
                    raise LearnableSROKError("relation weights became non-finite")
            history.append(total_loss / len(prepared))
            self.training_steps += 1
        return history

    def predict_relation_probability(self, assignment: Sequence[Node], *, interaction_order: int = 3) -> float:
        """Return P(label=+1) from the model's actual assignment score."""
        logit = self.score(assignment, interaction_order=interaction_order)
        if logit >= 0:
            exp_value = math.exp(-min(logit, 60.0))
            return 1.0 / (1.0 + exp_value)
        exp_value = math.exp(max(logit, -60.0))
        return exp_value / (1.0 + exp_value)


    def _enumerate(self, pools, max_expansions):
        if isinstance(max_expansions, bool) or not isinstance(max_expansions, int) or max_expansions < 1:
            raise LearnableSROKError("max_expansions must be a positive integer")
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

    def _partial_score(self, assignment: Sequence[Node]) -> float:
        """Score all unary/pair/triple terms whose roles are already assigned."""
        count = len(assignment)
        if count > len(self.roles):
            raise LearnableSROKError("partial assignment role count mismatch")
        features: list[float] = []
        for node in assignment:
            self._validate_node(node)
        for node in assignment:
            features.extend(node.features)
        for left, right in combinations(range(count), 2):
            features.extend(
                a * b for a, b in zip(
                    assignment[left].features, assignment[right].features
                )
            )
        for first, second, third in combinations(range(count), 3):
            features.extend(
                a * b * c for a, b, c in zip(
                    assignment[first].features,
                    assignment[second].features,
                    assignment[third].features,
                )
            )
        # Feature blocks in the model are ordered by role, then role-pair,
        # then role-triple. Build the matching weight indices explicitly.
        indices: list[int] = []
        dim = self.feature_dim
        indices.extend(range(count * dim))
        pair_offset = len(self.roles) * dim
        all_pairs = tuple(combinations(range(len(self.roles)), 2))
        for pair in combinations(range(count), 2):
            indices.extend(
                range(pair_offset + all_pairs.index(pair) * dim,
                      pair_offset + (all_pairs.index(pair) + 1) * dim)
            )
        triple_offset = pair_offset + len(all_pairs) * dim
        all_triples = tuple(combinations(range(len(self.roles)), 3))
        for triple in combinations(range(count), 3):
            index = all_triples.index(triple)
            indices.extend(range(triple_offset + index * dim,
                                 triple_offset + (index + 1) * dim))
        if len(indices) != len(features):
            raise LearnableSROKError("partial feature layout mismatch")
        return self._dot([self.weights[index] for index in indices], features)

    def _beam_enumerate(self, pools, max_expansions: int, beam_width: int):
        """Bounded deterministic beam search over role prefixes.

        The partial score is an ordering heuristic, not an admissible upper
        bound. Beam search is therefore approximate; the exhaustion flag
        reports budget truncation but cannot certify recall.
        """
        if isinstance(beam_width, bool) or not isinstance(beam_width, int) or beam_width < 1:
            raise LearnableSROKError("beam_width must be a positive integer")
        beam: list[tuple[Node, ...]] = [()]
        expanded = 0
        pruned = False
        for pool in pools:
            proposals: list[tuple[Node, ...]] = []
            for prefix in beam:
                for node in pool:
                    if expanded >= max_expansions:
                        ranked = sorted(
                            proposals,
                            key=lambda item: (-self._partial_score(item),
                                              tuple(value.node_id for value in item)),
                        )
                        return (
                            [item for item in ranked if len(item) == len(self.roles)],
                            True, pruned, expanded,
                        )
                    expanded += 1
                    if any(existing.node_id == node.node_id for existing in prefix):
                        continue
                    proposals.append(prefix + (node,))
            proposals.sort(
                key=lambda item: (-self._partial_score(item),
                                  tuple(value.node_id for value in item))
            )
            if len(proposals) > beam_width:
                pruned = True
            beam = proposals[:beam_width]
            if not beam:
                break
        complete = [item for item in beam if len(item) == len(self.roles)]
        return complete, False, pruned, expanded

    def _assignment_upper_bound(self, prefix: Sequence[Node], pools) -> float:
        """Admissible upper bound for every completion of a role prefix.

        Each unary/pairwise/third-order feature term is bounded independently
        over the remaining role pools. Ignoring cross-term candidate coupling
        and distinct-member constraints can only make the bound optimistic.
        """
        assigned = len(prefix)
        role_count = len(self.roles)
        if assigned > role_count or len(pools) != role_count:
            raise LearnableSROKError("partial assignment or pool role count mismatch")
        for node in prefix:
            self._validate_node(node)
        if any(not pool for pool in pools):
            raise LearnableSROKError("upper-bound candidate pools must be non-empty")

        def maximum_contribution(term_roles, weight_index, feature_index):
            min_product = 1.0
            max_product = 1.0
            for role_index in term_roles:
                if role_index < assigned:
                    values = (prefix[role_index].features[feature_index],)
                else:
                    values = tuple(
                        node.features[feature_index] for node in pools[role_index]
                    )
                low, high = min(values), max(values)
                products = (
                    min_product * low, min_product * high,
                    max_product * low, max_product * high,
                )
                if any(not math.isfinite(value) for value in products):
                    raise LearnableSROKError("upper-bound interaction product overflowed")
                min_product = min(products)
                max_product = max(products)
            weight = self.weights[weight_index]
            contribution = weight * (
                max_product if weight >= 0.0 else min_product
            )
            if not math.isfinite(contribution):
                raise LearnableSROKError("upper-bound contribution is non-finite")
            return contribution

        dim = self.feature_dim
        terms = []
        for role_index in range(role_count):
            for feature_index in range(dim):
                terms.append(maximum_contribution(
                    (role_index,), role_index * dim + feature_index,
                    feature_index,
                ))

        pair_offset = role_count * dim
        for pair_index, pair in enumerate(self.pairs):
            for feature_index in range(dim):
                terms.append(maximum_contribution(
                    pair,
                    pair_offset + pair_index * dim + feature_index,
                    feature_index,
                ))

        triple_offset = pair_offset + len(self.pairs) * dim
        for triple_index, triple in enumerate(self.triples):
            for feature_index in range(dim):
                terms.append(maximum_contribution(
                    triple,
                    triple_offset + triple_index * dim + feature_index,
                    feature_index,
                ))

        try:
            bound = math.fsum(terms)
        except OverflowError as exc:
            raise LearnableSROKError("upper-bound score overflowed") from exc
        if not math.isfinite(bound):
            raise LearnableSROKError("upper-bound score is non-finite")
        return bound

    def _branch_bound_enumerate(self, pools, max_expansions: int, top_k: int):
        """Best-first exact top-k search using an admissible score upper bound.

        Unlike beam search, branches are discarded only after their optimistic
        score is strictly below the current kth complete score. Equal-score
        branches remain searchable so deterministic tie ordering is exact.
        """
        if isinstance(max_expansions, bool) or not isinstance(max_expansions, int) or max_expansions < 1:
            raise LearnableSROKError("max_expansions must be a positive integer")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 2:
            raise LearnableSROKError("branch-and-bound top_k must be at least two")

        def minimum_completion_ids(prefix):
            return (
                tuple(node.node_id for node in prefix)
                + tuple(
                    min(node.node_id for node in pool)
                    for pool in pools[len(prefix):]
                )
            )

        root = ()
        serial = 0
        root_bound = self._assignment_upper_bound(root, pools)
        frontier = [(-root_bound, minimum_completion_ids(root), serial, root)]
        best = []
        expanded = 0
        role_count = len(self.roles)

        while frontier:
            best_remaining_bound = -frontier[0][0]
            if len(best) >= top_k:
                kth_score = best[-1][0]
                kth_ids = tuple(node.node_id for node in best[-1][1])
                best_tie_lower_bound = frontier[0][1]
                if (
                    best_remaining_bound < kth_score
                    or (
                        best_remaining_bound == kth_score
                        and best_tie_lower_bound >= kth_ids
                    )
                ):
                    break

            _negative_bound, _tie_lower_bound, _serial, prefix = heapq.heappop(frontier)
            if len(prefix) == role_count:
                score = self.score(prefix)
                best.append((score, prefix))
                best.sort(key=lambda item: (
                    -item[0], tuple(node.node_id for node in item[1])
                ))
                if len(best) > top_k:
                    best.pop()
                continue

            role_index = len(prefix)
            for node in pools[role_index]:
                if expanded >= max_expansions:
                    return [assignment for _score, assignment in best], True, expanded
                expanded += 1
                if any(existing.node_id == node.node_id for existing in prefix):
                    continue
                child = prefix + (node,)
                bound = self._assignment_upper_bound(child, pools)
                serial += 1
                tie_lower_bound = minimum_completion_ids(child)
                heapq.heappush(
                    frontier, (-bound, tie_lower_bound, serial, child)
                )

        return [assignment for _score, assignment in best], False, expanded

    def fit(
        self, examples: Iterable[TrainingExample], *, epochs: int = 80,
        learning_rate: float = 0.2, l2: float = 1e-4,
        max_assignments_per_example: int = 4096,
    ) -> list[float]:
        """Train by full-candidate-set softmax; return mean loss per epoch."""
        rows = tuple(examples)
        if not rows:
            raise LearnableSROKError("training examples must not be empty")
        if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
            raise LearnableSROKError("epochs must be a positive integer")
        if not isinstance(learning_rate, (int, float)) or isinstance(learning_rate, bool) or not math.isfinite(learning_rate) or learning_rate <= 0:
            raise LearnableSROKError("learning_rate must be finite and positive")
        if not isinstance(l2, (int, float)) or isinstance(l2, bool) or not math.isfinite(l2) or l2 < 0:
            raise LearnableSROKError("l2 must be finite and non-negative")
        if isinstance(max_assignments_per_example, bool) or not isinstance(max_assignments_per_example, int) or max_assignments_per_example < 1:
            raise LearnableSROKError("max_assignments_per_example must be a positive integer")
        prepared = []
        for example in rows:
            if len(example.role_candidates) != len(self.roles):
                raise LearnableSROKError("training role pool count mismatch")
            if len(example.target_ids) != len(self.roles) or any(not isinstance(value, str) or not value.strip() for value in example.target_ids):
                raise LearnableSROKError("target IDs must match the role count and be non-empty strings")
            if len(set(example.target_ids)) != len(example.target_ids):
                raise LearnableSROKError("target IDs must be unique across roles")
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
                if not math.isfinite(gradient[column]):
                    raise LearnableSROKError("training gradient became non-finite")
                self.weights[column] -= learning_rate * gradient[column]
                if not math.isfinite(self.weights[column]):
                    raise LearnableSROKError("model weights became non-finite")
            mean_loss = total_loss / len(prepared)
            if not math.isfinite(mean_loss):
                raise LearnableSROKError("training loss became non-finite")
            history.append(mean_loss)
            self.training_steps += 1
        return history


    def fit_reiterable(
        self, examples_factory: Callable[[], Iterable[TrainingExample]], *,
        epochs: int = 80, learning_rate: float = 0.2, l2: float = 1e-4,
        max_assignments_per_example: int = 4096,
    ) -> list[float]:
        """Exact full-batch updates from a re-openable stream, retaining one example at a time.

        The factory must return the same ordered dataset on every call. Each epoch
        accumulates the complete-dataset gradient against frozen weights and applies
        exactly one update, so this is not mini-batch SGD. Memory is bounded by one
        example's candidate assignments plus the parameter/gradient vectors.
        """
        if not callable(examples_factory):
            raise LearnableSROKError("examples_factory must be callable")
        if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
            raise LearnableSROKError("epochs must be a positive integer")
        if not isinstance(learning_rate, (int, float)) or isinstance(learning_rate, bool) or not math.isfinite(learning_rate) or learning_rate <= 0:
            raise LearnableSROKError("learning_rate must be finite and positive")
        if not isinstance(l2, (int, float)) or isinstance(l2, bool) or not math.isfinite(l2) or l2 < 0:
            raise LearnableSROKError("l2 must be finite and non-negative")
        if isinstance(max_assignments_per_example, bool) or not isinstance(max_assignments_per_example, int) or max_assignments_per_example < 1:
            raise LearnableSROKError("max_assignments_per_example must be a positive integer")

        def stream_signature():
            hasher = hashlib.sha256()
            count = 0
            for example in examples_factory():
                if not isinstance(example, TrainingExample):
                    raise LearnableSROKError("each streamed row must be a TrainingExample")
                try:
                    payload = {
                        "target_ids": list(example.target_ids),
                        "role_candidates": [[
                            {
                                "node_id": node.node_id,
                                "node_type": node.node_type,
                                "features": list(node.features),
                                "tags": sorted(node.tags),
                                "evidence_ids": list(node.evidence_ids),
                            }
                            for node in pool
                        ] for pool in example.role_candidates],
                    }
                    encoded = json.dumps(
                        payload, sort_keys=True, separators=(",", ":"),
                        ensure_ascii=False, allow_nan=False,
                    ).encode("utf-8")
                except (AttributeError, TypeError, ValueError) as exc:
                    raise LearnableSROKError("stream contains a malformed training example") from exc
                hasher.update(len(encoded).to_bytes(8, "big"))
                hasher.update(encoded)
                count += 1
            return count, hasher.hexdigest()

        example_count, expected_signature = stream_signature()
        if example_count == 0:
            raise LearnableSROKError("training examples must not be empty")

        history = []
        width = len(self.weights)
        for _ in range(epochs):
            total_loss = 0.0
            gradient = [0.0] * width
            observed = 0
            pass_hasher = hashlib.sha256()
            for example in examples_factory():
                if not isinstance(example, TrainingExample):
                    raise LearnableSROKError("each streamed row must be a TrainingExample")
                try:
                    payload = {
                        "target_ids": list(example.target_ids),
                        "role_candidates": [[
                            {
                                "node_id": node.node_id,
                                "node_type": node.node_type,
                                "features": list(node.features),
                                "tags": sorted(node.tags),
                                "evidence_ids": list(node.evidence_ids),
                            }
                            for node in pool
                        ] for pool in example.role_candidates],
                    }
                    encoded = json.dumps(
                        payload, sort_keys=True, separators=(",", ":"),
                        ensure_ascii=False, allow_nan=False,
                    ).encode("utf-8")
                except (AttributeError, TypeError, ValueError) as exc:
                    raise LearnableSROKError("stream contains a malformed training example") from exc
                pass_hasher.update(len(encoded).to_bytes(8, "big"))
                pass_hasher.update(encoded)
                observed += 1
                if len(example.role_candidates) != len(self.roles):
                    raise LearnableSROKError("training role pool count mismatch")
                if len(example.target_ids) != len(self.roles) or any(
                    not isinstance(value, str) or not value.strip()
                    for value in example.target_ids
                ):
                    raise LearnableSROKError("target IDs must match the role count and be non-empty strings")
                if len(set(example.target_ids)) != len(example.target_ids):
                    raise LearnableSROKError("target IDs must be unique across roles")
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
                features = [self._assignment_features(item) for item in assignments]
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

            if observed != example_count or pass_hasher.hexdigest() != expected_signature:
                raise LearnableSROKError("reiterable training stream changed content, order, or record count")
            scale = 1.0 / example_count
            for column in range(width):
                gradient[column] = gradient[column] * scale + l2 * self.weights[column]
                if not math.isfinite(gradient[column]):
                    raise LearnableSROKError("training gradient became non-finite")
                self.weights[column] -= learning_rate * gradient[column]
                if not math.isfinite(self.weights[column]):
                    raise LearnableSROKError("model weights became non-finite")
            mean_loss = total_loss / example_count
            if not math.isfinite(mean_loss):
                raise LearnableSROKError("training loss became non-finite")
            history.append(mean_loss)
            self.training_steps += 1
        return history

    def retrieve(self, role_index: int, nodes: Iterable[Node], *, top_k: int):
        """Role-conditioned top-k retrieval after deterministic hard filtering."""
        if isinstance(role_index, bool) or not isinstance(role_index, int) or not 0 <= role_index < len(self.roles):
            raise LearnableSROKError("role_index out of range")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise LearnableSROKError("top_k must be a positive integer")
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
        abstain_margin: float = 0.0, retrieval_mode: str = "unary",
        search_strategy: str = "product", beam_width: int = 64,
    ) -> Prediction:
        """Retrieve, compose, score, and optionally abstain under fixed budgets.

        unary preserves role-wise Top-K retrieval. joint retains every
        type/tag-compatible candidate. Product exhaustively enumerates the
        Cartesian product; Beam is approximate and abstains after pruning;
        branch_bound uses an admissible upper bound to certify exact top-k
        results when it finishes within max_expansions.
        """
        if isinstance(result_limit, bool) or not isinstance(result_limit, int) or result_limit < 1:
            raise LearnableSROKError("result_limit must be a positive integer")
        if isinstance(top_k_per_role, bool) or not isinstance(top_k_per_role, int) or top_k_per_role < 1:
            raise LearnableSROKError("top_k_per_role must be a positive integer")
        if isinstance(max_expansions, bool) or not isinstance(max_expansions, int) or max_expansions < 1:
            raise LearnableSROKError("max_expansions must be a positive integer")
        if not isinstance(abstain_margin, (int, float)) or isinstance(abstain_margin, bool) or not math.isfinite(abstain_margin) or abstain_margin < 0:
            raise LearnableSROKError("abstain_margin must be finite and non-negative")
        if retrieval_mode not in ("unary", "joint"):
            raise LearnableSROKError("retrieval_mode must be 'unary' or 'joint'")
        if search_strategy not in ("product", "beam", "branch_bound"):
            raise LearnableSROKError("search_strategy must be 'product', 'beam', or 'branch_bound'")
        if isinstance(beam_width, bool) or not isinstance(beam_width, int) or beam_width < 1:
            raise LearnableSROKError("beam_width must be a positive integer")
        node_list = tuple(nodes)
        for node in node_list:
            self._validate_node(node)
        if len({node.node_id for node in node_list}) != len(node_list):
            raise LearnableSROKError("node IDs must be unique")
        if retrieval_mode == "unary":
            retrieved = tuple(
                self.retrieve(i, node_list, top_k=top_k_per_role)
                for i in range(len(self.roles))
            )
            pools = tuple(tuple(node for node, _ in items) for items in retrieved)
        else:
            # Joint mode avoids unary Top-K truncation. Hard type/tag
            # constraints remain active; relational scoring ranks complete
            # distinct assignments after bounded enumeration.
            pools = tuple(
                tuple(sorted(
                    (node for node in node_list if self._compatible(node, role)),
                    key=lambda node: node.node_id,
                ))
                for role in self.roles
            )
        sizes = tuple((role.name, len(pool)) for role, pool in zip(self.roles, pools))
        if any(not pool for pool in pools):
            return Prediction((), True, "NO_ROLE_CANDIDATES", 0, False, sizes)
        pruned = False
        if search_strategy == "branch_bound" and retrieval_mode != "joint":
            raise LearnableSROKError("branch_bound search requires retrieval_mode='joint'")
        if retrieval_mode == "joint" and search_strategy == "beam":
            assignments, exhausted, pruned, expanded = self._beam_enumerate(
                pools, max_expansions, beam_width
            )
        elif retrieval_mode == "joint" and search_strategy == "branch_bound":
            assignments, exhausted, expanded = self._branch_bound_enumerate(
                pools, max_expansions, max(result_limit, 2)
            )
        else:
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
            reason = (
                "SEARCH_BUDGET_EXHAUSTED" if exhausted
                else "BEAM_PRUNED" if pruned
                else "NO_VALID_ASSIGNMENT"
            )
            return Prediction(
                (), True, reason, expanded, exhausted, sizes
            )
        # Budget truncation and beam pruning both make the search incomplete.
        # Preserve any discovered candidates for inspection, but never report
        # an incomplete search as an accepted global ranking.
        if exhausted:
            return Prediction(
                structures, True, "SEARCH_BUDGET_EXHAUSTED",
                expanded, True, sizes,
            )
        if pruned:
            return Prediction(
                structures, True, "BEAM_PRUNED", expanded, False, sizes,
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


    def checkpoint_json(self) -> str:
        """Serialize all learned parameters in a deterministic, integrity-checked envelope."""
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
        """Restore model state after strict schema, digest, shape and finiteness checks."""
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
        if not isinstance(supplied_digest, str) or supplied_digest != actual_digest:
            raise LearnableSROKError("checkpoint digest mismatch")
        if (
            payload["format"] != "zhouyi-ai.n10.learnable-srok"
            or isinstance(payload["schema_version"], bool)
            or not isinstance(payload["schema_version"], int)
            or payload["schema_version"] != 1
        ):
            raise LearnableSROKError("unsupported checkpoint format or version")
        feature_dim = payload["feature_dim"]
        if isinstance(feature_dim, bool) or not isinstance(feature_dim, int) or feature_dim < 1:
            raise LearnableSROKError("checkpoint feature_dim must be a positive integer")
        raw_roles = payload["roles"]
        if not isinstance(raw_roles, list) or len(raw_roles) < 2:
            raise LearnableSROKError("checkpoint roles must be a list of at least two roles")
        roles = []
        for item in raw_roles:
            if (
                not isinstance(item, dict)
                or set(item) != {"name", "allowed_types", "required_tags"}
                or not isinstance(item["name"], str) or not item["name"].strip()
                or not isinstance(item["allowed_types"], list)
                or not isinstance(item["required_tags"], list)
                or any(
                    not isinstance(value, str) or not value.strip()
                    for value in item["allowed_types"] + item["required_tags"]
                )
            ):
                raise LearnableSROKError("invalid checkpoint role schema")
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
