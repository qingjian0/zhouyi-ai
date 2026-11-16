"""Conditional motif proposals for finite CPG-EI hyperedge discovery.

This diagnostic proposes a whole 3-line motif (its three pairwise terms plus
its third-order term) as one unit. It is deliberately separate from the greedy
default: it tests whether joint conditional fitting can recover parity support
that has no useful first-order pairwise correlation.
"""
from __future__ import annotations

import itertools
import math
from typing import Sequence

from prototype.cpg_ei_mvp import Example, FEATURE_NAMES, encode_state


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Deterministic Gauss-Jordan solve with partial pivoting."""
    size = len(vector)
    augmented = [list(row) + [vector[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) <= 1e-14:
            raise ValueError("singular conditional-proposal system")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        for j in range(column, size + 1):
            augmented[column][j] /= scale
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0.0:
                continue
            for j in range(column, size + 1):
                augmented[row][j] -= factor * augmented[column][j]
    result = [augmented[index][size] for index in range(size)]
    if any(not math.isfinite(value) for value in result):
        raise ValueError("non-finite conditional-proposal solution")
    return result


def _ridge_sse(rows: Sequence[Sequence[float]], targets: Sequence[float], ridge: float) -> float:
    width = len(rows[0])
    gram = [[0.0] * width for _ in range(width)]
    rhs = [0.0] * width
    for row, target in zip(rows, targets):
        for i, left in enumerate(row):
            rhs[i] += left * target
            for j, right in enumerate(row):
                gram[i][j] += left * right
    for index in range(width):
        gram[index][index] += ridge
    weights = _solve_linear_system(gram, rhs)
    return sum(
        (target - sum(weight * value for weight, value in zip(weights, row))) ** 2
        for row, target in zip(rows, targets)
    )


def rank_conditional_motifs(
    examples: Sequence[Example], *, max_motifs: int = 3, ridge: float = 1e-8
) -> dict:
    """Rank 3-line motifs by multi-feature conditional SSE reduction on train data.

    A motif is proposed atomically as three pairwise conjunctions plus the
    corresponding third-order conjunction. Scores are summed across six
    transition heads. Only the supplied examples are used; callers must pass
    training data, not validation or locked-test labels.
    """
    if not examples:
        raise ValueError("examples must be non-empty")
    if isinstance(max_motifs, bool) or not isinstance(max_motifs, int) or not 1 <= max_motifs <= 20:
        raise ValueError("max_motifs must be an integer in [1, 20]")
    if isinstance(ridge, bool) or not isinstance(ridge, (int, float)) or not math.isfinite(ridge) or ridge <= 0:
        raise ValueError("ridge must be finite and positive")
    if any(not isinstance(row, Example) for row in examples):
        raise ValueError("examples must contain Example records")

    encoded = [encode_state(row.state) for row in examples]
    base_rows = [list(row[:7]) for row in encoded]
    feature_index = {name: index for index, name in enumerate(FEATURE_NAMES)}
    candidates = []
    for lines in itertools.combinations(range(6), 3):
        pair_names = [
            "hyperedge_2_" + "_".join(map(str, pair))
            for pair in itertools.combinations(lines, 2)
        ]
        triple_name = "hyperedge_3_" + "_".join(map(str, lines))
        indices = [feature_index[name] for name in (*pair_names, triple_name)]
        augmented_rows = [
            [*base, *(row[index] for index in indices)]
            for base, row in zip(base_rows, encoded)
        ]
        per_head = []
        total_gain = 0.0
        for head in range(6):
            targets = [float(row.target[head]) for row in examples]
            baseline = _ridge_sse(base_rows, targets, ridge)
            augmented = _ridge_sse(augmented_rows, targets, ridge)
            gain = max(0.0, baseline - augmented)
            per_head.append(gain)
            total_gain += gain
        candidates.append({
            "lines": list(lines),
            "feature_names": [*pair_names, triple_name],
            "score": total_gain,
            "per_head_score": per_head,
        })
    candidates.sort(key=lambda item: (-item["score"], item["lines"]))
    return {
        "method": "conditional_four_term_motif",
        "candidate_count": len(candidates),
        "selected": candidates[:max_motifs],
        "ranked": candidates,
        "claim_boundary": (
            "Finite six-line motif-proposal diagnostic; not open-world relation "
            "induction, natural-language reasoning, or evidence of general transfer."
        ),
    }
