"""SROK-0: deterministic sparse role-based relational composition.

This is an executable algorithmic baseline, not a trained model. It composes
non-adjacent evidence items into role-typed multi-way candidates under explicit
candidate and expansion budgets. Learned routing/scoring can replace the
deterministic components only after this baseline is measured.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
from typing import Callable, Iterable, Sequence


@dataclass(frozen=True)
class Node:
    node_id: str
    node_type: str
    tags: frozenset[str] = frozenset()
    score: float = 0.0
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoleSpec:
    name: str
    allowed_types: frozenset[str] = frozenset()
    required_tags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class OperatorSpec:
    name: str
    relation_type: str
    roles: tuple[RoleSpec, ...]
    max_candidates_per_role: int = 32
    max_expansions: int = 10_000


@dataclass(frozen=True)
class ComposedCandidate:
    relation_type: str
    role_bindings: tuple[tuple[str, str], ...]
    score: float
    evidence_ids: tuple[str, ...]

    @property
    def member_ids(self) -> tuple[str, ...]:
        return tuple(node_id for _, node_id in self.role_bindings)


@dataclass(frozen=True)
class SearchReport:
    candidates: tuple[ComposedCandidate, ...]
    candidate_pool_sizes: tuple[tuple[str, int], ...]
    expanded_assignments: int
    valid_assignments: int
    budget_exhausted: bool


JointScorer = Callable[[tuple[Node, ...]], float]
HardConstraint = Callable[[tuple[Node, ...]], bool]


class SROKValidationError(ValueError):
    """Raised when a schema or search budget is invalid."""


class SparseRoleComposer:
    """Build role-compatible candidates without enumerating all node subsets.

    The search enumerates a bounded Cartesian product of per-role sparse
    candidate pools. It is deliberately explicit about recall limits: a
    correct assignment omitted by role retrieval cannot be recovered later.
    """

    def __init__(self, nodes: Iterable[Node]) -> None:
        self.nodes = tuple(nodes)
        ids = [node.node_id for node in self.nodes]
        if any(not node.node_id or not node.node_type for node in self.nodes):
            raise SROKValidationError("node_id and node_type are required")
        if len(ids) != len(set(ids)):
            raise SROKValidationError("node_id values must be unique")
        if any(not math.isfinite(node.score) for node in self.nodes):
            raise SROKValidationError("node scores must be finite")
        self._by_id = {node.node_id: node for node in self.nodes}
        self._by_type: dict[str, set[str]] = {}
        self._by_tag: dict[str, set[str]] = {}
        for node in self.nodes:
            self._by_type.setdefault(node.node_type, set()).add(node.node_id)
            for tag in node.tags:
                self._by_tag.setdefault(tag, set()).add(node.node_id)

    def _pool(self, role: RoleSpec, limit: int) -> tuple[Node, ...]:
        if not role.name:
            raise SROKValidationError("role names must be non-empty")
        if role.allowed_types:
            eligible: set[str] = set()
            for node_type in role.allowed_types:
                eligible.update(self._by_type.get(node_type, set()))
        else:
            eligible = set(self._by_id)
        for tag in role.required_tags:
            eligible.intersection_update(self._by_tag.get(tag, set()))
        ranked = sorted(
            (self._by_id[node_id] for node_id in eligible),
            key=lambda node: (-node.score, node.node_id),
        )
        return tuple(ranked[:limit])

    @staticmethod
    def _validate_spec(spec: OperatorSpec) -> None:
        if not spec.name or not spec.relation_type:
            raise SROKValidationError("operator name and relation_type are required")
        if len(spec.roles) < 2:
            raise SROKValidationError("an operator requires at least two roles")
        names = [role.name for role in spec.roles]
        if len(names) != len(set(names)):
            raise SROKValidationError("role names must be unique")
        if spec.max_candidates_per_role < 1 or spec.max_expansions < 1:
            raise SROKValidationError("search budgets must be positive")

    def compose(
        self,
        spec: OperatorSpec,
        *,
        limit: int = 10,
        joint_scorer: JointScorer | None = None,
        hard_constraint: HardConstraint | None = None,
    ) -> SearchReport:
        """Return the best valid assignments found within the explicit budget.

        Base priority is the sum of node scores. The optional joint scorer is
        applied to complete assignments, so it cannot be used as an admissible
        pruning bound; consequently this method promises bounded enumeration,
        not globally optimal ranking under arbitrary joint scores.
        """
        self._validate_spec(spec)
        if limit < 1:
            raise SROKValidationError("result limit must be positive")

        pools = tuple(
            self._pool(role, spec.max_candidates_per_role) for role in spec.roles
        )
        pool_sizes = tuple(
            (role.name, len(pool)) for role, pool in zip(spec.roles, pools)
        )
        if any(not pool for pool in pools):
            return SearchReport((), pool_sizes, 0, 0, False)

        # Each pool is sorted by descending node score. A heap enumerates
        # Cartesian index vectors in descending additive base-score order.
        start = tuple(0 for _ in pools)

        def base_score(indices: tuple[int, ...]) -> float:
            return sum(pools[i][index].score for i, index in enumerate(indices))

        heap: list[tuple[float, tuple[str, ...], tuple[int, ...]]] = []
        heapq.heappush(heap, (-base_score(start), (), start))
        visited = {start}
        found: dict[tuple[str, ...], ComposedCandidate] = {}
        expanded = 0
        valid = 0

        while heap and expanded < spec.max_expansions:
            _, _, indices = heapq.heappop(heap)
            expanded += 1
            selected = tuple(pools[i][index] for i, index in enumerate(indices))
            member_ids = tuple(node.node_id for node in selected)

            if len(set(member_ids)) == len(member_ids):
                if hard_constraint is None or hard_constraint(selected):
                    valid += 1
                    extra = joint_scorer(selected) if joint_scorer else 0.0
                    if not math.isfinite(extra):
                        raise SROKValidationError("joint score must be finite")
                    score = sum(node.score for node in selected) + extra
                    evidence = tuple(dict.fromkeys(
                        evidence_id
                        for node in selected
                        for evidence_id in node.evidence_ids
                    ))
                    candidate = ComposedCandidate(
                        relation_type=spec.relation_type,
                        role_bindings=tuple(
                            (role.name, node.node_id)
                            for role, node in zip(spec.roles, selected)
                        ),
                        score=score,
                        evidence_ids=evidence,
                    )
                    found[member_ids] = candidate

            for dimension, pool in enumerate(pools):
                next_index = indices[dimension] + 1
                if next_index >= len(pool):
                    continue
                neighbor = list(indices)
                neighbor[dimension] = next_index
                neighbor_key = tuple(neighbor)
                if neighbor_key in visited:
                    continue
                visited.add(neighbor_key)
                heapq.heappush(
                    heap,
                    (-base_score(neighbor_key), (), neighbor_key),
                )

        ranked = sorted(
            found.values(),
            key=lambda candidate: (-candidate.score, candidate.member_ids),
        )[:limit]
        return SearchReport(
            candidates=tuple(ranked),
            candidate_pool_sizes=pool_sizes,
            expanded_assignments=expanded,
            valid_assignments=valid,
            budget_exhausted=bool(heap),
        )
