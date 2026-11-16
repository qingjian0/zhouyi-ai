"""Exact small-state audit for the bipartite 2-switch Markov kernel."""
from __future__ import annotations

import itertools
from collections import Counter, deque
from typing import Sequence


def _canonical(rows: Sequence[set[str]]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(sorted(row)) for row in rows)


def enumerate_degree_realizations(
    row_degrees: Sequence[int],
    item_degrees: dict[str, int],
    *,
    max_states: int = 10000,
) -> list[tuple[tuple[str, ...], ...]]:
    """Enumerate all simple bipartite graphs with the requested margins."""
    if not row_degrees or not item_degrees:
        raise ValueError("row_degrees and item_degrees must be non-empty")
    universe = tuple(sorted(item_degrees))
    if any(not isinstance(d, int) or isinstance(d, bool) or d < 0 or d > len(universe)
           for d in row_degrees):
        raise ValueError("invalid row degree")
    if any(not isinstance(d, int) or isinstance(d, bool) or d < 0 or d > len(row_degrees)
           for d in item_degrees.values()):
        raise ValueError("invalid item degree")
    if sum(row_degrees) != sum(item_degrees.values()):
        raise ValueError("row and item degree sums must match")
    if max_states < 1:
        raise ValueError("max_states must be positive")

    option_lists = [
        list(itertools.combinations(universe, degree))
        for degree in row_degrees
    ]
    upper_bound = 1
    for options in option_lists:
        upper_bound *= len(options)
    if upper_bound > max_states * 1000:
        raise ValueError("enumeration search space exceeds safety bound")

    target = Counter(item_degrees)
    states = []
    for candidate in itertools.product(*option_lists):
        counts = Counter(item for row in candidate for item in row)
        if counts == target:
            states.append(tuple(tuple(row) for row in candidate))
            if len(states) > max_states:
                raise ValueError("realization count exceeds max_states")
    return states


def _switch_transition_counts(
    state: tuple[tuple[str, ...], ...],
) -> Counter:
    rows = [set(row) for row in state]
    edges = [(row_index, item) for row_index, row in enumerate(rows) for item in row]
    transitions = Counter()
    for index1, (r1, i1) in enumerate(edges):
        for index2, (r2, i2) in enumerate(edges):
            if index1 == index2 or r1 == r2 or i1 == i2:
                continue
            if i2 in rows[r1] or i1 in rows[r2]:
                continue
            changed = [set(row) for row in rows]
            changed[r1].remove(i1)
            changed[r2].remove(i2)
            changed[r1].add(i2)
            changed[r2].add(i1)
            target = _canonical(changed)
            transitions[target] += 1
    return transitions


def audit_small_state_space(
    row_degrees: Sequence[int],
    item_degrees: dict[str, int],
    *,
    max_states: int = 10000,
) -> dict:
    """Check connectivity and detailed-balance symmetry of the 2-switch kernel."""
    states = enumerate_degree_realizations(
        row_degrees, item_degrees, max_states=max_states
    )
    state_set = set(states)
    if not states:
        return {
            "state_count": 0,
            "connected": False,
            "asymmetric_transition_pairs": 0,
            "stationary_uniformity_supported": False,
            "reason": "No graph realization matches the supplied margins.",
        }

    adjacency = {state: set() for state in states}
    asymmetric_pairs = 0
    directed_pairs = set()
    for state in states:
        transitions = _switch_transition_counts(state)
        for target, count in transitions.items():
            if target not in state_set:
                raise AssertionError("2-switch left the fixed-margin state space")
            adjacency[state].add(target)
            directed_pairs.add((state, target, count))

    for state, target, count in directed_pairs:
        reverse_count = _switch_transition_counts(target).get(state, 0)
        if reverse_count != count:
            asymmetric_pairs += 1

    visited = {states[0]}
    queue = deque([states[0]])
    while queue:
        current = queue.popleft()
        for neighbor in adjacency[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    connected = len(visited) == len(states)
    symmetric = asymmetric_pairs == 0
    return {
        "state_count": len(states),
        "connected": connected,
        "asymmetric_transition_pairs": asymmetric_pairs,
        "stationary_uniformity_supported": connected and symmetric,
        "interpretation": (
            "For this finite degree sequence, the enumerated 2-switch graph is "
            "connected and the proposal transition counts are symmetric; with "
            "the algorithm's self-loop probability this supports a uniform "
            "stationary distribution on the enumerated realizations. It does "
            "not establish finite-time mixing or generalize to untested inputs."
            if connected and symmetric else
            "The tested state space is disconnected or transition counts are "
            "asymmetric; do not assume a uniform stationary distribution."
        ),
    }
