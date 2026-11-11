"""Exact stationary law and finite-run convergence audit for tiny 2-switch chains."""
from __future__ import annotations

import random
from collections import Counter
from fractions import Fraction
from math import comb

from prototype.e12m2_exact_state_audit import (
    _switch_transition_counts,
    enumerate_degree_realizations,
    audit_small_state_space,
)


def _transition_matrix(states):
    """Return an exact row-stochastic matrix using integer proposal counts."""
    if not states:
        raise ValueError("state space must be non-empty")
    edge_count = sum(map(len, states[0]))
    proposals = comb(edge_count, 2)
    if proposals == 0:
        return [[Fraction(int(i == j), 1) for j in range(len(states))]
                for i in range(len(states))]
    index = {state: i for i, state in enumerate(states)}
    matrix = []
    for state in states:
        row = [0] * len(states)
        off = 0
        for target, ordered_count in _switch_transition_counts(state).items():
            if target not in index:
                raise AssertionError("transition escaped fixed-margin state space")
            if ordered_count % 2:
                raise AssertionError("ordered transition multiplicity must be even")
            count = ordered_count // 2
            row[index[target]] += count
            off += count
        row[index[state]] += proposals - off
        matrix.append([Fraction(value, proposals) for value in row])
    return matrix


def _solve_fraction_system(matrix, rhs):
    """Gauss-Jordan solve; raises when the stationary system is singular."""
    n = len(rhs)
    augmented = [list(matrix[i]) + [rhs[i]] for i in range(n)]
    for column in range(n):
        pivot = next((r for r in range(column, n)
                      if augmented[r][column] != 0), None)
        if pivot is None:
            raise ValueError("stationary system is singular; state space may be reducible")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(n):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [
                    augmented[row][j] - factor * augmented[column][j]
                    for j in range(n + 1)
                ]
    return [augmented[i][-1] for i in range(n)]


def exact_stationary_distribution(transition_matrix):
    """Solve pi P = pi exactly, with sum(pi)=1."""
    n = len(transition_matrix)
    if n == 0 or any(len(row) != n for row in transition_matrix):
        raise ValueError("transition matrix must be non-empty and square")
    if any(sum(row) != 1 for row in transition_matrix):
        raise ValueError("transition matrix must be row-stochastic")
    if n == 1:
        return [Fraction(1, 1)]
    system = []
    rhs = []
    for column in range(n - 1):
        system.append([
            transition_matrix[row][column] - Fraction(int(row == column), 1)
            for row in range(n)
        ])
        rhs.append(Fraction(0, 1))
    system.append([Fraction(1, 1)] * n)
    rhs.append(Fraction(1, 1))
    distribution = _solve_fraction_system(system, rhs)
    if any(value < 0 for value in distribution):
        raise ValueError("stationary solution is not a probability distribution")
    return distribution


def _total_variation(empirical, target):
    return sum(abs(Fraction(empirical[i], sum(empirical)) - target[i])
               for i in range(len(target))) / 2


def run_finite_chain_convergence(
    row_degrees,
    item_degrees,
    *,
    chains=4,
    burn_in_steps=100,
    sample_steps=2000,
    seed=0,
):
    """Compare empirical chain occupancy with exact stationary probabilities."""
    if chains < 1 or burn_in_steps < 0 or sample_steps < 1:
        raise ValueError("invalid chain or step counts")
    states = enumerate_degree_realizations(row_degrees, item_degrees)
    if not states:
        raise ValueError("degree margins have no realizations")
    state_audit = audit_small_state_space(row_degrees, item_degrees)
    if not state_audit["connected"]:
        raise ValueError("finite-chain stationary solve requires a connected fixed-margin state space")
    matrix = _transition_matrix(states)
    stationary = exact_stationary_distribution(matrix)
    if any(value != Fraction(1, len(states)) for value in stationary):
        raise AssertionError("expected uniform stationary law for symmetric 2-switch kernel")

    reports = []
    pooled = [0] * len(states)
    for chain_index in range(chains):
        rng = random.Random(seed + chain_index)
        current = 0
        for _ in range(burn_in_steps):
            current = rng.choices(range(len(states)),
                                  weights=[int(value * _proposal_denominator(matrix))
                                           for value in matrix[current]], k=1)[0]
        counts = [0] * len(states)
        for _ in range(sample_steps):
            current = rng.choices(range(len(states)),
                                  weights=[int(value * _proposal_denominator(matrix))
                                           for value in matrix[current]], k=1)[0]
            counts[current] += 1
        for index, count in enumerate(counts):
            pooled[index] += count
        reports.append({
            "chain": chain_index,
            "sample_steps": sample_steps,
            "occupied_states": sum(count > 0 for count in counts),
            "total_variation": float(_total_variation(counts, stationary)),
            "state_counts": counts,
        })
    return {
        "state_count": len(states),
        "stationary_distribution": [
            {"state_index": i, "probability": str(value)}
            for i, value in enumerate(stationary)
        ],
        "transition_matrix": [
            [str(value) for value in row] for row in matrix
        ],
        "chains": reports,
        "pooled_total_variation": float(_total_variation(pooled, stationary)),
        "pooled_state_counts": pooled,
        "warning": (
            "Finite-run total variation is an empirical diagnostic, not a proof "
            "of convergence or a universal mixing-time bound. Results depend on "
            "the chosen initial state, graph margins, and run length."
        ),
    }


def _proposal_denominator(matrix):
    from math import lcm
    denominator = 1
    for row in matrix:
        for value in row:
            denominator = lcm(denominator, value.denominator)
    return denominator


if __name__ == "__main__":
    import json
    print(json.dumps(run_finite_chain_convergence(
        (1, 1), {"a": 1, "b": 1}, chains=2,
        burn_in_steps=20, sample_steps=200,
    ), indent=2, sort_keys=True))
