"""Independent pair-elimination oracle for tiny deterministic worlds.

This deliberately does not use partition refinement. It computes the
greatest predictive bisimulation relation by eliminating distinguishable
state pairs. Evaluator-only; never expose its relation to a learner.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable, Mapping, Sequence, TypeVar

State = TypeVar("State", bound=Hashable)
Action = TypeVar("Action", bound=Hashable)
Outcome = TypeVar("Outcome", bound=Hashable)


@dataclass(frozen=True)
class PairEliminationResult:
    blocks: tuple[tuple[Hashable, ...], ...]
    related_pairs: frozenset[tuple[Hashable, Hashable]]
    elimination_rounds: int


def greatest_bisimulation_partition(
    states: Sequence[State],
    actions: Sequence[Action],
    outcomes: Mapping[tuple[State, Action], Outcome],
    transitions: Mapping[tuple[State, Action], State],
) -> PairEliminationResult:
    """Find predictive-equivalence classes by greatest-relation elimination.

    Start with every ordered state pair related. Repeatedly remove a pair when
    some action yields a different immediate outcome or successor states that
    are no longer related. The fixed point is independent of the partition
    refinement implementation in xra_partition.py.
    """
    state_values = tuple(states)
    action_values = tuple(actions)
    if not state_values or not action_values:
        raise ValueError("states and actions must both be non-empty")
    try:
        if len(set(state_values)) != len(state_values):
            raise ValueError("states must be unique")
        if len(set(action_values)) != len(action_values):
            raise ValueError("actions must be unique")
        expected = {(s, a) for s in state_values for a in action_values}
        if set(outcomes) != expected:
            raise ValueError("outcome table must contain exactly one value per state/action")
        if set(transitions) != expected:
            raise ValueError("transition table must contain exactly one next state per state/action")
        state_set = set(state_values)
        if any(target not in state_set for target in transitions.values()):
            raise ValueError("every transition target must be a declared state")
        for value in outcomes.values():
            hash(value)
    except TypeError as exc:
        raise ValueError("states, actions, outcomes, and transitions must be hashable") from exc

    relation = {(left, right) for left in state_values for right in state_values}
    rounds = 0
    while True:
        remove = set()
        for left, right in relation:
            for action in action_values:
                if outcomes[(left, action)] != outcomes[(right, action)]:
                    remove.add((left, right))
                    break
                next_pair = (
                    transitions[(left, action)],
                    transitions[(right, action)],
                )
                if next_pair not in relation:
                    remove.add((left, right))
                    break
        rounds += 1
        if not remove:
            break
        relation.difference_update(remove)

    # Materialize equivalence classes in caller-supplied state order.
    remaining = set(state_values)
    blocks = []
    for state in state_values:
        if state not in remaining:
            continue
        block = tuple(
            candidate for candidate in state_values
            if candidate in remaining and (state, candidate) in relation
        )
        if not block or state not in block:
            raise AssertionError("fixed-point relation is not reflexive")
        for left in block:
            for right in block:
                if (left, right) not in relation:
                    raise AssertionError("fixed-point relation is not an equivalence relation")
        blocks.append(block)
        remaining.difference_update(block)

    return PairEliminationResult(
        blocks=tuple(blocks),
        related_pairs=frozenset(relation),
        elimination_rounds=rounds,
    )
