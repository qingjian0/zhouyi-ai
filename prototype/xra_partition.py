"""Exact predictive-equivalence partitioning for finite deterministic worlds.

This is an evaluator-side oracle for tiny benchmark worlds. It is not a
learner and must never be exposed as learner-visible ground truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable, Mapping, Sequence, TypeVar

State = TypeVar("State", bound=Hashable)
Action = TypeVar("Action", bound=Hashable)
Outcome = TypeVar("Outcome", bound=Hashable)


@dataclass(frozen=True)
class PartitionResult:
    """Coarsest deterministic bisimulation partition in input-state order."""
    blocks: tuple[tuple[Hashable, ...], ...]
    state_to_block: tuple[tuple[Hashable, int], ...]
    refinement_rounds: int

    def block_of(self, state: Hashable) -> int:
        for item, block_id in self.state_to_block:
            if item == state:
                return block_id
        raise KeyError(state)

    def equivalent(self, left: Hashable, right: Hashable) -> bool:
        return self.block_of(left) == self.block_of(right)


def _assign_block_ids(signatures: Sequence[Hashable]) -> tuple[int, ...]:
    signature_to_id: dict[Hashable, int] = {}
    ids: list[int] = []
    for signature in signatures:
        try:
            block_id = signature_to_id.get(signature)
        except TypeError as exc:
            raise ValueError("outcomes and signatures must be hashable") from exc
        if block_id is None:
            block_id = len(signature_to_id)
            signature_to_id[signature] = block_id
        ids.append(block_id)
    return tuple(ids)


def exact_predictive_partition(
    states: Sequence[State],
    actions: Sequence[Action],
    outcomes: Mapping[tuple[State, Action], Outcome],
    transitions: Mapping[tuple[State, Action], State],
) -> PartitionResult:
    """Compute the coarsest deterministic predictive-equivalence partition.

    Two states remain equivalent iff, for every declared action, they produce
    the same immediate outcome and transition into the same final block.
    The finite transition/outcome tables must be complete and deterministic.
    """
    state_values = tuple(states)
    action_values = tuple(actions)
    if not state_values or not action_values:
        raise ValueError("states and actions must both be non-empty")
    if len(set(state_values)) != len(state_values):
        raise ValueError("states must be unique")
    if len(set(action_values)) != len(action_values):
        raise ValueError("actions must be unique")

    expected = {(state, action) for state in state_values for action in action_values}
    if set(outcomes) != expected:
        raise ValueError("outcome table must contain exactly one value per state/action")
    if set(transitions) != expected:
        raise ValueError("transition table must contain exactly one next state per state/action")
    state_set = set(state_values)
    if any(next_state not in state_set for next_state in transitions.values()):
        raise ValueError("every transition target must be a declared state")

    # Begin with the coarsest partition; refine until no block can be split.
    block_ids = (0,) * len(state_values)
    rounds = 0
    while True:
        signatures = tuple(
            tuple(
                (outcomes[(state, action)],
                 block_ids[state_values.index(transitions[(state, action)])])
                for action in action_values
            )
            for state in state_values
        )
        refined = _assign_block_ids(signatures)
        rounds += 1
        if refined == block_ids:
            break
        block_ids = refined

    grouped: list[list[Hashable]] = []
    for state, block_id in zip(state_values, block_ids):
        while len(grouped) <= block_id:
            grouped.append([])
        grouped[block_id].append(state)

    return PartitionResult(
        blocks=tuple(tuple(block) for block in grouped),
        state_to_block=tuple(zip(state_values, block_ids)),
        refinement_rounds=rounds,
    )
