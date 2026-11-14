"""Exhaustive degree-sequence sweep for tiny bipartite 2-switch state spaces."""
from __future__ import annotations
import itertools
from collections import Counter
from math import comb
from prototype.e12m2_exact_state_audit import _switch_transition_counts, audit_small_state_space

def _all_binary_matrices(rows, items):
    for bits in itertools.product((0, 1), repeat=rows * items):
        yield tuple(tuple(bits[r * items:(r + 1) * items]) for r in range(rows))

def _margins(matrix):
    return (tuple(map(sum, matrix)),
            tuple(sum(matrix[r][c] for r in range(len(matrix)))
                  for c in range(len(matrix[0]))))

def _states_for_margins(shape, margins):
    rows, items = shape
    result = []
    for matrix in _all_binary_matrices(rows, items):
        if _margins(matrix) == margins:
            result.append(tuple(tuple(f"i{c}" for c, present in enumerate(row) if present)
                                for row in matrix))
    return result

def _audit_exact_kernel(states):
    """Include rejected proposals as self-loops and audit exact row/column sums."""
    if not states:
        return {"proposal_count": 0, "row_sums_exact": False, "column_sums_exact": False}
    edges = sum(map(len, states[0]))
    proposals = comb(edges, 2)
    if proposals == 0:
        return {"proposal_count": 0, "row_sums_exact": True, "column_sums_exact": True}
    allowed = set(states)
    columns = Counter()
    rows_ok = True
    for state in states:
        directed = _switch_transition_counts(state)
        off = {}
        for target, ordered_count in directed.items():
            if target not in allowed:
                raise AssertionError("transition escaped fixed-margin state space")
            if ordered_count % 2:
                raise AssertionError("ordered transition count must be even")
            off[target] = ordered_count // 2
        diagonal = proposals - sum(off.values())
        if diagonal < 0:
            raise AssertionError("transition count exceeds proposal count")
        rows_ok &= diagonal + sum(off.values()) == proposals
        columns[state] += diagonal
        for target, count in off.items():
            columns[target] += count
    return {
        "proposal_count": proposals,
        "row_sums_exact": rows_ok,
        "column_sums_exact": all(columns[state] == proposals for state in states),
    }

def run_tiny_state_space_sweep(*, shapes=((2, 2), (2, 3), (3, 2), (3, 3)), max_states=10000):
    """Audit every feasible margin profile represented by all tiny matrices."""
    if not shapes:
        raise ValueError("shapes must be non-empty")
    if max_states < 1:
        raise ValueError("max_states must be positive")
    results, disconnected, asymmetric = [], [], []
    maximum = 0
    for shape in shapes:
        rows, items = shape
        if not (1 <= rows <= 3 and 1 <= items <= 3):
            raise ValueError("exhaustive sweep supports dimensions from 1 to 3")
        profiles = {_margins(matrix) for matrix in _all_binary_matrices(rows, items)}
        for row_degrees, item_degrees in sorted(profiles):
            item_map = {f"i{i}": degree for i, degree in enumerate(item_degrees)}
            report = audit_small_state_space(row_degrees, item_map, max_states=max_states)
            states = _states_for_margins(shape, (row_degrees, item_degrees))
            kernel = _audit_exact_kernel(states)
            result = {
                "shape": list(shape), "row_degrees": list(row_degrees),
                "item_degrees": list(item_degrees), "state_count": report["state_count"],
                "connected": report["connected"],
                "asymmetric_transition_pairs": report["asymmetric_transition_pairs"],
                **kernel,
            }
            results.append(result)
            maximum = max(maximum, report["state_count"])
            if not report["connected"]:
                disconnected.append(result)
            if report["asymmetric_transition_pairs"] or not kernel["column_sums_exact"]:
                asymmetric.append(result)
    return {
        "shapes": [list(shape) for shape in shapes], "profile_count": len(results),
        "max_state_count": maximum, "all_state_spaces_connected": not disconnected,
        "all_transition_kernels_symmetric": not asymmetric,
        "all_transition_matrices_doubly_stochastic": all(
            item["row_sums_exact"] and item["column_sums_exact"] for item in results),
        "disconnected_profiles": disconnected, "asymmetric_profiles": asymmetric,
        "profiles": results,
        "scope": "Exhaustive only for enumerated labeled matrices and dimensions; not a proof for larger graphs or finite-time mixing.",
    }

if __name__ == "__main__":
    import json
    print(json.dumps(run_tiny_state_space_sweep(), indent=2, sort_keys=True))
