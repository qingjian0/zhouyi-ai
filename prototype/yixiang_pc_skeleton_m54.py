"""M54 experimental PC-style target-skeleton baseline.

This is deliberately not a full PC/FCI implementation: it estimates only the
adjacency set of one target, uses linear-Gaussian partial-correlation tests,
and does not orient edges or identify latent confounding.
"""
from itertools import combinations
from math import atanh, erfc, isfinite, sqrt

from prototype.yixiang_fair_baselines_m54 import BaselineProposal


def _center(values):
    mean = sum(values) / len(values)
    return [value - mean for value in values]


def _dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def _residualize(values, orthonormal_basis):
    residual = list(values)
    for basis in orthonormal_basis:
        projection = _dot(residual, basis)
        residual = [value - projection * direction
                    for value, direction in zip(residual, basis)]
    return residual


def _partial_correlation_pvalue(x_values, y_values, conditioning_columns):
    """Two-sided Fisher-z p-value for a partial correlation.

    Conditioning columns are orthogonalized with modified Gram-Schmidt.
    Singular/constant residuals are treated as conditionally independent;
    insufficient degrees of freedom are treated conservatively as dependent.
    """
    n = len(x_values)
    k = len(conditioning_columns)
    degrees_of_freedom = n - k - 3
    if degrees_of_freedom <= 0:
        return 0.0

    x = _center(x_values)
    y = _center(y_values)
    basis = []
    for column in conditioning_columns:
        vector = _center(column)
        vector = _residualize(vector, basis)
        norm_sq = _dot(vector, vector)
        if norm_sq <= 1e-20:
            continue
        norm = sqrt(norm_sq)
        basis.append([value / norm for value in vector])

    residual_x = _residualize(x, basis)
    residual_y = _residualize(y, basis)
    vx = _dot(residual_x, residual_x)
    vy = _dot(residual_y, residual_y)
    if vx <= 1e-20 or vy <= 1e-20:
        return 1.0

    correlation = _dot(residual_x, residual_y) / sqrt(vx * vy)
    correlation = max(-0.999999999999, min(0.999999999999, correlation))
    z_score = abs(atanh(correlation)) * sqrt(degrees_of_freedom)
    return erfc(z_score / sqrt(2.0))


def pc_skeleton_baseline(context, alpha=0.05, max_conditioning_size=2):
    """Return target-adjacent candidates after PC-style CI pruning.

    Assumptions: numeric, finite, approximately linear-Gaussian observations.
    This is a target-local skeleton heuristic, not full PC/FCI or a causal
    identification procedure. It has no edge orientation phase.
    """
    if (not isinstance(alpha, (int, float)) or isinstance(alpha, bool)
            or not isfinite(alpha) or not 0.0 < alpha < 1.0):
        raise ValueError("alpha_must_be_between_zero_and_one")
    if (not isinstance(max_conditioning_size, int)
            or isinstance(max_conditioning_size, bool)
            or max_conditioning_size < 0):
        raise ValueError("invalid_max_conditioning_size")

    names = tuple(name for name in context.candidate_variables
                  if name != context.target)
    rows = context.rows
    if len(rows) < 2:
        return BaselineProposal(())

    columns = {}
    try:
        for name in names + (context.target,):
            values = [float(row[name]) for row in rows]
            if not all(isfinite(value) for value in values):
                raise ValueError("non_finite_training_value")
            columns[name] = values
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid_numeric_training_data") from exc

    neighbors = list(names)
    conditioning_depth = min(max_conditioning_size, max(0, len(neighbors) - 1))
    for depth in range(conditioning_depth + 1):
        snapshot = tuple(neighbors)
        removals = []
        for candidate in snapshot:
            others = tuple(name for name in snapshot if name != candidate)
            if len(others) < depth:
                continue
            independent = False
            for subset in combinations(others, depth):
                p_value = _partial_correlation_pvalue(
                    columns[candidate], columns[context.target],
                    [columns[name] for name in subset],
                )
                if p_value >= alpha:
                    independent = True
                    break
            if independent:
                removals.append(candidate)
        if removals:
            neighbors = [name for name in neighbors if name not in set(removals)]
    return BaselineProposal(tuple(neighbors))
