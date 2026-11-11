"""YJ-10.3: evidence-constrained partial permutation groups.

This module learns a subgroup of slot permutations from explicit, independent
compatibility/conflict observations. Group closure is a mathematical
consequence of the selected generators, not additional empirical evidence.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from itertools import permutations
from typing import Iterable


class PermutationGroupError(ValueError):
    """Invalid permutation evidence or exceeded group-closure budget."""


@dataclass(frozen=True)
class SlotPermutationEvidence:
    permutation: tuple[int, ...]
    evidence_id: str
    compatible: bool

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
            raise PermutationGroupError("evidence_id is required")
        if not isinstance(self.compatible, bool):
            raise PermutationGroupError("compatible must be boolean")


@dataclass(frozen=True)
class PermutationSupport:
    permutation: tuple[int, ...]
    compatible_evidence_ids: tuple[str, ...]
    conflicting_evidence_ids: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class PermutationGroupHypothesis:
    arity: int
    directly_supported_generators: tuple[tuple[int, ...], ...]
    generated_group: tuple[tuple[int, ...], ...]
    closure_only_elements: tuple[tuple[int, ...], ...]
    support: tuple[PermutationSupport, ...]
    min_support: int


@dataclass(frozen=True)
class SymmetryGroupTransition:
    from_group_order: int
    to_group_order: int
    relation: str
    removed_permutations: tuple[tuple[int, ...], ...]
    added_permutations: tuple[tuple[int, ...], ...]


def _validate_permutation(value: tuple[int, ...], arity: int) -> None:
    if not isinstance(value, tuple) or len(value) != arity:
        raise PermutationGroupError("permutation arity mismatch")
    if any(not isinstance(item, int) or isinstance(item, bool) for item in value):
        raise PermutationGroupError("permutation entries must be integers")
    if set(value) != set(range(arity)):
        raise PermutationGroupError("permutation must be a bijection over slot indices")


def _compose(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[int, ...]:
    """Return left after right: (left ∘ right)(i) = left(right(i))."""
    return tuple(left[right[index]] for index in range(len(left)))


def _inverse(value: tuple[int, ...]) -> tuple[int, ...]:
    result = [0] * len(value)
    for source, target in enumerate(value):
        result[target] = source
    return tuple(result)


def _closure(
    arity: int,
    generators: Iterable[tuple[int, ...]],
    *,
    max_group_elements: int,
) -> tuple[tuple[int, ...], ...]:
    identity = tuple(range(arity))
    steps = set(generators)
    steps.update(_inverse(item) for item in tuple(steps))
    discovered = {identity}
    queue = deque([identity])
    while queue:
        current = queue.popleft()
        for generator in sorted(steps):
            candidate = _compose(current, generator)
            if candidate in discovered:
                continue
            discovered.add(candidate)
            if len(discovered) > max_group_elements:
                raise PermutationGroupError(
                    "generated subgroup exceeds max_group_elements; no partial closure returned"
                )
            queue.append(candidate)
    return tuple(sorted(discovered))


def learn_slot_permutation_group(
    arity: int,
    observations: Iterable[SlotPermutationEvidence],
    *,
    min_support: int = 2,
    max_group_elements: int = 100_000,
) -> PermutationGroupHypothesis:
    """Learn a conservative subgroup from supported, non-contradicted swaps.

    A permutation becomes a generator only when it has at least min_support
    distinct compatible evidence IDs and zero conflicting evidence IDs.
    The generated subgroup may contain closure-only elements; these are
    algebraically implied by the selected generators, not directly observed.
    """
    if not isinstance(arity, int) or isinstance(arity, bool) or not 2 <= arity <= 8:
        raise PermutationGroupError("arity must be between 2 and 8")
    if not isinstance(min_support, int) or isinstance(min_support, bool) or min_support < 1:
        raise PermutationGroupError("min_support must be positive")
    if (not isinstance(max_group_elements, int) or isinstance(max_group_elements, bool)
            or max_group_elements < 1):
        raise PermutationGroupError("max_group_elements must be positive")

    rows = tuple(observations)
    buckets: dict[tuple[int, ...], dict[str, set[str]]] = defaultdict(
        lambda: {"compatible": set(), "conflicting": set()}
    )
    for row in rows:
        _validate_permutation(row.permutation, arity)
        bucket = buckets[row.permutation]
        bucket["compatible" if row.compatible else "conflicting"].add(row.evidence_id)

    support_rows = []
    generators = []
    for candidate in sorted(buckets):
        compatible = tuple(sorted(buckets[candidate]["compatible"]))
        conflicting = tuple(sorted(buckets[candidate]["conflicting"]))
        if conflicting:
            status = "CONTRADICTED"
        elif len(compatible) >= min_support:
            status = "SUPPORTED"
            if candidate != tuple(range(arity)):
                generators.append(candidate)
        else:
            status = "UNRESOLVED"
        support_rows.append(PermutationSupport(
            candidate, compatible, conflicting, status
        ))

    generated = _closure(
        arity, generators, max_group_elements=max_group_elements
    )
    directly_observed = {row.permutation for row in support_rows
                         if row.status == "SUPPORTED"}
    closure_only = tuple(item for item in generated if item not in directly_observed)
    return PermutationGroupHypothesis(
        arity=arity,
        directly_supported_generators=tuple(generators),
        generated_group=generated,
        closure_only_elements=closure_only,
        support=tuple(support_rows),
        min_support=min_support,
    )


def compare_symmetry_groups(
    before: Iterable[tuple[int, ...]],
    after: Iterable[tuple[int, ...]],
) -> SymmetryGroupTransition:
    """Classify group evolution; strict subgroup reduction is symmetry breaking."""
    old = tuple(sorted(set(before)))
    new = tuple(sorted(set(after)))
    if not old or not new:
        raise PermutationGroupError("both groups must contain at least the identity")
    arity = len(old[0])
    if any(len(item) != arity for item in old + new):
        raise PermutationGroupError("group arities must match")
    for item in old + new:
        _validate_permutation(item, arity)
    old_set, new_set = set(old), set(new)
    if old_set == new_set:
        relation = "UNCHANGED"
    elif new_set < old_set:
        relation = "SYMMETRY_BROKEN"
    elif old_set < new_set:
        relation = "SYMMETRY_EXPANDED"
    else:
        relation = "RECONFIGURED"
    return SymmetryGroupTransition(
        len(old), len(new), relation,
        tuple(sorted(old_set - new_set)),
        tuple(sorted(new_set - old_set)),
    )
